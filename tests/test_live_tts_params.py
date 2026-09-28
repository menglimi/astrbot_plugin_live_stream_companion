# -*- coding: utf-8 -*-
"""外部 TTS 情绪/语气透传回归测试（不依赖 AstrBot，可直接本地运行）。

覆盖三件事：
1. 情绪归一与语气提示（自由词 → 通用四类，原词与强度不丢）；
2. 入参按目标方法签名裁剪（只收文本的旧服务行为不变）；
3. 回复意图缓存（同一条回复可复用，跨回复不串台）。
"""

import asyncio
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from live_tts_params import (  # noqa: E402
    StyleIntentCache,
    build_external_tts_kwargs,
    build_style_hint,
    describe_intent,
    map_emotion,
    supported_kwargs,
)


class _OnlyTextService:
    """旧式外部服务：只接受文本。"""

    def __init__(self) -> None:
        self.received: list[dict] = []

    def synth(self, text: str) -> str:
        self.received.append({"text": text})
        return "audio.wav"


class _StyledService:
    """新式外部服务：接受 emotion 与 context。"""

    def __init__(self) -> None:
        self.received: list[dict] = []

    async def synth(self, text: str, emotion: str = "", context: str = "") -> str:
        self.received.append({"text": text, "emotion": emotion, "context": context})
        return "audio.wav"


class _KwargsService:
    """带 **kwargs 的外部服务：应收到全部参数。"""

    def __init__(self) -> None:
        self.received: list[dict] = []

    def synth(self, text: str, **kwargs) -> str:
        self.received.append({"text": text, **kwargs})
        return "audio.wav"


class TestEmotionMapping(unittest.TestCase):
    def test_alias_and_unknown(self):
        self.assertEqual(map_emotion("happy"), "happy")
        self.assertEqual(map_emotion("HAPPY"), "happy")
        self.assertEqual(map_emotion("开心"), "happy")
        self.assertEqual(map_emotion("excited"), "happy")
        self.assertEqual(map_emotion("难过"), "sad")
        self.assertEqual(map_emotion("生气"), "angry")
        self.assertEqual(map_emotion("shy"), "neutral")     # 未知自由词 → 通用兜底
        self.assertEqual(map_emotion(""), "neutral")
        self.assertEqual(map_emotion(None), "neutral")

    def test_style_hint_keeps_raw_word_and_intensity(self):
        hint = build_style_hint("excited", intensity=0.82)
        self.assertIn("明亮", hint)
        self.assertIn("excited", hint)      # 原始词不丢
        self.assertIn("0.8", hint)          # 强度不丢

    def test_style_hint_plain_when_generic(self):
        hint = build_style_hint("happy", intensity=None)
        self.assertTrue(hint.startswith("语气"))
        self.assertNotIn("情绪：", hint)

    def test_style_hint_empty_without_emotion(self):
        self.assertEqual(build_style_hint(""), "")

    def test_describe_intent(self):
        self.assertEqual(describe_intent(None)["source"], "none")
        summary = describe_intent({"emotion": "excited", "intensity": 0.5})
        self.assertEqual(summary["emotion"], "excited")
        self.assertEqual(summary["mapped"], "happy")
        self.assertEqual(summary["source"], "soullink")


