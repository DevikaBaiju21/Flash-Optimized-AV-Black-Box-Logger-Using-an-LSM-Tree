MEMBER 1: Record format and MemTable.

Record on disk (WAL and SSTable), one per line:   key|value|deleted
    key     = "<sensor_id>:<timestamp zero-padded to 10 digits>"
              e.g. "speed:0000001001"  (string order == time order per sensor)
    value   = sensor reading as text, e.g. "62.5"
    deleted = 1 for a tombstone (a delete marker), else 0

MemTable = in-memory buffer holding the newest writes.
  - Python dict {key: (value, deleted)}
  - put/get/delete: O(1) average
  - sorting is done once, at flush time: O(n log n)
"""

SEP = "|"
def make_key(sensor_id, timestamp):
    """Build the key used everywhere, e.g. ('speed', 1001) -> 'speed:0000001001'."""
    sensor_id = str(sensor_id)
    if not sensor_id or ":" in sensor_id or SEP in sensor_id or "\n" in sensor_id:
        raise ValueError("sensor_id must be non-empty and contain no ':' '|' or newline")
    if not isinstance(timestamp, int) or timestamp < 0 or timestamp >= 10 ** 10:
        raise ValueError("timestamp must be an integer in [0, 10^10)")
    return f"{sensor_id}:{timestamp:010d}"
def check_value(value):
    """Values are stored as text. The separator and newlines would break the file format."""
    value = str(value)
    if SEP in value or "\n" in value or "\r" in value:
        raise ValueError("value must not contain '|' or newline characters")
    return value

class MemTable:
    def __init__(self):
        self.data = {}  # key -> (value, deleted)

    def put(self, key, value):
        """Insert or overwrite a record."""
        self.data[key] = (value, False)

    def delete(self, key):
        """Delete = insert a tombstone. Nothing is erased; compaction removes it later."""
        self.data[key] = ("", True)

    def get(self, key):
        """Return (value, deleted) or None if this memtable has never seen the key."""
        return self.data.get(key)

    def size(self):
        return len(self.data)

    def clear(self):
        self.data.clear()
     def sorted_items(self):
        """All records as [(key, (value, deleted)), ...] sorted by key. Used by flush."""
        return sorted(self.data.items())

    def range(self, start, end):
        """Records with start <= key <= end, as {key: (value, deleted)}."""
        return {k: v for k, v in self.data.items() if start <= k <= end}


