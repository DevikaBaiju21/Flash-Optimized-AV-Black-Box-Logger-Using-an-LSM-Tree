"""
MEMBER 4: Live demo. Run:  python main.py
Walks through every feature faculty may ask to see.
"""
import shutil

from engine import LSMEngine

DIR = "demo_data"


def title(text):
    print("\n" + "=" * 8 + " " + text + " " + "=" * 8)


def main():
    shutil.rmtree(DIR, ignore_errors=True)

    title("1. Log sensor data (flush_threshold=5, so SSTables appear quickly)")
    db = LSMEngine(DIR, flush_threshold=5, compact_after=None)
    for t in range(1000, 1012):
        db.put("speed", t, 60 + (t - 1000) * 0.5)
    db.put("brake", 1005, 1)
    db.put("event", 1008, "lane_departure")
    db.put("gps", 1003, "12.9716N_77.5946E")
    print(db.stats())

    title("2. Point lookup (get)")
    print("speed @1003 ->", db.get("speed", 1003))
    print("speed @9999 ->", db.get("speed", 9999), "(missing key)")

    title("3. Overwrite the same key")
    db.put("speed", 1003, 99.9)
    print("speed @1003 ->", db.get("speed", 1003))

    title("4. Delete (tombstone) then get")
    db.delete("speed", 1004)
    print("speed @1004 ->", db.get("speed", 1004))

    title("5. Time-range query (incident window 1002..1007, sensor 'speed')")
    for key, value in db.range("speed", 1002, 1007):
        print("  ", key, value)
    print("empty range ->", db.range("speed", 5000, 6000))

    title("6. Compaction")
    print("SSTable files before:", db.stats()["sstable_files"])
    print("compaction result   :", db.compact())
    print("SSTable files after :", db.stats()["sstable_files"])
    print("speed @1003 still   ->", db.get("speed", 1003))
    print("speed @1004 still   ->", db.get("speed", 1004), "(deleted)")

    title("7. Crash and recover")
    db.put("event", 2000, "hard_brake")           # only in WAL + memtable, not flushed
    db.put("speed", 2001, 12.0)
    print("before crash, memtable holds", db.stats()["memtable_records"], "records")
    db = None                                      # simulate a crash: RAM is lost
    db = LSMEngine(DIR, flush_threshold=5, compact_after=None)   # restart -> WAL replay
    print("after restart, event @2000 ->", db.get("event", 2000))
    print("after restart, speed @2001 ->", db.get("speed", 2001))

    title("8. Write-amplification statistics")
    print(db.stats())
    print("(write_amplification = bytes physically written / bytes the user logged)")
    db.close()


if __name__ == "__main__":
    main()
