import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from football_ai_editor.tts import (
    MiniMaxSettings,
    build_payload,
    load_dotenv,
    settings_from_env,
    synthesize_to_file,
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MiniMaxTtsTests(unittest.TestCase):
    def test_build_payload_uses_one_continuous_request(self):
        settings = MiniMaxSettings(api_key="secret")
        payload = build_payload("梅西突然加速，随后完成射门。", settings)
        self.assertEqual(payload["model"], "speech-2.8-hd")
        self.assertEqual(payload["voice_setting"]["voice_id"], "Chinese (Mandarin)_Straightforward_Boy")
        self.assertEqual(payload["voice_setting"]["speed"], 1.18)
        self.assertEqual(payload["voice_setting"]["emotion"], "happy")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["output_format"], "hex")
        self.assertEqual(payload["language_boost"], "Chinese")

    def test_load_dotenv_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local-config"
            path.write_text("MINIMAX_API_KEY=file-key\nMINIMAX_VOICE_ID=test-voice\n", encoding="utf-8")
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "existing-key"}, clear=False):
                load_dotenv(path)
                self.assertEqual(os.environ["MINIMAX_API_KEY"], "existing-key")
                self.assertEqual(os.environ["MINIMAX_VOICE_ID"], "test-voice")

    def test_settings_require_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("football_ai_editor.tts.Path.is_file", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "MINIMAX_API_KEY"):
                    settings_from_env(require_api_key=True)

    def test_synthesize_decodes_hex_and_writes_audio(self):
        response = {
            "data": {"audio": b"fake-mp3".hex(), "status": 2},
            "extra_info": {"usage_characters": 6, "audio_format": "mp3"},
            "trace_id": "trace-1",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "narration.mp3"
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}, clear=True):
                with patch("football_ai_editor.tts.Path.is_file", return_value=False):
                    with patch("urllib.request.urlopen", return_value=_FakeResponse(response)):
                        result, metadata = synthesize_to_file("测试解说文本", output)
            self.assertEqual(result.read_bytes(), b"fake-mp3")
            self.assertEqual(metadata["usage_characters"], 6)
            self.assertEqual(metadata["trace_id"], "trace-1")


if __name__ == "__main__":
    unittest.main()
