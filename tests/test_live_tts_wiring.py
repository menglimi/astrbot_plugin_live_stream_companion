# -*- coding: utf-8 -*-
"""情绪/语气透传的接线回归（静态断言，不需要 AstrBot 运行时）。

纯函数逻辑由 tests/test_live_tts_params.py 覆盖；这里只守住「链路真的接上了」：
解析 → 缓存 → 取用 → 透传 → 诊断回显，任何一环被删掉都会在这里失败。
"""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class TestLiveTtsWiring(unittest.TestCase):
    def test_soullink_intent_is_cached(self):
        source = _read("soullink_mixin.py")
        self.assertIn("_live_tts_style_cache", source)
        self.assertIn("cache.store(cleaned, intent)", source)

    def test_payload_reads_style_values_and_passes_them(self):
        source = _read("main.py")
        self.assertIn("tts_emotion, tts_style_hint = self._live_tts_style_values(text)", source)
        self.assertIn("emotion=tts_emotion", source)
        self.assertIn("style_hint=tts_style_hint", source)

    def test_external_call_builds_common_kwargs(self):
        source = _read("main.py")
        self.assertIn("build_external_tts_kwargs(", source)
        self.assertIn("return supported_kwargs(method, values)", source)

    def test_switches_are_read_with_expected_defaults(self):
        source = _read("main.py")
        self.assertIn('self.config.get("live_tts_emotion_passthrough_enabled", True)', source)
        self.assertIn('self.config.get("live_tts_style_hint_enabled", False)', source)

    def test_style_values_are_derived_from_cache(self):
        """情绪取值必须走缓存 + 开关，两个开关默认值不得改动。"""
        source = _read("main.py")
        self.assertIn("def _live_tts_style_values(", source)
        self.assertIn("def _live_tts_style_intent_for(", source)
        self.assertIn("map_emotion(raw)", source)
        self.assertIn("build_style_hint(", source)


if __name__ == "__main__":
    unittest.main()
