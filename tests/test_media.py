import unittest

from services.media import MediaProcessor


class MediaProcessorTests(unittest.TestCase):
    def test_parse_timecode_line(self):
        result = MediaProcessor.parse_timecode_line(
            "00:01:02,500 --> 00:01:05,250"
        )
        self.assertEqual(result.start_seconds, 62.5)
        self.assertEqual(result.end_seconds, 65.25)

    def test_evenly_spaced_timestamps(self):
        timestamps = MediaProcessor.evenly_spaced_timestamps(60.0, 5)
        self.assertEqual(timestamps, [10.0, 20.0, 30.0, 40.0, 50.0])

    def test_absolute_interval_timestamps_left_closed_right_open(self):
        timestamps = MediaProcessor.absolute_interval_timestamps(
            start_seconds=61.0,
            end_seconds=180.0,
            interval_seconds=60.0,
            include_start=True,
            include_end=False,
        )
        self.assertEqual(timestamps, [61.0, 120.0])

    def test_absolute_interval_timestamps_last_chunk_can_include_end(self):
        timestamps = MediaProcessor.absolute_interval_timestamps(
            start_seconds=120.0,
            end_seconds=180.0,
            interval_seconds=60.0,
            include_start=True,
            include_end=True,
        )
        self.assertEqual(timestamps, [120.0, 180.0])


if __name__ == "__main__":
    unittest.main()
