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

    def put(self, sensor_id, timestamp, value):
        key = make_key(sensor_id, timestamp)
        value = check_value(value)
        self.wal.append(key, value, False)          # 1. durable log first
        self.memtable.put(key, value)               # 2. then memory
        self.logical_bytes += len(key) + len(value)
        
    def delete(self, sensor_id, timestamp):
        key = make_key(sensor_id, timestamp)
        self.wal.append(key, "", True)
        self.memtable.delete(key)
        self.logical_bytes += len(key)
