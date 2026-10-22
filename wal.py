
import os


class WAL:
    def __init__(self, path, sync=True):
        self.path = path
        self.sync = sync            # True = force data to the physical disk on every append
        self.bytes_written = 0      # used for the write-amplification statistic
        self._f = open(path, "a", encoding="utf-8")
        def append(self, key, value, deleted):
        line = f"{key}|{value}|{1 if deleted else 0}\n"
        self._f.write(line)
        self._f.flush()
        if self.sync:
            os.fsync(self._f.fileno())
        self.bytes_written += len(line.encode("utf-8"))

    def replay(self):
        """Return all intact records as a list of (key, value, deleted).

        A crash can leave a half-written last line. Such a line has no trailing
        newline or the wrong number of fields, so we skip it instead of crashing.
        """
        records = []
        if not os.path.exists(self.path):
            return records
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.endswith("\n"):
                    continue                      # torn (incomplete) last line
                parts = line.rstrip("\n").split("|")
                if len(parts) != 3 or parts[2] not in ("0", "1"):
                    continue                      # corrupted line
                records.append((parts[0], parts[1], parts[2] == "1"))
        return records
        def reset(self):
        """Empty the log. Only call this after the SSTable flush succeeded."""
        self._f.close()
        open(self.path, "w", encoding="utf-8").close()
        self._f = open(self.path, "a", encoding="utf-8")

    def close(self):
        if not self._f.closed:
            self._f.close()


    


    