class TestKwargsFiltering(unittest.TestCase):
    def test_only_signature_parameters_survive(self):
        service = _OnlyTextService()
        values = build_external_tts_kwargs(
            session_id="session-1", emotion="happy", style_hint="提示", style_enabled=True
        )
        self.assertEqual(supported_kwargs(service.synth, values), {})

    def test_styled_service_receives_emotion_and_context(self):
        service = _StyledService()
        values = build_external_tts_kwargs(
            session_id="session-1", emotion="happy", style_hint="提示", style_enabled=True
        )
        filtered = supported_kwargs(service.synth, values)
        self.assertEqual(
            filtered, {"emotion": "happy", "context": "提示"},
            "只应保留对方签名里出现过的参数",
        )

    def test_style_hint_off_keeps_context_empty(self):
        values = build_external_tts_kwargs(
            session_id="session-1", emotion="sad", style_hint="提示", style_enabled=False
        )
        self.assertEqual(values["context"], "")

    def test_kwargs_service_receives_everything(self):
        service = _KwargsService()
        values = build_external_tts_kwargs(
            session_id="session-2", emotion="angry", style_hint="提示", style_enabled=True
        )
        filtered = supported_kwargs(service.synth, values)
        self.assertEqual(filtered["emotion"], "angry")
        self.assertEqual(filtered["context"], "提示")
        self.assertEqual(filtered["session_id"], "session-2")

    def test_none_values_are_dropped(self):
        service = _StyledService()
        self.assertNotIn("voice", supported_kwargs(service.synth, {"emotion": "happy", "voice": None}))

    def test_uninspectable_callable_passes_through(self):
        """拿不到签名时原样透传（交由调用方 try/except 处理）。"""
        values = {"emotion": "happy"}
        with mock.patch(
            "live_tts_params.inspect.signature", side_effect=ValueError("no signature")
        ):
            self.assertEqual(supported_kwargs(_OnlyTextService().synth, values), values)


class TestIntentCache(unittest.TestCase):
    def test_same_text_reuses_intent(self):
        cache = StyleIntentCache()
        cache.store("今天好开心呀", {"emotion": "happy", "intensity": 0.8})
        self.assertEqual(cache.get("今天好开心呀")["emotion"], "happy")

    def test_other_text_does_not_reuse(self):
        cache = StyleIntentCache()
        cache.store("第一条回复", {"emotion": "happy"})
        self.assertIsNone(cache.get("第二条回复"), "跨回复不得复用上一条情绪")

    def test_overwrite_and_clear(self):
        cache = StyleIntentCache()
        cache.store("文本", {"emotion": "happy"})
        cache.store("文本", None)
        self.assertIsNone(cache.get("文本"))
        cache.store("文本", {"emotion": "sad"})
        cache.clear()
        self.assertIsNone(cache.get("文本"))


class TestExternalCallSimulation(unittest.TestCase):
    """按直播链路的真实调用顺序走一遍：缓存 → 归一 → 裁剪 → 调用。"""

    def _call(self, service, text, intent, *, passthrough=True, style_enabled=False):
        cache = StyleIntentCache()
        cache.store(text, intent)
        stored = cache.get(text) or {}
        raw = str(stored.get("emotion") or "")
        emotion = map_emotion(raw) if (raw and passthrough) else ""
        hint = ""
        if style_enabled and raw:
            hint = build_style_hint(
                raw, intensity=stored.get("intensity"), variant=stored.get("variant") or ""
            )
        kwargs = supported_kwargs(
            service.synth,
            build_external_tts_kwargs(
                session_id="live-session",
                emotion=emotion,
                style_hint=hint,
                style_enabled=style_enabled,
            ),
        )
        result = service.synth(text, **kwargs)
        if asyncio.iscoroutine(result):
            asyncio.run(result)
        return service.received[-1]

    def test_legacy_service_unaffected(self):
        received = self._call(_OnlyTextService(), "你好", {"emotion": "happy"})
        self.assertEqual(received, {"text": "你好"})

    def test_new_service_gets_mapped_emotion(self):
        received = self._call(_StyledService(), "你好", {"emotion": "excited", "intensity": 0.9})
        self.assertEqual(received["emotion"], "happy")
        self.assertEqual(received["context"], "", "语气提示默认关闭")

    def test_style_hint_enabled(self):
        received = self._call(
            _StyledService(), "你好", {"emotion": "excited", "intensity": 0.9},
            style_enabled=True,
        )
        self.assertEqual(received["emotion"], "happy")
        self.assertIn("excited", received["context"])

    def test_passthrough_disabled_keeps_legacy_empty_emotion(self):
        received = self._call(
            _StyledService(), "你好", {"emotion": "happy"}, passthrough=False
        )
        self.assertEqual(received["emotion"], "")

    def test_no_intent_keeps_legacy_behaviour(self):
        received = self._call(_StyledService(), "你好", None)
        self.assertEqual(received["emotion"], "")


if __name__ == "__main__":
    unittest.main()
