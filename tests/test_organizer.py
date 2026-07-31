import unittest
from pathlib import Path

from media_sorter.organizer import (
    TitleRegistry,
    build_movie_dest,
    build_series_dest,
    episode_tag,
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


if __name__ == "__main__":
    unittest.main()
