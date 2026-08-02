import tempfile
import unittest
from pathlib import Path
from unittest import mock
from io import StringIO

from marquee.cli import active_download_reason, reconcile, title_plausible, print_library_summary, console
from marquee.filename_parser import FilenameHints


class TestTitlePlausible(unittest.TestCase):
    def test_matching_titles(self):
        self.assertTrue(title_plausible("The Bear", "The Bear"))
        self.assertTrue(
            title_plausible("Daredevil - Born Again", "Daredevil Born Again")
        )

    def test_partial_overlap_is_enough(self):
        self.assertTrue(title_plausible("Daredevil - Born Again", "Daredevil"))

    def test_unrelated_titles_rejected(self):
        self.assertFalse(title_plausible("Daredevil - Born Again", "The Bear"))

    def test_no_guess_means_trust_model(self):
        self.assertTrue(title_plausible("Inception", None))
        self.assertTrue(title_plausible("Inception", ""))


class TestReconcile(unittest.TestCase):
    def _series_result(self, **overrides):
        result = {
            "type": "series",
            "title": "The Bear",
            "year": None,
            "season": 1,
            "episode": 1,
            "confidence": "high",
        }
        result.update(overrides)
        return result

    def test_regex_numbers_override_model(self):
        hints = FilenameHints(season=3, episodes=[2], guessed_title="The Bear")
        result = reconcile(self._series_result(season=1, episode=1), hints)
        self.assertEqual(result["season"], 3)
        self.assertEqual(result["episodes"], [2])

    def test_movie_with_episode_marker_demoted(self):
        hints = FilenameHints(season=1, episodes=[2], guessed_title="Show")
        result = reconcile(
            {"type": "movie", "title": "Show", "year": None,
             "season": None, "episode": None, "confidence": "high"},
            hints,
        )
        self.assertEqual(result["type"], "ambiguous")

    def test_implausible_series_title_falls_back_to_filename(self):
        # Season/episode are already regex-confirmed here, so an implausible
        # model title (e.g. it snapped to an unrelated known title) shouldn't
        # sink the whole file -- fall back to the filename's own title text.
        hints = FilenameHints(season=3, episodes=[2], guessed_title="The Bear")
        result = reconcile(
            self._series_result(title="Daredevil - Born Again"), hints
        )
        self.assertEqual(result["type"], "series")
        self.assertEqual(result["title"], "The Bear")

    def test_implausible_movie_title_demoted(self):
        hints = FilenameHints(year="2010", guessed_title="Inception")
        result = reconcile(
            {"type": "movie", "title": "The Matrix", "year": None,
             "season": None, "episode": None, "confidence": "high"},
            hints,
        )
        self.assertEqual(result["type"], "ambiguous")

    def test_movie_year_backfilled_from_hints(self):
        hints = FilenameHints(year="2010", guessed_title="Inception")
        result = reconcile(
            {"type": "movie", "title": "Inception", "year": None,
             "season": None, "episode": None, "confidence": "high"},
            hints,
        )
        self.assertEqual(result["year"], "2010")


class TestPrintLibrarySummary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.output_root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_library(self):
        with mock.patch.object(console, 'print') as mock_print:
            print_library_summary(self.output_root)
        # Should print exactly one message about no media found
        self.assertTrue(mock_print.called)

    def test_movies_only(self):
        movies_dir = self.output_root / "Movies" / "Inception (2010)"
        movies_dir.mkdir(parents=True)
        (movies_dir / "Inception (2010).mkv").write_text("x" * 1000)

        with mock.patch.object(console, 'print') as mock_print:
            print_library_summary(self.output_root)

        # Should call print for panel and table
        self.assertGreaterEqual(mock_print.call_count, 2)

    def test_series_only(self):
        series_dir = self.output_root / "Series" / "The Bear" / "Season 01"
        series_dir.mkdir(parents=True)
        (series_dir / "The Bear - S01E01.mkv").write_text("x" * 1000)

        with mock.patch.object(console, 'print') as mock_print:
            print_library_summary(self.output_root)

        # Should call print for panel and table
        self.assertGreaterEqual(mock_print.call_count, 2)

    def test_mixed_library(self):
        # Create a movie
        movies_dir = self.output_root / "Movies" / "Inception (2010)"
        movies_dir.mkdir(parents=True)
        (movies_dir / "Inception (2010).mkv").write_text("x" * 1000)

        # Create a series
        series_dir = self.output_root / "Series" / "The Bear" / "Season 01"
        series_dir.mkdir(parents=True)
        (series_dir / "The Bear - S01E01.mkv").write_text("x" * 1000)

        with mock.patch.object(console, 'print') as mock_print:
            print_library_summary(self.output_root)

        # Should call print for panel and both tables
        self.assertGreaterEqual(mock_print.call_count, 3)


class TestActiveDownloadReason(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "Movie.mkv"
        self.path.write_text("x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_partial_sibling_marker_flags_without_shelling_out(self):
        self.path.with_name(self.path.name + ".part").write_text("")
        with mock.patch("marquee.cli.subprocess.run") as run:
            reason = active_download_reason(self.path)
        run.assert_not_called()
        self.assertIn("still downloading", reason)

    def test_open_file_is_flagged(self):
        with mock.patch("marquee.cli.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            reason = active_download_reason(self.path)
        self.assertIn("currently open", reason)

    def test_closed_file_is_not_flagged(self):
        with mock.patch("marquee.cli.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=1)
            reason = active_download_reason(self.path)
        self.assertIsNone(reason)

    def test_missing_lsof_does_not_block(self):
        with mock.patch("marquee.cli.subprocess.run", side_effect=FileNotFoundError):
            reason = active_download_reason(self.path)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
