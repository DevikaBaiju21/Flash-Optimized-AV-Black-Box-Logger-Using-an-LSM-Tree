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
