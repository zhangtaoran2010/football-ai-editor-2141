import json
import tempfile
import unittest
from pathlib import Path

from football_ai_editor.media import delivery_video_profile
from football_ai_editor.pipeline import (
    build_plan,
    merge_candidate_signals,
    merge_overlapping_clips,
)
from football_ai_editor.review import boundary_sample_times, timeline_sample_times


class PipelineTests(unittest.TestCase):
    def test_merge_candidate_signals_combines_nearby_audio_and_scene(self):
        merged = merge_candidate_signals([10.0], [(11.5, -8.0)], merge_distance=3.0)
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0].scene)
        self.assertEqual(merged[0].audio_rms, -8.0)

    def test_merge_overlapping_clips(self):
        clips = [
            {"start": 10.0, "end": 20.0, "importance": 6, "event_ids": ["a"]},
            {"start": 19.5, "end": 25.0, "importance": 9, "event_ids": ["b"]},
            {"start": 40.0, "end": 50.0, "importance": 7, "event_ids": ["c"]},
        ]
        merged = merge_overlapping_clips(clips)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["start"], 10.0)
        self.assertEqual(merged[0]["end"], 25.0)
        self.assertEqual(merged[0]["importance"], 9)
        self.assertEqual(merged[0]["event_ids"], ["a", "b"])

    def test_build_plan_respects_importance_and_chronology(self):
        events = {
            "events": [
                {"id": "late", "start": 50, "end": 60, "importance": 9},
                {"id": "low", "start": 20, "end": 30, "importance": 3},
                {"id": "early", "start": 5, "end": 15, "importance": 8},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events_path = tmp_path / "events.json"
            plan_path = tmp_path / "plan.json"
            events_path.write_text(json.dumps(events), encoding="utf-8")

            build_plan(events_path, plan_path, min_importance=5)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [clip["event_ids"][0] for clip in plan["clips"]],
                ["early", "late"],
            )

    def test_timeline_sample_times_are_bounded_and_cover_edges(self):
        values = timeline_sample_times(10.0, 28.0, max_frames=8)
        self.assertEqual(len(values), 8)
        self.assertAlmostEqual(values[0], 10.0)
        self.assertAlmostEqual(values[-1], 28.0)

    def test_delivery_profile_caps_high_res_portrait_at_1080(self):
        profile = delivery_video_profile(2160, 3840, 60.0)
        self.assertEqual(profile["video_filter"], "scale=1080:-2")
        self.assertEqual(profile["bitrate"], "10M")
        self.assertEqual(profile["target_width"], 1080)
        self.assertEqual(profile["target_height"], 1920)

    def test_delivery_profile_keeps_native_1080_portrait(self):
        profile = delivery_video_profile(1080, 1920, 60.0)
        self.assertIsNone(profile["video_filter"])
        self.assertEqual(profile["bitrate"], "10M")

    def test_delivery_profile_does_not_upscale_720_portrait(self):
        profile = delivery_video_profile(720, 1280, 60.0)
        self.assertIsNone(profile["video_filter"])
        self.assertEqual(profile["target_width"], 720)
        self.assertEqual(profile["target_height"], 1280)

    def test_boundary_sample_times_clamp_to_video(self):
        start_values = boundary_sample_times(0.5, 100.0)
        self.assertEqual(start_values[0], 0.0)
        self.assertIn(0.5, start_values)

        end_values = boundary_sample_times(99.5, 100.0)
        self.assertLessEqual(end_values[-1], 99.95)



if __name__ == "__main__":
    unittest.main()
