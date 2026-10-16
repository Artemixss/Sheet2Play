from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge
from homr465_profile import MODEL_HASHES, PROFILE_PATH, ProfileError, asset_path, load_profile
from musicxml_normalizer import NormalizedScore, RawMusicNote, TempoChange


class Homr465ProfileTests(unittest.TestCase):
    def test_pinned_manifest_contract(self):
        profile, identity = load_profile(verify_assets=False)
        self.assertEqual(len(identity), 64)
        self.assertEqual(profile["processing"]["title_detection"], False)
        self.assertEqual({name: row["sha256"] for name, row in profile["models"].items()}, MODEL_HASHES)

    def test_rejects_changed_identity_settings_and_model(self):
        original = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        mutations = [("source_revision", "wrong"), ("provider", "CPUExecutionProvider"), ("threads", 1)]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            for key, value in mutations:
                profile = copy.deepcopy(original)
                profile[key] = value
                path.write_text(json.dumps(profile), encoding="utf-8")
                with self.subTest(key=key), self.assertRaises(ProfileError):
                    load_profile(path, verify_assets=False)
            profile = copy.deepcopy(original)
            profile["models"]["encoder"]["sha256"] = "0" * 64
            path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaises(ProfileError):
                load_profile(path, verify_assets=False)

    def test_missing_assets_fail_and_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "profile.json"
            path.write_bytes(PROFILE_PATH.read_bytes())
            with self.assertRaises(ProfileError):
                load_profile(path)
            with self.assertRaises(ProfileError):
                asset_path(root, "../outside.onnx")

    def test_bridge_dispatch_preserves_schema_and_adds_candidate_identity(self):
        score = NormalizedScore(
            notes=(RawMusicNote(pitch="C4", midi_pitch=60, start_beat=0, duration_beats=1,
                               part_index=0, staff_index=0, voice_identifier="1"),),
            tempo_changes=(TempoChange(0, 120),), staff_count=1, part_count=1, total_beats=1)
        profile, identity = load_profile(verify_assets=False)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "score.png"
            source.write_bytes(b"image")
            output = io.StringIO()
            with mock.patch("homr465_profile.load_profile", return_value=(profile, identity)), \
                 mock.patch.object(bridge, "run_homr_engine", return_value=bridge.EngineOutput(score, 1, 1)) as run, \
                 mock.patch("sys.stdout", output):
                self.assertEqual(bridge.main([str(source), "--engine", "homr465"]), 0)
            run.assert_called_once_with(source.resolve(), "homr465")
            result = json.loads(output.getvalue())
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(result["engine"], "homr465")
            self.assertEqual(result["model_revision"], profile["model_revision"])
            self.assertEqual(result["runtime_profile_sha256"], identity)
            self.assertEqual(result["notes"][0]["duration_seconds"], 0.5)

    def test_legacy_result_shape_omits_candidate_fields(self):
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            bridge.emit_json(bridge.OmrResult(2, "homr", bridge.HOMR_ENGINE_REVISION, (), ()))
        self.assertNotIn("model_revision", json.loads(output.getvalue()))
        self.assertNotIn("runtime_profile_sha256", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
