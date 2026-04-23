import unittest
import os
import shutil
from pathlib import Path
from input.media_resolver import MediaResolver

class TestMediaResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path("test_media")
        cls.test_dir.mkdir(exist_ok=True)
        (cls.test_dir / "the_matrix.mp4").touch()
        (cls.test_dir / "the_matrix.srt").touch()
        (cls.test_dir / "pulp_fiction.mkv").touch()
        (cls.test_dir / "pulp_fiction.en.vtt").touch()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir)

    def test_resolve_exact_match(self):
        resolver = MediaResolver(media_dir=str(self.test_dir))
        result = resolver.resolve("the matrix")
        self.assertIsNotNone(result)
        self.assertEqual(result.media_path.name, "the_matrix.mp4")
        self.assertEqual(result.subtitle_path.name, "the_matrix.srt")

    def test_resolve_partial_match(self):
        resolver = MediaResolver(media_dir=str(self.test_dir))
        result = resolver.resolve("pulp")
        self.assertIsNotNone(result)
        self.assertEqual(result.media_path.name, "pulp_fiction.mkv")
        self.assertEqual(result.subtitle_path.name, "pulp_fiction.en.vtt")

    def test_resolve_no_match(self):
        resolver = MediaResolver(media_dir=str(self.test_dir))
        result = resolver.resolve("nonexistent movie")
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
