import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from media_sorter.organizer import (
    TitleRegistry,
    build_movie_dest,
    build_series_dest,
    episode_tag,
    has_room_for,
    move_file,
    movie_label,
    sanitize_name,
)


class TestSanitize(unittest.TestCase):
    def test_invalid_chars(self):
        self.assertEqual(sanitize_name('What: If...? <v2>'), "What If... v2")

    def test_reserved_names(self):
        self.assertEqual(sanitize_name("CON"), "_CON")

    def test_empty(self):
        self.assertEqual(sanitize_name("???"), "Untitled")


class TestTitleRegistry(unittest.TestCase):
    def test_exact_reuse(self):
        reg = TitleRegistry(["Daredevil - Born Again"])
        name, existing = reg.resolve("Daredevil - Born Again")
        self.assertTrue(existing)
        self.assertEqual(name, "Daredevil - Born Again")

    def test_punctuation_variant_snaps_to_existing(self):
        reg = TitleRegistry(["Daredevil - Born Again"])
        name, existing = reg.resolve("Daredevil.Born.Again")
        self.assertTrue(existing)
        self.assertEqual(name, "Daredevil - Born Again")

    def test_case_variant(self):
        reg = TitleRegistry(["The Bear"])
        name, existing = reg.resolve("the bear")
        self.assertTrue(existing)
        self.assertEqual(name, "The Bear")

    def test_new_title_added(self):
        reg = TitleRegistry(["The Bear"])
        name, existing = reg.resolve("Severance")
        self.assertFalse(existing)
        self.assertEqual(name, "Severance")
        # subsequent variant now matches it
        name2, existing2 = reg.resolve("severance")
        self.assertTrue(existing2)
        self.assertEqual(name2, "Severance")

    def test_distinct_titles_not_merged(self):
        reg = TitleRegistry(["The Office (US)"])
        name, existing = reg.resolve("The Office (UK)")
        self.assertFalse(existing)


class TestDestinations(unittest.TestCase):
    def test_movie_dest(self):
        dest = build_movie_dest(Path("/media"), movie_label("Inception", "2010"), ".mkv")
        self.assertEqual(
            dest, Path("/media/Movies/Inception (2010)/Inception (2010).mkv")
        )

    def test_movie_dest_no_year(self):
        dest = build_movie_dest(Path("/media"), movie_label("Inception", None), ".mp4")
        self.assertEqual(dest, Path("/media/Movies/Inception/Inception.mp4"))

    def test_series_dest(self):
        dest = build_series_dest(Path("/media"), "The Bear", 3, [2], ".mkv")
        self.assertEqual(
            dest,
            Path("/media/Series/The Bear/Season 03/The Bear - S03E02.mkv"),
        )

    def test_multi_episode_tag(self):
        self.assertEqual(episode_tag(1, [1, 2]), "S01E01-E02")
        self.assertEqual(episode_tag(10, [5]), "S10E05")


class TestMoveFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.src = self.root / "src" / "movie.mkv"
        self.src.parent.mkdir(parents=True)
        self.src.write_bytes(b"video-bytes")
        self.dest = self.root / "dest" / "Movies" / "movie.mkv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_same_filesystem_uses_rename(self):
        move_file(self.src, self.dest)
        self.assertFalse(self.src.exists())
        self.assertEqual(self.dest.read_bytes(), b"video-bytes")

    def test_cross_device_falls_back_to_verified_copy(self):
        # Force the rename fast path to fail, as it would across filesystems.
        with mock.patch("media_sorter.organizer.os.rename", side_effect=OSError):
            move_file(self.src, self.dest)
        self.assertFalse(self.src.exists())
        self.assertEqual(self.dest.read_bytes(), b"video-bytes")
        self.assertFalse(self.dest.with_name(self.dest.name + ".msorter-tmp").exists())

    def test_size_mismatch_is_rolled_back_and_source_kept(self):
        def truncated_copy(src, dst, *a, **k):
            Path(dst).write_bytes(b"short")

        with mock.patch("media_sorter.organizer.os.rename", side_effect=OSError), \
             mock.patch("media_sorter.organizer.shutil.copy2", side_effect=truncated_copy), \
             mock.patch("media_sorter.organizer.MOVE_RETRIES", 0), \
             mock.patch("media_sorter.organizer.time.sleep"):
            with self.assertRaises(OSError):
                move_file(self.src, self.dest)
        # Source untouched, no corrupt file left at dest, no leftover temp file.
        self.assertTrue(self.src.exists())
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.dest.with_name(self.dest.name + ".msorter-tmp").exists())

    def test_retry_after_partial_completion_skips_recopy(self):
        # Simulate a prior attempt that copied the file but died before
        # removing the source: dest already holds the full, correct file.
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(b"video-bytes")

        with mock.patch("media_sorter.organizer.os.rename", side_effect=OSError), \
             mock.patch("media_sorter.organizer.shutil.copy2") as copy2:
            move_file(self.src, self.dest)
        copy2.assert_not_called()
        self.assertFalse(self.src.exists())
        self.assertEqual(self.dest.read_bytes(), b"video-bytes")


class TestHasRoomFor(unittest.TestCase):
    def test_enough_space(self):
        usage = shutil.disk_usage(tempfile.gettempdir())
        with mock.patch("media_sorter.organizer.shutil.disk_usage", return_value=usage):
            self.assertTrue(has_room_for(Path(tempfile.gettempdir()) / "x.mkv", 10))

    def test_not_enough_space(self):
        fake_usage = type(shutil.disk_usage(tempfile.gettempdir()))(
            total=1000, used=999, free=1
        )
        with mock.patch("media_sorter.organizer.shutil.disk_usage", return_value=fake_usage):
            self.assertFalse(has_room_for(Path(tempfile.gettempdir()) / "x.mkv", 1_000_000))


if __name__ == "__main__":
    unittest.main()
