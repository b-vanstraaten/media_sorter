import tempfile
import unittest
from pathlib import Path

from media_sorter.movelog import last_run, log_path, pop_last_run, record_run
from media_sorter.organizer import find_subtitles, prune_release_dirs

VIDEO_EXTS = {".mkv", ".mp4"}


class TestFindSubtitles(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        return path

    def test_same_stem_with_language_tag(self):
        video = self._touch("rel/Movie.2010.mkv")
        self._touch("rel/Movie.2010.en.srt")
        self._touch("rel/Movie.2010.srt")
        self._touch("rel/Other.srt")
        found = find_subtitles(video, VIDEO_EXTS)
        tails = sorted(tail for _, tail in found)
        self.assertEqual(tails, [".en.srt", ".srt"])

    def test_subs_folder_claimed_by_only_video(self):
        video = self._touch("rel/Movie.mkv")
        self._touch("rel/Subs/English.srt")
        found = find_subtitles(video, VIDEO_EXTS)
        self.assertEqual([tail for _, tail in found], [".English.srt"])

    def test_subs_folder_not_claimed_with_multiple_videos(self):
        video = self._touch("rel/Ep1.mkv")
        self._touch("rel/Ep2.mkv")
        self._touch("rel/Subs/English.srt")
        self.assertEqual(find_subtitles(video, VIDEO_EXTS), [])


class TestPruneReleaseDirs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        return path

    def test_junk_only_folder_removed(self):
        self._touch("Movie.Release/movie.nfo")
        self._touch("Movie.Release/screenshot.jpg")
        dirs, junk = prune_release_dirs(self.root)
        self.assertEqual((dirs, junk), (1, 2))
        self.assertFalse((self.root / "Movie.Release").exists())

    def test_folder_with_video_untouched(self):
        self._touch("Movie.Release/movie.nfo")
        video = self._touch("Movie.Release/movie.mkv")
        dirs, junk = prune_release_dirs(self.root)
        self.assertEqual((dirs, junk), (0, 0))
        self.assertTrue(video.exists())

    def test_nested_empty_dirs_removed(self):
        (self.root / "a/b/c").mkdir(parents=True)
        dirs, _ = prune_release_dirs(self.root)
        self.assertEqual(dirs, 3)


class TestMoveLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_and_pop(self):
        self.assertIsNone(last_run(self.root))
        record_run(self.root, [(Path("/a/x.mkv"), Path("/b/x.mkv"))])
        record_run(self.root, [(Path("/a/y.mkv"), Path("/b/y.mkv"))])

        run = last_run(self.root)
        self.assertEqual(run["moves"][0]["from"], "/a/y.mkv")

        popped = pop_last_run(self.root)
        self.assertEqual(popped["moves"][0]["to"], "/b/y.mkv")
        self.assertEqual(last_run(self.root)["moves"][0]["from"], "/a/x.mkv")

        pop_last_run(self.root)
        self.assertIsNone(last_run(self.root))
        self.assertFalse(log_path(self.root).exists())


if __name__ == "__main__":
    unittest.main()
