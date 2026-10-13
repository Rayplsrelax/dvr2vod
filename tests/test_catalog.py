import unittest

from dvr2vod.catalog import (
    MODE_FLAT,
    MODE_SERIES,
    build_entries,
    entry_url,
    render_m3u,
    split_show_episode,
)


class SplitShowEpisode(unittest.TestCase):
    def test_sxxeyy_marker(self):
        show, ep = split_show_episode("Chelsea - S01E02 - The Pitch")
        self.assertEqual(show, "Chelsea")
        self.assertEqual(ep, "S01E02")

    def test_sxxeyy_without_separator(self):
        show, ep = split_show_episode("NovaS01E12rivers")
        self.assertEqual(show, "Nova")
        self.assertEqual(ep, "S01E12")

    def test_single_digit_seasons_normalized(self):
        show, ep = split_show_episode("Show - s1e2")
        self.assertEqual(show, "Show")
        self.assertEqual(ep, "S01E02")

    def test_date_stamp(self):
        show, ep = split_show_episode("Evening News - 2026.10.12")
        self.assertEqual(show, "Evening News")
        self.assertEqual(ep, "2026-10-12")

    def test_separator_split(self):
        show, ep = split_show_episode("Frontline | The Untold Story")
        self.assertEqual(show, "Frontline")
        self.assertEqual(ep, "The Untold Story")

    def test_colon_split(self):
        show, ep = split_show_episode("Planet Wild: Deep Ocean")
        self.assertEqual(show, "Planet Wild")
        self.assertEqual(ep, "Deep Ocean")

    def test_fallback_is_whole_title(self):
        show, ep = split_show_episode("Just A Movie")
        self.assertEqual(show, "Just A Movie")
        self.assertEqual(ep, "")

    def test_empty_title_falls_into_shared_bucket(self):
        show, ep = split_show_episode("   ")
        self.assertEqual(show, "Recordings")
        self.assertEqual(ep, "")


class BuildEntries(unittest.TestCase):
    def test_newest_first_with_untimestamped_last(self):
        rows = [
            {"id": 2, "title": "Show B - S01E02", "started_iso": "2026-10-11T20:00:00+00:00"},
            {"id": 1, "title": "Show B - S01E01", "started_iso": "2026-10-10T20:00:00+00:00"},
            {"id": 3, "title": "Old Thing", "started_iso": None},
        ]
        entries = build_entries(rows)
        self.assertEqual([e["id"] for e in entries], [2, 1, 3])

    def test_stable_order_for_same_timestamp(self):
        rows = [
            {"id": 9, "title": "A", "started_iso": "2026-10-10T20:00:00+00:00"},
            {"id": 8, "title": "B", "started_iso": "2026-10-10T20:00:00+00:00"},
        ]
        self.assertEqual([e["id"] for e in build_entries(rows)], [9, 8])

    def test_blank_title_gets_placeholder(self):
        entries = build_entries([{"id": 5, "title": "", "started_iso": None}])
        self.assertEqual(entries[0]["title"], "Untitled recording")
        self.assertEqual(entries[0]["show"], "Recordings")

    def test_whitespace_and_quotes_cleaned(self):
        entries = build_entries([{"id": 5, "title": '  "Show  X"  ', "started_iso": None}])
        self.assertEqual(entries[0]["title"], "Show X")


class EntryUrl(unittest.TestCase):
    def test_url_shape_with_token(self):
        url = entry_url({"id": 42}, "http://box:9191/", "sec ret")
        self.assertEqual(url, "http://box:9191/api/channels/recordings/42/file/?token=sec%20ret")

    def test_url_without_token_has_no_query(self):
        url = entry_url({"id": 42}, "http://box:9191", "")
        self.assertEqual(url, "http://box:9191/api/channels/recordings/42/file/")

    def test_empty_base_yields_relative(self):
        url = entry_url({"id": 1}, "", "t")
        self.assertEqual(url, "/api/channels/recordings/1/file/?token=t")


class RenderM3u(unittest.TestCase):
    ENTRIES = [
        {"id": 2, "show": "Show B", "episode": "S01E02", "title": "Show B - S01E02",
         "started_iso": "2026-10-11T20:00:00+00:00", "duration_s": 3600, "logo": "http://l/2.png"},
        {"id": 1, "show": "Show A", "episode": "", "title": "Show A Movie",
         "started_iso": "2026-10-10T20:00:00+00:00", "duration_s": 7200, "logo": ""},
    ]

    def test_series_mode_groups_by_show(self):
        text = render_m3u(self.ENTRIES, "http://box:9191", "t", mode=MODE_SERIES)
        self.assertIn('group-title="Show B"', text)
        self.assertIn('group-title="Show A"', text)
        self.assertIn("Show B - S01E02 2026-10-11 20:00", text)

    def test_date_stamped_title_does_not_repeat_the_date(self):
        entries = [{"id": 7, "show": "Sunday Night Football", "episode": "2026-10-11",
                    "title": "Sunday Night Football - 2026.10.11",
                    "started_iso": "2026-10-11T20:20:00-04:00", "duration_s": 12600, "logo": ""}]
        text = render_m3u(entries, "http://b", "t")
        self.assertIn(",Sunday Night Football - 2026-10-11\n", text)
        self.assertNotIn("2026-10-11 2026-10-11", text)

    def test_flat_mode_uses_configured_group(self):
        text = render_m3u(self.ENTRIES, "http://box:9191", "t", mode=MODE_FLAT, group_title="My DVR")
        self.assertEqual(text.count('group-title="My DVR"'), 2)
        self.assertNotIn('group-title="Show B"', text)

    def test_header_and_url_lines(self):
        text = render_m3u(self.ENTRIES, "http://box:9191", "t")
        lines = text.splitlines()
        self.assertEqual(lines[0], "#EXTM3U")
        self.assertIn("api/channels/recordings/2/file/?token=t", lines[2])
        self.assertIn("api/channels/recordings/1/file/?token=t", lines[4])

    def test_quotes_in_titles_do_not_break_extinf(self):
        entries = [{"id": 1, "show": 'Weird "Show"', "episode": "", "title": 'The "Special" One',
                    "started_iso": None, "duration_s": None, "logo": ""}]
        text = render_m3u(entries, "http://b", "t")
        self.assertNotIn('"Special"', text)
        self.assertIn("'Special'", text)

    def test_ends_with_newline(self):
        self.assertTrue(render_m3u(self.ENTRIES, "http://b", "t").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
