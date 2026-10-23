import os

from memtable import MemTable, check_value, make_key
from sstable import SSTableManager
from wal import WAL


class LSMEngine:
    def __init__(self, directory="data", flush_threshold=100, compact_after=4, sync=True):
        os.makedirs(directory, exist_ok=True)
        self.flush_threshold = flush_threshold
        self.compact_after = compact_after
        self.memtable = MemTable()
        self.sstables = SSTableManager(directory)
        self.wal = WAL(os.path.join(directory, "wal.log"), sync=sync)
        self.logical_bytes = 0          # bytes the user asked us to store
        self._recover()

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

    def flush(self):
        """Memtable -> new SSTable, then clear memtable and WAL (in this order!)."""
        path = self.sstables.flush(self.memtable)
        if path is None:
            return None
        self.memtable.clear()
        self.wal.reset()
        return path
    

    def _maybe_flush(self):
        if self.memtable.size() >= self.flush_threshold:
            self.flush()

    def _recover(self):
        for key, value, deleted in self.wal.replay():
            if deleted:
                self.memtable.delete(key)
            else:
                self.memtable.put(key, value)
        def get(self, sensor_id, timestamp):
        return self.sstables.get(make_key(sensor_id, timestamp), self.memtable)

    def range(self, sensor_id, t_start, t_end):
        """All readings of one sensor with t_start <= timestamp <= t_end."""
        return self.sstables.range(make_key(sensor_id, t_start),
                                   make_key(sensor_id, t_end), self.memtable)
