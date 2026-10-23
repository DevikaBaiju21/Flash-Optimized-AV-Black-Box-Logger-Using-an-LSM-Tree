"""
MEMBER 4: Compaction.

Why: every flush adds another SSTable, so reads must search more files and old /
overwritten / deleted records waste space.

How: a K-WAY MERGE of all SSTables using a min-heap (heapq.merge).
  - Each file is already sorted, so merging is a single streaming pass.
  - If the same key appears in several files, the NEWEST file wins.
  - Tombstones are dropped (safe because we merge ALL files, so no older
    copy of the key survives anywhere).
  - The merged result is written as ONE new SSTable, then the old files are deleted.

Complexity: O(N log k)  (N = total records, k = number of files).

Limitation (mention in viva): a crash between writing the new file and deleting
the old ones could resurrect a deleted key. A real system fixes this with a
manifest file. Out of scope here.
"""
import heapq
import os


def _tagged(manager, path, age):
    """Yield (key, age, value, deleted); bigger age = newer file."""
    for key, value, deleted in manager.iter_file(path):
        yield key, age, value, deleted


def compact(manager):
    """Merge all SSTables into one. Returns a stats dict, or None if < 2 files."""
    files = manager.list_files()
    if len(files) < 2:
        return None

    streams = [_tagged(manager, p, age) for age, p in enumerate(files)]
    # Sort by key; for equal keys the NEWEST (largest age) comes first.
    merged = heapq.merge(*streams, key=lambda r: (r[0], -r[1]))

    out = []
    records_in = 0
    last_key = None
    for key, _age, value, deleted in merged:
        records_in += 1
        if key == last_key:
            continue                      # an older copy of a key we already handled
        last_key = key
        if not deleted:                   # drop tombstones
            out.append((key, value, False))

    new_number = manager.number_of(files[-1]) + 1
    if out:
        manager.write(out, number=new_number)
    for p in files:
        os.remove(p)

    return {
        "files_merged": len(files),
        "records_in": records_in,
        "records_out": len(out),
        "removed": records_in - len(out),
    }
