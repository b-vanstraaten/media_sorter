import unittest
from pathlib import Path

from marquee.filename_parser import (
    clean_title,
    extract_year,
    parse_filename,
    parse_season_episode,
)


class TestSeasonEpisode(unittest.TestCase):
    def test_standard_sxxeyy(self):
        season, episodes, pos = parse_season_episode("Daredevil.Born.Again.S02E05.1080p")
        self.assertEqual(season, 2)
        self.assertEqual(episodes, [5])
        self.assertGreater(pos, 0)

    def test_lowercase_and_single_digits(self):
        season, episodes, _ = parse_season_episode("show s1e9 hdtv")
        self.assertEqual((season, episodes), (1, [9]))

    def test_multi_episode(self):
        season, episodes, _ = parse_season_episode("Show.S01E01E02.mkv")
        self.assertEqual((season, episodes), (1, [1, 2]))
        season, episodes, _ = parse_season_episode("Show.S01E03-E04")
        self.assertEqual((season, episodes), (1, [3, 4]))

    def test_x_format(self):
        season, episodes, _ = parse_season_episode("Show.Name.4x08.HDTV")
        self.assertEqual((season, episodes), (4, [8]))

    def test_no_match(self):
        season, episodes, pos = parse_season_episode("Inception.2010.1080p")
        self.assertIsNone(season)
        self.assertEqual(episodes, [])
        self.assertIsNone(pos)

    def test_x_format_not_fooled_by_resolution(self):
        # 1080x720 style strings must not parse as season 8 episode 0 etc.
        season, _, _ = parse_season_episode("Movie.2010.1920x1080.mkv")
        self.assertIsNone(season)


class TestYear(unittest.TestCase):
    def test_plain_year(self):
        self.assertEqual(extract_year("Inception.2010.1080p.x264"), "2010")

    def test_resolution_not_a_year(self):
        self.assertIsNone(extract_year("Some.Show.2160p.HDR"))

    def test_bracketed(self):
        self.assertEqual(extract_year("Movie (1994) [1080p]"), "1994")


class TestCleanTitle(unittest.TestCase):
    def test_strips_noise(self):
        self.assertEqual(
            clean_title("Inception.2010.1080p.BluRay.x264.YIFY"), "Inception"
        )

    def test_strips_brackets(self):
        self.assertEqual(clean_title("Movie.Name.[RARBG].720p"), "Movie Name")

    def test_keeps_hyphenated_names(self):
        self.assertEqual(
            clean_title("Daredevil.Born.Again"), "Daredevil Born Again"
        )


class TestParseFilename(unittest.TestCase):
    def test_series_file(self):
        hints = parse_filename(
            Path("/dl/Daredevil.Born.Again.S02E05.1080p.WEB-DL/episode.mkv")
        )
        self.assertEqual(hints.season, 2)
        self.assertEqual(hints.episodes, [5])
        self.assertEqual(hints.guessed_title, "Daredevil Born Again")

    def test_movie_file(self):
        hints = parse_filename(Path("/dl/Inception.2010.1080p.BluRay.mkv"))
        self.assertIsNone(hints.season)
        self.assertEqual(hints.year, "2010")
        self.assertEqual(hints.guessed_title, "Inception")

    def test_sample_detection(self):
        self.assertTrue(parse_filename(Path("/dl/movie/sample.mkv")).is_sample)
        self.assertTrue(parse_filename(Path("/dl/movie/Samples/x.mkv")).is_sample)
        self.assertTrue(
            parse_filename(Path("/dl/Movie.2020.sample.mkv")).is_sample
        )
        self.assertFalse(
            parse_filename(Path("/dl/The.Sampler.2020.mkv")).is_sample
        )


if __name__ == "__main__":
    unittest.main()
