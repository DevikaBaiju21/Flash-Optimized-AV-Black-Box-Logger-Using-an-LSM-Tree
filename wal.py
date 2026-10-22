
import os


class WAL:
    def __init__(self, path, sync=True):
        self.path = path
        self.sync = sync            # True = force data to the physical disk on every append
        self.bytes_written = 0      # used for the write-amplification statistic
        self._f = open(path, "a", encoding="utf-8")

    
