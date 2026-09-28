# -*- coding: utf-8 -*-
"""外部 TTS 参数透传（通用实现，不依赖 AstrBot，方便单测）。

本模块刻意只做三件与具体插件无关的事：

1. 把上游给出的情绪词归一成通用四类（``happy`` / ``sad`` / ``angry`` / ``neutral``），
   原始词、强度与变体保留在「语气提示」文本里，不丢信息；
2. 按外部服务方法的**真实签名**裁剪参数——对方不认识的参数一律不传，
   因此对「只收文本」的旧服务仍然逐字兼容；
3. 缓存最近一条回复的语气意图，供同一条回复的 TTS 复用（按文本指纹匹配，避免跨回复串台）。

这里没有任何插件名、平台名或系列名假设：调用方只需要给出 ``text``，被调方按自己的
签名接收它想要的参数。
"""

from __future__ import annotations

import hashlib
import inspect
from typing import Any, Iterable, Mapping

#: 归一化后的通用情绪集合（不扩张，避免把自由词表塞进外部服务）
GENERIC_EMOTIONS = ("happy", "sad", "angry", "neutral")

#: 自由情绪词 → 通用四类。未命中的词一律落到 neutral，但原词会保留在语气提示里。
_EMOTION_ALIASES: dict[str, str] = {
    # happy
    "happy": "happy", "joy": "happy", "joyful": "happy", "excited": "happy",
    "cheerful": "happy", "smile": "happy", "bright": "happy", "proud": "happy",
    "开心": "happy", "高兴": "happy", "愉快": "happy", "兴奋": "happy", "得意": "happy",
    # sad
    "sad": "sad", "sorrow": "sad", "down": "sad", "lonely": "sad", "cry": "sad",
    "难过": "sad", "悲伤": "sad", "伤心": "sad", "委屈": "sad", "失落": "sad",
    # angry
    "angry": "angry", "mad": "angry", "furious": "angry", "annoyed": "angry",
    "生气": "angry", "愤怒": "angry", "不满": "angry", "烦躁": "angry",
    # neutral（显式中性词）
    "neutral": "neutral", "calm": "neutral", "normal": "neutral", "plain": "neutral",
    "自然": "neutral", "中性": "neutral", "普通": "neutral", "平静": "neutral",
}

#: 通用四类 → 中文朗读语气提示（与外部服务的具体实现无关的普适描述）
_GENERIC_HINTS: dict[str, str] = {
    "happy": "语气明亮、轻快，带一点笑意",
    "sad": "语气低沉、放慢、收敛",
    "angry": "语气更有力度和张力，但不要破音",
    "neutral": "语气自然、平稳",
}


def map_emotion(raw: Any) -> str:
    """自由情绪词 → 通用四类之一；空值/未知值统一落到 ``neutral``。"""
    key = str(raw or "").strip().lower()
    if not key:
        return "neutral"
    return _EMOTION_ALIASES.get(key, "neutral")


def build_style_hint(
    raw_emotion: Any,
    *,
    intensity: Any = None,
    variant: Any = "",
) -> str:
    """把原始情绪意图写成一段通用朗读提示；原始词与强度都会保留。"""
    raw = str(raw_emotion or "").strip()
    if not raw:
        return ""
    generic = map_emotion(raw)
    parts = [_GENERIC_HINTS.get(generic, _GENERIC_HINTS["neutral"])]
    detail: list[str] = []
    if raw.lower() != generic:
        detail.append(f"情绪：{raw}")
    number = _coerce_float(intensity)
    if number is not None:
        detail.append(f"强度 {max(0.0, min(1.0, number)):.1f}")
    variant_text = str(variant or "").strip()
    if variant_text:
        detail.append(f"变体：{variant_text}")
    if detail:
        parts.append("（" + "，".join(detail) + "）")
    return "".join(parts)


def build_external_tts_kwargs(
    *,
    session_id: str = "",
    emotion: str = "",
    style_hint: str = "",
    style_enabled: bool = False,
) -> dict[str, Any]:
    """外部 TTS 通用入参（后续按方法签名裁剪）。

    * ``emotion`` 为空串时保持旧行为（显式传空，交给对方自己兜底）；
    * ``style_hint`` 只在 ``style_enabled`` 打开时随 ``context`` 发出，
      避免在用户没开语气提示时改变既有行为。
    """
    return {
        "emotion": str(emotion or ""),
        "context": str(style_hint or "") if style_enabled else "",
        "target_umo": str(session_id or ""),
        "session": str(session_id or ""),
        "session_id": str(session_id or ""),
    }


def supported_kwargs(method: Any, values: Mapping[str, Any]) -> dict[str, Any]:
    """按 ``method`` 的真实签名裁剪 ``values``。

    * 拿不到签名（C 扩展 / 被包装）时保持原样，交由调用方处理异常；
    * 方法带 ``**kwargs`` 时全部传入；
    * 其余只保留签名里出现过、且值不为 ``None`` 的参数。
    """
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return dict(values)
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return dict(values)
    return {
        name: value
        for name, value in values.items()
        if name in parameters and value is not None
    }


def fingerprint(text: Any) -> str:
    """文本指纹：只用于「同一条回复」的意图取用，不参与任何持久化。"""
    content = str(text or "").strip().encode("utf-8", "ignore")
    return hashlib.sha1(content).hexdigest()[:16]


class StyleIntentCache:
    """最近一条回复的语气意图缓存。

    直播链路里「解析情绪」和「合成语音」是两次调用（还可能在后台任务里补发），
    因此用文本指纹把意图绑回同一条回复：文本不一致就返回 ``None``，
    不会把上一条回复的情绪套到新回复上。
    """

    def __init__(self) -> None:
        self._fingerprint = ""
        self._payload: dict[str, Any] | None = None

    def store(self, text: str, payload: Mapping[str, Any] | None) -> None:
        self._fingerprint = fingerprint(text)
        self._payload = dict(payload) if isinstance(payload, Mapping) else None

    def get(self, text: str) -> dict[str, Any] | None:
        if not self._fingerprint or fingerprint(text) != self._fingerprint:
            return None
        return dict(self._payload) if self._payload else None

    def clear(self) -> None:
        self._fingerprint = ""
        self._payload = None


def describe_intent(intent: Mapping[str, Any] | None) -> dict[str, Any]:
    """给诊断页用的只读摘要：命中的情绪 / 是否做了归一 / 是否带语气提示。"""
    if not isinstance(intent, Mapping) or not intent:
        return {"emotion": "", "mapped": "", "intensity": None, "source": "none"}
    raw = str(intent.get("emotion") or "").strip()
    return {
        "emotion": raw,
        "mapped": map_emotion(raw) if raw else "",
        "intensity": _coerce_float(intent.get("intensity")),
        "source": "soullink" if raw else "none",
    }


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iter_generic_emotions() -> Iterable[str]:
    """通用情绪枚举（供页面/文档复用，避免各处硬编码）。"""
    return tuple(GENERIC_EMOTIONS)
