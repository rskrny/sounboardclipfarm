import unittest
import os
from pathlib import Path
from matching.quote_matcher import QuoteMatcher

class TestQuoteMatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srt_path = "test.srt"
        with open(cls.srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n2\n00:00:05,000 --> 00:00:08,000\nThis is a test subtitle\n\n3\n00:00:10,000 --> 00:00:12,000\nMulti-line\nquote spans here")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.srt_path):
            os.remove(cls.srt_path)

    def test_find_match_exact(self):
        matcher = QuoteMatcher(self.srt_path)
        match = matcher.find_match("Hello world")
        self.assertIsNotNone(match)
        self.assertEqual(match.text, "Hello world")
        self.assertEqual(match.start_time_ms, 1000)

    def test_find_match_fuzzy(self):
        matcher = QuoteMatcher(self.srt_path)
        match = matcher.find_match("hello wrld")
        self.assertIsNotNone(match)
        self.assertTrue(match.confidence > 80)

    def test_find_multi_block_match(self):
        matcher = QuoteMatcher(self.srt_path)
        # Match across block 1 and 2
        match = matcher.find_multi_block_match("Hello world this is a test")
        self.assertIsNotNone(match)
        self.assertEqual(match.start_time_ms, 1000)
        self.assertEqual(match.end_time_ms, 8000)

if __name__ == "__main__":
    unittest.main()
