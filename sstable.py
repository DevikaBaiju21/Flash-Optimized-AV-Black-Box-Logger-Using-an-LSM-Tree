"""
An SSTable is a file that is
  - SORTED by key      -> binary search and range queries are easy
  - IMMUTABLE          -> written once, never edited (sequential, flash-friendly)
  - NUMBERED           -> sst_1.txt is oldest, higher number = newer

Read rule: newest data wins. Search the MemTable first, then SSTables from the
newest file to the oldest. The first hit is the latest value. A tombstone hit
means "deleted", so the answer is "not found".

Complexity (m = records in a file, k = number of files):
  flush       : O(n) to write (n log n if we count sorting the memtable)
  get         : O(1) memtable + O(m) to load + O(log m) binary search per file
                (a sparse index would remove the O(m) load: future work)
  range query : O(k * (m + log m + r)) in this simple version, r = results
"""
import bisect
import os
import re

#Compiles a regular expression pattern into a reusable pattern matching object
_NAME = re.compile(r"^sst_(\d+)\.txt$")

class SSTableManager:
    def __init__(self, directory):
        """
        Initializes the SSTable storage manager.
        
        directory : str -> The folder path where all SSTable text files (.txt) live.
        """
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self.bytes_written = 0      

    def path_of(self, number):
        """Builds a full string path for a given file ID (e.g., 'data/sst_1.txt')"""
        return os.path.join(self.dir, f"sst_{number}.txt")

    def list_files(self):
        """Scans the directory and returns a sorted list of full paths from OLDEST to NEWEST"""
        numbered = []
        for name in os.listdir(self.dir):
            m = _NAME.match(name)
            if m:
                # Store tuple: (integer_id, full_path) -> sorts automatically by integer_id
                numbered.append((int(m.group(1)), os.path.join(self.dir, name)))
        numbered.sort()
        return [p for _, p in numbered]  # Strip the numbers out, return just the sorted paths

    def number_of(self, path):
        """Extracts the integer ID from an SSTable's filename string"""
        return int(_NAME.match(os.path.basename(path)).group(1))

    def next_number(self):
        """Determines the next unused ID counter. If no files exist, starts at 1"""
        files = self.list_files()
        return 1 if not files else self.number_of(files[-1]) + 1
    
    def write(self, records, number=None):
        """Physically saves a sorted list of (key, value, deleted) tuples to disk safely"""
        if number is None:
            number = self.next_number()
        final_path = self.path_of(number)
        tmp_path = final_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            for key, value, deleted in records:
                # Encode booleans as 1 (deleted) or 0 (active)
                line = f"{key}|{value}|{1 if deleted else 0}\n"
                f.write(line)
                self.bytes_written += len(line.encode("utf-8"))
            f.flush()            # Push data out of Python's buffer into OS cache
            os.fsync(f.fileno()) # Force OS cache to hard-engrave data onto the physical drive
        os.replace(tmp_path, final_path)
        return final_path

    def flush(self, memtable):
         """Dumps RAM data (MemTable) out onto the disk as a brand new sorted file"""
        if memtable.size() == 0:
            return None
        # Convert memory dict into an ordered list of tuples
        records = [(k, v, d) for k, (v, d) in memtable.sorted_items()]
        return self.write(records)
    
    def iter_file(self, path):
        """Memory-safe generator that yields parsed lines one by one without full-file loads"""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("|")
                if len(parts) == 3:
                    # Yield structures: (key, value, boolean_is_deleted)
                    yield parts[0], parts[1], parts[2] == "1"

    def load(self, path):
        """Eagerly consumes the file stream generator into a standard Python list"""
        return list(self.iter_file(path))

    def get_from_file(self, path, key):
        """Performs a Binary Search inside a single specific file path"""
        records = self.load(path)
        keys = [r[0] for r in records]
        i = bisect.bisect_left(keys, key)  # O(log m) binary pinpoint lookup
        if i < len(keys) and keys[i] == key:
            return records[i]
        return None

    def get(self, key, memtable):
        """High-level POINT LOOKUP: Checks RAM first, then searches disk NEWEST to OLDEST"""
        # Step 1: Check absolute latest volatile memory state
        hit = memtable.get(key)
        if hit is not None:
            value, deleted = hit
            return None if deleted else value

        # Step 2: Loop backwards through files (highest number = newest file wins)
        for path in reversed(self.list_files()):          
            rec = get_from_file(path, key)
            if rec is not None:
                return None if rec[2] else rec[1]          
        return None  # Missing completely from memory and disk
      
    def range(self, start, end, memtable):
         """High-level RANGE QUERY: Gathers all values matching start <= key <= end"""
        merged = {}

        # Step 1: Scan historical storage files from OLDEST to NEWEST. 
        # Newer files overwrite older duplicates naturally in our tracking dictionary.
        for path in self.list_files():                     
            records = self.load(path)
            keys = [r[0] for r in records]
            i = bisect.bisect_left(keys, start)            
            while i < len(records) and records[i][0] <= end:
                key, value, deleted = records[i]
                merged[key] = (value, deleted)             
                i += 1

        # Step 2: Merge memory data right over top. Overwrites older files with true fresh states.
        for key, (value, deleted) in memtable.range(start, end).items():
            merged[key] = (value, deleted)   
          
         # Step 3: Alphabetize the items dictionary and strip away deleted tombstones (if not d)
        return [(k, v) for k, (v, d) in sorted(merged.items()) if not d]
