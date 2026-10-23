
import os
import shutil
import tempfile
import unittest

from engine import LSMEngine
from memtable import make_key


class LSMTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def db(self, **kw):
        kw.setdefault("flush_threshold", 3)
        kw.setdefault("compact_after", None)
        kw.setdefault("sync", False)
        return LSMEngine(self.dir, **kw)

    def test_missing_key(self):
        db = self.db()
        self.assertIsNone(db.get("speed", 1))

    def test_put_get_memtable_and_sstable(self):
        db = self.db()
        for t in range(1, 8):               # forces several flushes
            db.put("speed", t, t * 10)
        self.assertEqual(db.get("speed", 1), "10")   # in an SSTable
        self.assertEqual(db.get("speed", 7), "70")   # in the memtable

    def test_overwrite_newest_wins(self):
        db = self.db()
        db.put("speed", 1, 10)
        db.flush()
        db.put("speed", 1, 20)
        db.flush()
        db.put("speed", 1, 30)               # still in memtable
        self.assertEqual(db.get("speed", 1), "30")
        db.flush()
        self.assertEqual(db.get("speed", 1), "30")

    def test_delete_then_get(self):
        db = self.db()
        db.put("speed", 1, 10)
        db.flush()
        db.delete("speed", 1)                # tombstone in memtable hides the SSTable value
        self.assertIsNone(db.get("speed", 1))
        db.flush()                           # tombstone now in a newer SSTable
        self.assertIsNone(db.get("speed", 1))

    def test_range_query(self):
        db = self.db()
        for t in range(1, 11):
            db.put("speed", t, t)
        db.put("brake", 5, 1)
        db.delete("speed", 4)
        result = db.range("speed", 3, 6)
        self.assertEqual([k for k, _ in result],
                         [make_key("speed", t) for t in (3, 5, 6)])
        self.assertEqual(db.range("speed", 100, 200), [])      # empty range

    def test_crash_recovery_from_wal(self):
        db = self.db(flush_threshold=100)    # nothing gets flushed
        db.put("event", 1, "crash")
        db.put("speed", 2, 55)
        db.delete("speed", 2)
        del db                               # "crash": memory lost, WAL stays on disk
        db2 = self.db(flush_threshold=100)
        self.assertEqual(db2.get("event", 1), "crash")
        self.assertIsNone(db2.get("speed", 2))               # delete was recovered too

    def test_torn_wal_line_is_ignored(self):
        db = self.db(flush_threshold=100)
        db.put("speed", 1, 10)
        db.close()
        with open(os.path.join(self.dir, "wal.log"), "a") as f:
            f.write("speed:0000000002|7")    # half-written line, no newline
        db2 = self.db(flush_threshold=100)
        self.assertEqual(db2.get("speed", 1), "10")
        self.assertIsNone(db2.get("speed", 2))

    def test_compaction_merges_and_drops_tombstones(self):
        db = self.db()
        db.put("speed", 1, 10)
        db.put("speed", 2, 20)
        db.flush()
        db.put("speed", 1, 11)               # overwrite
        db.delete("speed", 2)                # delete
        db.flush()
        db.put("speed", 3, 30)
        db.flush()
        self.assertEqual(len(db.sstables.list_files()), 3)
        stats = db.compact()
        self.assertEqual(len(db.sstables.list_files()), 1)
        self.assertEqual(stats["records_out"], 2)
        self.assertEqual(db.get("speed", 1), "11")
        self.assertIsNone(db.get("speed", 2))
        self.assertEqual(db.get("speed", 3), "30")

    def test_compaction_with_fewer_than_two_files(self):
        db = self.db()
        self.assertIsNone(db.compact())

    def test_auto_compaction(self):
        db = self.db(flush_threshold=2, compact_after=3)
        for t in range(1, 20):
            db.put("speed", t, t)
        self.assertLess(len(db.sstables.list_files()), 3)
        self.assertEqual(db.get("speed", 1), "1")
        self.assertEqual(db.get("speed", 19), "19")

    def test_invalid_input(self):
        db = self.db()
        with self.assertRaises(ValueError):
            db.put("sp:eed", 1, 1)
        with self.assertRaises(ValueError):
            db.put("speed", -5, 1)
        with self.assertRaises(ValueError):
            db.put("speed", 1, "a|b")


if __name__ == "__main__":
    unittest.main()
