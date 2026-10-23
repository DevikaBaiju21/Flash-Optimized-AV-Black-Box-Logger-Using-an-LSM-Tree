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
