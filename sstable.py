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

_NAME = re.compile(r"^sst_(\d+)\.txt$")

class SSTableManager:
    def __init__(self, directory):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self.bytes_written = 0      

    def path_of(self, number):
        return os.path.join(self.dir, f"sst_{number}.txt")

    def list_files(self):
        numbered = []
        for name in os.listdir(self.dir):
            m = _NAME.match(name)
            if m:
                numbered.append((int(m.group(1)), os.path.join(self.dir, name)))
        numbered.sort()
        return [p for _, p in numbered]

    def number_of(self, path):
        return int(_NAME.match(os.path.basename(path)).group(1))

    def next_number(self):
        files = self.list_files()
        return 1 if not files else self.number_of(files[-1]) + 1
    
    def write(self, records, number=None):
        if number is None:
            number = self.next_number()
        final_path = self.path_of(number)
        tmp_path = final_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            for key, value, deleted in records:
                line = f"{key}|{value}|{1 if deleted else 0}\n"
                f.write(line)
                self.bytes_written += len(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
        return final_path

    def flush(self, memtable):
        if memtable.size() == 0:
            return None
        records = [(k, v, d) for k, (v, d) in memtable.sorted_items()]
        return self.write(records)
    
    def iter_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("|")
                if len(parts) == 3:
                    yield parts[0], parts[1], parts[2] == "1"

    def load(self, path):
        return list(self.iter_file(path))

    def get_from_file(self, path, key):
        records = self.load(path)
        keys = [r[0] for r in records]
        i = bisect.bisect_left(keys, key)
        if i < len(keys) and keys[i] == key:
            return records[i]
        return None

    def get(self, key, memtable):
        hit = memtable.get(key)
        if hit is not None:
            value, deleted = hit
            return None if deleted else value
        for path in reversed(self.list_files()):          
            rec = get_from_file(path, key)
            if rec is not None:
                return None if rec[2] else rec[1]          
        return None
    def range(self, start, end, memtable):
        merged = {}
        for path in self.list_files():                     
            records = self.load(path)
            keys = [r[0] for r in records]
            i = bisect.bisect_left(keys, start)            
            while i < len(records) and records[i][0] <= end:
                key, value, deleted = records[i]
                merged[key] = (value, deleted)             
                i += 1
        for key, (value, deleted) in memtable.range(start, end).items():
            merged[key] = (value, deleted)                 
        return [(k, v) for k, (v, d) in sorted(merged.items()) if not d]
