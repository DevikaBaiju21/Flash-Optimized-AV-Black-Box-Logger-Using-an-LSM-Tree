"""
Engine: 

WRITE PATH:  put -> WAL append -> MemTable -> (full?) flush to SSTable -> reset WAL
READ PATH :  MemTable -> SSTables newest to oldest
RECOVERY  :  on start, replay the WAL into a fresh MemTable
"""
import os

from compaction import compact
from memtable import MemTable, check_value, make_key
from sstable import SSTableManager
from wal import WAL


class LSMEngine:
    def __init__(self, directory="data", flush_threshold=100, compact_after=4, sync=True):
        """
        flush_threshold : flush the memtable once it holds this many records
        compact_after   : auto-compact when this many SSTables exist (None = never)
        sync            : fsync the WAL on every write (safest, slower)
        """
        os.makedirs(directory, exist_ok=True)
        self.flush_threshold = flush_threshold
        self.compact_after = compact_after
        self.memtable = MemTable()
        self.sstables = SSTableManager(directory)
        self.wal = WAL(os.path.join(directory, "wal.log"), sync=sync)
        self.logical_bytes = 0          # bytes the user asked us to store
        self._recover()

    # ---------- recovery ----------
    def _recover(self):
        for key, value, deleted in self.wal.replay():
            if deleted:
                self.memtable.delete(key)
            else:
                self.memtable.put(key, value)

    # ---------- writes ----------
    def put(self, sensor_id, timestamp, value):
        key = make_key(sensor_id, timestamp)
        value = check_value(value)
        self.wal.append(key, value, False)          # 1. durable log first
        self.memtable.put(key, value)               # 2. then memory
        self.logical_bytes += len(key) + len(value)
        self._maybe_flush()

    def delete(self, sensor_id, timestamp):
        key = make_key(sensor_id, timestamp)
        self.wal.append(key, "", True)
        self.memtable.delete(key)
        self.logical_bytes += len(key)
        self._maybe_flush()

    def _maybe_flush(self):
        if self.memtable.size() >= self.flush_threshold:
            self.flush()

    def flush(self):
        """Memtable -> new SSTable, then clear memtable and WAL (in this order!)."""
        path = self.sstables.flush(self.memtable)
        if path is None:
            return None
        self.memtable.clear()
        self.wal.reset()
        if self.compact_after and len(self.sstables.list_files()) >= self.compact_after:
            self.compact()
        return path

    def compact(self):
        return compact(self.sstables)

    # ---------- reads ----------
    def get(self, sensor_id, timestamp):
        return self.sstables.get(make_key(sensor_id, timestamp), self.memtable)

    def range(self, sensor_id, t_start, t_end):
        """All readings of one sensor with t_start <= timestamp <= t_end."""
        return self.sstables.range(make_key(sensor_id, t_start),
                                   make_key(sensor_id, t_end), self.memtable)

    # ---------- statistics ----------
    def stats(self):
        physical = self.wal.bytes_written + self.sstables.bytes_written
        return {
            "memtable_records": self.memtable.size(),
            "sstable_files": len(self.sstables.list_files()),
            "logical_bytes": self.logical_bytes,
            "wal_bytes": self.wal.bytes_written,
            "sstable_bytes": self.sstables.bytes_written,
            "write_amplification": round(physical / self.logical_bytes, 2)
            if self.logical_bytes else 0,
        }

    def close(self):
        self.wal.close()
