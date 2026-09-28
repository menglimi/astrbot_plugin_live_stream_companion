"""Optional Soullink Emotion integration for AstrBot and VTube Studio."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import re
import time
from typing import Any

from astrbot.api import logger


SOULLINK_TAG_PATTERN = re.compile(
    r"<soullink\s*>(.*?)</soullink\s*>",
    re.IGNORECASE | re.DOTALL,
)

DEFAULT_VTS_MAPPING: dict[str, dict[str, Any]] = {
    "poseX": {"ids": ["FaceAngleX"], "scale": 36.0, "min": -24.0, "max": 24.0},
    "poseY": {"ids": ["FaceAngleY"], "scale": 32.0, "min": -18.0, "max": 18.0},
    "poseZ": {"ids": ["FaceAngleZ"], "scale": 34.0, "min": -24.0, "max": 24.0},
    "gazeX": {
        "ids": ["EyeLeftX", "EyeRightX"],
        "scale": 0.9,
        "min": -1.0,
        "max": 1.0,
    },
    "gazeY": {
        "ids": ["EyeLeftY", "EyeRightY"],
        "scale": 0.9,
        "min": -1.0,
        "max": 1.0,
    },
    "eyeOpenLeft": {
        "ids": ["EyeOpenLeft"],
        "scale": 0.526315,
        "min": 0.0,
        "max": 1.0,
    },
    "eyeOpenRight": {
        "ids": ["EyeOpenRight"],
        "scale": 0.526315,
        "min": 0.0,
        "max": 1.0,
    },
    "mouthShape": {
        "ids": ["MouthSmile"],
        "scale": 0.32,
        "offset": 0.78,
        "min": 0.2,
        "max": 1.0,
    },
    "browComposite": {
        "ids": ["Brows"],
        "scale": 0.5,
        "offset": 0.5,
        "min": 0.0,
        "max": 1.0,
    },
}

SOULLINK_COMPOSITE_DEFAULTS: dict[str, float] = {
    "bodyXMix": 0.65,
    "bodyYMix": 0.6,
    "bodyZMix": 0.65,
    "eyeSquintMix": 0.3,
    "mouthNeutral": 0.04,
    "mouthFrownMix": 1.0,
    "browInnerMix": 0.55,
    "browOuterMix": 0.45,
    "browDownMix": 1.0,
}


def _source_meta(
    label: str,
    group: str,
    minimum: float,
    neutral: float,
    maximum: float,
) -> dict[str, Any]:
    return {
        "label": label,
        "group": group,
        "min": minimum,
        "neutral": neutral,
        "max": maximum,
    }


SOULLINK_SOURCE_META: dict[str, dict[str, Any]] = {
    "poseX": _source_meta("头部与身体 X", "姿态", -1.0, 0.0, 1.0),
    "poseY": _source_meta("头部与身体 Y", "姿态", -1.0, 0.0, 1.0),
    "poseZ": _source_meta("头部与身体 Z", "姿态", -1.0, 0.0, 1.0),
    "headX": _source_meta("头部 X", "姿态", -1.0, 0.0, 1.0),
    "headY": _source_meta("头部 Y", "姿态", -1.0, 0.0, 1.0),
    "headZ": _source_meta("头部 Z", "姿态", -1.0, 0.0, 1.0),
    "bodyX": _source_meta("身体 X", "姿态", -1.0, 0.0, 1.0),
    "bodyY": _source_meta("身体 Y", "姿态", -1.0, 0.0, 1.0),
    "bodyZ": _source_meta("身体 Z", "姿态", -1.0, 0.0, 1.0),
    "gazeX": _source_meta("视线 X", "视线", -1.0, 0.0, 1.0),
    "gazeY": _source_meta("视线 Y", "视线", -1.0, 0.0, 1.0),
    "eyeOpenLeft": _source_meta("左眼开合", "眼睛", 0.0, 1.0, 1.0),
    "eyeOpenRight": _source_meta("右眼开合", "眼睛", 0.0, 1.0, 1.0),
    "eyeOpen": _source_meta("双眼开合", "眼睛", 0.0, 1.0, 1.0),
    "eyeBlinkL": _source_meta("左眼眨眼", "眼睛", 0.0, 0.0, 1.0),
    "eyeBlinkR": _source_meta("右眼眨眼", "眼睛", 0.0, 0.0, 1.0),
    "eyeSmile": _source_meta("笑眼", "眼睛", 0.0, 0.0, 1.0),
    "eyeSquint": _source_meta("眯眼", "眼睛", 0.0, 0.0, 1.0),
    "mouthShape": _source_meta("综合嘴角", "嘴部", -1.0, 0.0, 1.0),
    "mouthSmile": _source_meta("微笑", "嘴部", 0.0, 0.0, 1.0),
    "mouthFrown": _source_meta("嘴角下压", "嘴部", 0.0, 0.0, 1.0),
    "mouthOpen": _source_meta("张嘴", "嘴部", 0.0, 0.0, 1.0),
    "mouthPucker": _source_meta("嘟嘴", "嘴部", 0.0, 0.0, 1.0),
    "browComposite": _source_meta("综合眉形", "眉毛", -1.0, 0.0, 1.0),
    "browInnerUp": _source_meta("内眉抬起", "眉毛", 0.0, 0.0, 1.0),
    "browOuterUp": _source_meta("外眉抬起", "眉毛", 0.0, 0.0, 1.0),
    "browDown": _source_meta("眉毛下压", "眉毛", 0.0, 0.0, 1.0),
    "blush": _source_meta("脸红", "效果", 0.0, 0.0, 1.0),
    "tear": _source_meta("泪光", "效果", 0.0, 0.0, 1.0),
    "sweat": _source_meta("汗滴", "效果", 0.0, 0.0, 1.0),
    "breath": _source_meta("呼吸", "效果", 0.0, 0.5, 1.0),
    "vadValence": _source_meta("VAD 愉悦度", "情绪", -1.0, 0.0, 1.0),
    "vadArousal": _source_meta("VAD 唤醒度", "情绪", -1.0, 0.0, 1.0),
    "vadDominance": _source_meta("VAD 支配度", "情绪", -1.0, 0.0, 1.0),
    "emotionIntensity": _source_meta("情绪强度", "情绪", 0.0, 0.0, 1.0),
}


class SoullinkMixin:
    """Prompt, lifecycle, and VTS mapping glue for the Node emotion engine."""

    def _is_soullink_enabled(self) -> bool:
        return bool(self.config.get("soullink_enabled", False))

    def _soullink_mode(self) -> str:
        mode = str(self.config.get("soullink_mode") or "emotion").strip().lower()
        return mode if mode in {"emotion", "full"} else "emotion"

    def _soullink_runtime_options(self) -> dict[str, Any]:
        style = str(self.config.get("soullink_motion_style") or "natural").strip().lower()
        if style not in {"natural", "lively", "calm", "shy"}:
            style = "natural"
        return {
            "style": style,
            "fps": max(5, min(30, self._safe_parse_int(self.config.get("soullink_fps"), 20))),
            "parameterGain": max(
                0.4,
                min(5.0, self._safe_parse_float(self.config.get("soullink_parameter_gain"), 1.7)),
            ),
            "bodyMotionGain": max(
                0.0,
                min(4.0, self._safe_parse_float(self.config.get("soullink_body_motion_gain"), 1.6)),
            ),
            "vadDecayRate": max(
                0.0,
                min(1.0, self._safe_parse_float(self.config.get("soullink_vad_decay_rate"), 0.075)),
            ),
        }

    async def _start_soullink_runtime(self) -> bool:
        runtime = getattr(self, "_soullink_runtime", None)
        if not self._is_soullink_enabled() or runtime is None:
            return False
        options = self._soullink_runtime_options()
        self._accept_soullink_frames = True
        runtime.fps = int(options["fps"])
        runtime.node_path = str(self.config.get("soullink_node_path") or "").strip()
        scheduler = getattr(self, "_vts_parameter_scheduler", None)
        if scheduler:
            scheduler.set_source_fps("soullink", int(options["fps"]))
            scheduler.start()
        started = await runtime.start(options)
        if not started:
            self._accept_soullink_frames = False
            if scheduler:
                scheduler.clear_layer("soullink")
        else:
            self._ensure_soullink_gaze()
        return started

    async def _stop_soullink_runtime(self) -> None:
        self._accept_soullink_frames = False
        scheduler = getattr(self, "_vts_parameter_scheduler", None)
        runtime = getattr(self, "_soullink_runtime", None)
        self._stop_soullink_gaze()
        if runtime:
            await runtime.stop()
        if scheduler:
            scheduler.clear_layer("soullink")

    def _stop_soullink_gaze(self) -> None:
        """停掉鼠标视线追踪（gaze 循环 + VTS 轮询器）。"""
        gaze_task = getattr(self, "_soullink_gaze_task", None)
        if gaze_task:
            gaze_task.cancel()
            self._soullink_gaze_task = None
        poll_task = getattr(self, "_soullink_gaze_poll_task", None)
        if poll_task:
            poll_task.cancel()
            self._soullink_gaze_poll_task = None
        scheduler = getattr(self, "_vts_parameter_scheduler", None)
        if scheduler:
            scheduler.clear_layer("soullink_gaze")

    def _is_soullink_gaze_enabled(self) -> bool:
        return bool(self.config.get("soullink_gaze_enabled", False))

    def _soullink_gaze_is_tracking(self, now: float | None = None) -> bool:
        last_update = float(getattr(self, "_soullink_gaze_last_update_at", 0.0) or 0.0)
        current = time.monotonic() if now is None else now
        return last_update > 0.0 and current - last_update <= 1.0

    def _soullink_gaze_status(self) -> dict[str, Any]:
        runtime = getattr(self, "_soullink_runtime", None)
        gaze_task = getattr(self, "_soullink_gaze_task", None)
        poll_task = getattr(self, "_soullink_gaze_poll_task", None)
        last_update = float(getattr(self, "_soullink_gaze_last_update_at", 0.0) or 0.0)
        now = time.monotonic()
        running = bool(
            runtime
            and getattr(runtime, "running", False)
            and gaze_task is not None
            and not gaze_task.done()
            and poll_task is not None
            and not poll_task.done()
        )
        return {
            "enabled": self._is_soullink_gaze_enabled(),
            "soullink_enabled": self._is_soullink_enabled(),
            "running": running,
            "tracking": running and self._soullink_gaze_is_tracking(now),
            "x": round(float(getattr(self, "_soullink_gaze_x", 0.5)), 3),
            "y": round(float(getattr(self, "_soullink_gaze_y", 0.5)), 3),
            "last_error": str(getattr(self, "_soullink_gaze_last_error", "") or ""),
            "last_update_age": round(now - last_update, 3) if last_update > 0.0 else None,
        }

    async def _soullink_gaze_loop(self) -> None:
        """消费 VTS 轮询到的鼠标坐标 → 平滑 → 推身体朝向 + 视线。

        坐标由 _soullink_gaze_vts_poller 从 VTS 的 MousePositionX/Y
        读取并归一化为 0~1（左上原点）。

        模型映射：FaceAngleX/Y 同时驱动 ParamAngleX/Y（头）和
        ParamBodyAngleX/Y（身体），所以推 FaceAngleX/Y 让整个身体
        跟随鼠标朝向；左右眼参数精调眼珠视线。后写覆盖 Soullink
        默认视线（scheduler 合并顺序保证 soullink_gaze 赢）。
        """
        body_x = 0.0   # FaceAngleX（身体+头左右）
        body_y = 0.0   # FaceAngleY（身体+头上下）
        eye_x = 0.0
        eye_y = 0.0
        body_gain = 25.0  # 身体朝向角度（度）
        eye_gain = 1.6    # 眼珠偏转增益
        layer_active = False

        while True:
            scheduler = getattr(self, "_vts_parameter_scheduler", None)
            if not self._soullink_gaze_is_tracking():
                if scheduler and layer_active:
                    scheduler.clear_layer("soullink_gaze")
                body_x = body_y = eye_x = eye_y = 0.0
                layer_active = False
                await asyncio.sleep(0.05)
                continue
            x = getattr(self, "_soullink_gaze_x", 0.5)
            y = getattr(self, "_soullink_gaze_y", 0.5)
            dx = x - 0.5
            dy = y - 0.5
            target_body_x = dx * body_gain
            target_body_y = dy * body_gain
            body_x += (target_body_x - body_x) * 0.25
            body_y += (target_body_y - body_y) * 0.25
            target_eye_x = dx * 2.0 * eye_gain
            target_eye_y = -dy * 2.0 * eye_gain
            eye_x += (target_eye_x - eye_x) * 0.35
            eye_y += (target_eye_y - eye_y) * 0.35
            if scheduler:
                output_eye_x = max(-1.0, min(1.0, -eye_x))
                output_eye_y = max(-1.0, min(1.0, eye_y))
                scheduler.set_layer(
                    "soullink_gaze",
                    [
                        {"id": "FaceAngleX", "value": round(body_x, 2)},
                        {"id": "FaceAngleY", "value": round(body_y, 2)},
                        {"id": "EyeLeftX", "value": round(output_eye_x, 3)},
                        {"id": "EyeRightX", "value": round(output_eye_x, 3)},
                        {"id": "EyeLeftY", "value": round(output_eye_y, 3)},
                        {"id": "EyeRightY", "value": round(output_eye_y, 3)},
                    ],
                    ttl=0.25,
                )
                layer_active = True
            await asyncio.sleep(0.05)  # 20 Hz

    def _set_soullink_gaze(self, x: float, y: float) -> None:
        """更新鼠标坐标（由 VTS 轮询器或测试按钮调用）。"""
        try:
            self._soullink_gaze_x = max(0.0, min(1.0, float(x)))
            self._soullink_gaze_y = max(0.0, min(1.0, float(y)))
            self._soullink_gaze_last_update_at = time.monotonic()
            self._soullink_gaze_last_error = ""
        except (TypeError, ValueError):
            pass

    async def _soullink_gaze_vts_poller(self) -> None:
        """轮询 VTS 鼠标位置参数。

        VTS 桌面版系统级采集鼠标（用于点击/物品交互），MousePositionX/Y
        始终有值，范围 -1~1：X 轴 -1=屏幕左缘 +1=右缘；Y 轴与屏幕坐标
        相反（+1=屏幕顶），换算到 0~1（左上原点）时取反。
        走 self.vts 请求-响应通道（_parameter_vts 的响应被排水任务消费，
        不能在其上做请求-响应）。
        """
        interval = 0.066  # ~15 Hz：每周期两次串行请求，别挤占命令通道
        retry_delay = 3.0

        while True:
            try:
                data_x = await self.vts.get_parameter_value("MousePositionX")
                data_y = await self.vts.get_parameter_value("MousePositionY")
                mx = float(data_x.get("value", 0.0))
                my = float(data_y.get("value", 0.0))
                self._set_soullink_gaze((mx + 1.0) / 2.0, (1.0 - my) / 2.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._soullink_gaze_last_error = str(exc)
                logger.debug(f"[Soullink] VTS 鼠标参数轮询失败: {exc}")
                await asyncio.sleep(retry_delay)
                continue
            await asyncio.sleep(interval)

    def _ensure_soullink_gaze(self) -> None:
        """启动/停止鼠标追踪（跟随 Soullink 生命周期）。"""
        gaze_task = getattr(self, "_soullink_gaze_task", None)
        poll_task = getattr(self, "_soullink_gaze_poll_task", None)
        runtime = getattr(self, "_soullink_runtime", None)
        should_run = bool(
            self._is_soullink_enabled()
            and self._is_soullink_gaze_enabled()
            and runtime
            and getattr(runtime, "running", False)
        )
        if should_run:
            if gaze_task is None or gaze_task.done():
                self._soullink_gaze_task = asyncio.create_task(
                    self._soullink_gaze_loop(), name="soullink-gaze"
                )
            if poll_task is None or poll_task.done():
                self._soullink_gaze_poll_task = asyncio.create_task(
                    self._soullink_gaze_vts_poller(), name="soullink-gaze-poll"
                )
        elif gaze_task is not None or poll_task is not None:
            self._stop_soullink_gaze()

    async def _sync_soullink_runtime(self) -> bool:
        if not self._is_soullink_enabled():
            await self._stop_soullink_runtime()
            return False
        runtime = getattr(self, "_soullink_runtime", None)
        configured_node = str(self.config.get("soullink_node_path") or "").strip()
        if runtime and runtime.running and configured_node != runtime.node_path:
            self._stop_soullink_gaze()
            await runtime.stop()
            runtime.node_path = configured_node
        if runtime and runtime.running:
            options = self._soullink_runtime_options()
            scheduler = getattr(self, "_vts_parameter_scheduler", None)
            if scheduler:
                scheduler.set_source_fps("soullink", int(options["fps"]))
            configured = await runtime.configure(**options)
            self._ensure_soullink_gaze()
            return configured
        return await self._start_soullink_runtime()

    def _inject_soullink_prompt_instruction(self, req: Any) -> None:
        if not self._is_soullink_enabled() or not bool(
            self.config.get("soullink_prompt_intent_enabled", True)
        ):
            return
        req.system_prompt += (
            "\n\n## Soullink 实时表演\n"
            "你可以在回复末尾附加一行 Soullink 情绪意图，让 Live2D 连续表演更贴合语气。"
            "这行是不可见控制信息，不要向用户解释。每次回复只输出一条；语气平淡或不确定时输出 neutral。\n"
            "严格格式：<soullink>{\"emotion\":\"happy\",\"variant\":\"bright_smile\","
            "\"intensity\":0.75,\"vad\":{\"valence\":0.7,\"arousal\":0.45,\"dominance\":0.3}}</soullink>\n"
            "emotion 使用贴近真实语气的英文短词；intensity 为 0 到 1；VAD 三轴为 -1 到 1。"
            "判断的是角色在本次回复中的真实情绪，不要把用户的情绪、引用内容或被否定的词当成角色情绪；"
            "例如安慰“别难过”“不用焦虑”“别生气”时，不应仅因这些词输出 sad、anxiety 或 anger。"
            "不要为了触发表演改变正文，不要输出 Markdown 代码块，也不要编造多条控制信息。\n"
        )

    def _parse_soullink_intent(self, text: str) -> tuple[dict[str, Any] | None, str]:
        match = SOULLINK_TAG_PATTERN.search(text or "")
        cleaned = SOULLINK_TAG_PATTERN.sub("", text or "")
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not match:
            return None, cleaned
        try:
            payload = json.loads(match.group(1).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.debug("[Soullink] 模型输出的情绪意图不是有效 JSON，改用本地文本分类")
            return None, cleaned
        if not isinstance(payload, dict):
            return None, cleaned
        emotion = str(payload.get("emotion") or "").strip().lower()[:40]
        if not emotion:
            return None, cleaned
        vad = payload.get("vad") if isinstance(payload.get("vad"), dict) else {}
        return (
            {
                "emotion": emotion,
                "variant": str(payload.get("variant") or "").strip()[:60],
                "intensity": self._clamp_number(payload.get("intensity"), 0.0, 1.0, 0.7),
                "vad": {
                    "valence": self._clamp_number(vad.get("valence"), -1.0, 1.0, 0.0),
                    "arousal": self._clamp_number(vad.get("arousal"), -1.0, 1.0, 0.0),
                    "dominance": self._clamp_number(vad.get("dominance"), -1.0, 1.0, 0.0),
                },
                "contextTags": ["astrbot_llm", "prompt_intent"],
                "sourceMessage": cleaned[:1000],
            },
            cleaned,
        )

    def _handle_soullink_response(self, text: str) -> str:
        if not self._is_soullink_enabled():
            return text
        intent, cleaned = self._parse_soullink_intent(text)
        cache = getattr(self, "_live_tts_style_cache", None)
        if cache is not None:
            # 同一条回复稍后合成语音时按这段文本取回该意图（不跨回复串台）；
            # 没解析出意图时也记一条，避免复用上一条回复的情绪。
            cache.store(cleaned, intent)
        runtime = getattr(self, "_soullink_runtime", None)
        if not runtime or not runtime.running:
            return cleaned

        async def react() -> None:
            if intent:
                await runtime.trigger(intent)
            elif self._soullink_mode() == "full" or bool(
                self.config.get("soullink_local_fallback_enabled", False)
            ):
                await runtime.react_to_text(cleaned)

        self._create_soullink_task(react())
        return cleaned

    def _create_soullink_task(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        tasks = getattr(self, "_soullink_tasks", None)
        if isinstance(tasks, set):
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    async def _test_soullink_intent(self, intent: dict[str, Any]) -> bool:
        if not self._is_soullink_enabled():
            return False
        runtime = getattr(self, "_soullink_runtime", None)
        if not runtime or not runtime.running:
            if not await self._start_soullink_runtime():
                return False
        return await runtime.trigger(intent)

    def _on_soullink_frame(self, snapshot: dict[str, Any]) -> None:
        if not self._is_soullink_enabled() or not getattr(
            self, "_accept_soullink_frames", True
        ):
            return
        parameters = self._map_soullink_frame_to_vts(snapshot)
        self._soullink_last_vts_parameters = parameters
        scheduler = getattr(self, "_vts_parameter_scheduler", None)
        if scheduler and parameters:
            scheduler.set_layer("soullink", parameters, ttl=1.0)

    def _map_soullink_frame_to_vts(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw_facs = snapshot.get("facs") if isinstance(snapshot.get("facs"), dict) else {}
        smoothed = (
            snapshot.get("live2dParams")
            if isinstance(snapshot.get("live2dParams"), dict)
            else {}
        )
        facs = smoothed or raw_facs
        if not facs:
            return []
        mapping = self._soullink_vts_mapping()
        composites = mapping.get("composites") if isinstance(mapping.get("composites"), dict) else {}
        values = dict(raw_facs)
        values.update(facs)
        values["poseX"] = self._number(values.get("headX")) + self._number(
            values.get("bodyX")
        ) * self._number(composites.get("bodyXMix"), 0.65)
        values["poseY"] = self._number(values.get("headY")) + self._number(
            values.get("bodyY")
        ) * self._number(composites.get("bodyYMix"), 0.6)
        values["poseZ"] = self._number(values.get("headZ")) + self._number(
            values.get("bodyZ")
        ) * self._number(composites.get("bodyZMix"), 0.65)
        eye_open = self._number(facs.get("eyeOpen"), 1.0)
        eye_squint = self._number(facs.get("eyeSquint"))
        values["eyeOpenLeft"] = max(
            0.0,
            eye_open * (1.0 - self._number(facs.get("eyeBlinkL")))
            - eye_squint * self._number(composites.get("eyeSquintMix"), 0.3),
        )
        values["eyeOpenRight"] = max(
            0.0,
            eye_open * (1.0 - self._number(facs.get("eyeBlinkR")))
            - eye_squint * self._number(composites.get("eyeSquintMix"), 0.3),
        )
        values["mouthShape"] = (
            self._number(facs.get("mouthSmile"))
            - self._number(composites.get("mouthNeutral"), 0.04)
            - self._number(facs.get("mouthFrown"))
            * self._number(composites.get("mouthFrownMix"), 1.0)
        )
        values["browComposite"] = (
            self._number(facs.get("browInnerUp"))
            * self._number(composites.get("browInnerMix"), 0.55)
            + self._number(facs.get("browOuterUp"))
            * self._number(composites.get("browOuterMix"), 0.45)
            - self._number(facs.get("browDown"))
            * self._number(composites.get("browDownMix"), 1.0)
        )
        vad = snapshot.get("vad") if isinstance(snapshot.get("vad"), dict) else {}
        current_vad = vad.get("current") if isinstance(vad.get("current"), dict) else {}
        values["vadValence"] = self._number(current_vad.get("valence"))
        values["vadArousal"] = self._number(current_vad.get("arousal"))
        values["vadDominance"] = self._number(current_vad.get("dominance"))
        values["emotionIntensity"] = self._number(vad.get("intensity"))

        outputs: dict[str, dict[str, Any]] = {}
        frame_time = self._number(snapshot.get("time"), time.monotonic())
        rules = mapping.get("rules") if isinstance(mapping.get("rules"), list) else []
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                continue
            source = str(rule.get("source") or "").strip()
            target = str(rule.get("target") or "").strip()
            if source not in values or not target:
                continue
            valid_inputs = getattr(self, "_soullink_valid_vts_inputs", None)
            if isinstance(valid_inputs, set) and valid_inputs and target not in valid_inputs:
                continue
            value = self._transform_soullink_mapping_value(
                self._number(values.get(source)), rule
            )
            smoothing = max(0.0, self._number(rule.get("smoothing")))
            if smoothing > 0.0:
                value = self._smooth_soullink_mapping_value(
                    f"{rule.get('id') or index}:{target}",
                    value,
                    smoothing,
                    frame_time,
                )
            blend = str(rule.get("blend") or "replace").lower()
            previous = outputs.get(target)
            if previous and blend == "add":
                value = previous["value"] + value - self._number(
                    rule.get("outputNeutral")
                )
            elif previous and blend == "max":
                value = max(previous["value"], value)
            elif previous and blend == "min":
                value = min(previous["value"], value)
            outputs[target] = {
                "id": target,
                "value": value,
                "weight": self._clamp_number(rule.get("weight"), 0.0, 1.0, 1.0),
            }
        return list(outputs.values())

    def _transform_soullink_mapping_value(
        self,
        source_value: float,
        rule: dict[str, Any],
    ) -> float:
        source_min = self._number(rule.get("sourceMin"), -1.0)
        source_neutral = self._number(rule.get("sourceNeutral"), 0.0)
        source_max = self._number(rule.get("sourceMax"), 1.0)
        if source_value >= source_neutral:
            span = source_max - source_neutral
            normalized = (source_value - source_neutral) / span if span > 1e-9 else 0.0
        else:
            span = source_neutral - source_min
            normalized = (source_value - source_neutral) / span if span > 1e-9 else 0.0
        should_clamp = bool(rule.get("clamp", True))
        if should_clamp:
            normalized = max(-1.0, min(1.0, normalized))
        if bool(rule.get("invert", False)):
            normalized = -normalized
        deadzone = max(0.0, min(0.95, self._number(rule.get("deadzone"))))
        magnitude = abs(normalized)
        if magnitude <= deadzone:
            normalized = 0.0
        elif deadzone > 0.0:
            normalized = math.copysign((magnitude - deadzone) / (1.0 - deadzone), normalized)
        curve = max(0.05, min(8.0, self._number(rule.get("curve"), 1.0)))
        normalized = math.copysign(abs(normalized) ** curve, normalized) if normalized else 0.0
        output_min = self._number(rule.get("outputMin"), -1.0)
        output_neutral = self._number(rule.get("outputNeutral"), 0.0)
        output_max = self._number(rule.get("outputMax"), 1.0)
        if normalized >= 0.0:
            value = output_neutral + normalized * (output_max - output_neutral)
        else:
            value = output_neutral + (-normalized) * (output_min - output_neutral)
        if should_clamp:
            low = min(output_min, output_neutral, output_max)
            high = max(output_min, output_neutral, output_max)
            value = max(low, min(high, value))
        return value

    def _smooth_soullink_mapping_value(
        self,
        key: str,
        value: float,
        smoothing: float,
        frame_time: float,
    ) -> float:
        state = getattr(self, "_soullink_mapping_smoothing", None)
        if not isinstance(state, dict):
            state = {}
            self._soullink_mapping_smoothing = state
        previous = state.get(key)
        if not isinstance(previous, tuple) or len(previous) != 2:
            state[key] = (value, frame_time)
            return value
        previous_value, previous_time = previous
        delta = frame_time - self._number(previous_time, frame_time)
        if delta <= 0.0:
            smoothed = value
        else:
            alpha = 1.0 - math.exp(-delta / max(0.001, smoothing))
            smoothed = self._number(previous_value, value) + (value - self._number(previous_value, value)) * alpha
        state[key] = (smoothed, frame_time)
        return smoothed

    def _soullink_vts_mapping(self) -> dict[str, Any]:
        preview = getattr(self, "_soullink_mapping_preview", None)
        preview_until = self._number(getattr(self, "_soullink_mapping_preview_until", 0.0))
        now = time.monotonic()
        if isinstance(preview, dict) and preview_until > now:
            mapping = preview
            signature = f"preview:{getattr(self, '_soullink_mapping_preview_revision', 0)}"
        else:
            if isinstance(preview, dict):
                self._clear_soullink_mapping_preview()
            raw = self.config.get("soullink_vts_mapping")
            signature = self._soullink_mapping_signature(raw)
            if signature == getattr(self, "_soullink_mapping_cache_signature", None):
                mapping = getattr(self, "_soullink_mapping_cache", None)
            else:
                mapping = self._normalize_soullink_mapping(raw)
                self._soullink_mapping_cache_signature = signature
                self._soullink_mapping_cache = mapping
        if not isinstance(mapping, dict):
            mapping = self._normalize_soullink_mapping({})
        if signature != getattr(self, "_soullink_mapping_active_signature", None):
            self._soullink_mapping_active_signature = signature
            self._soullink_mapping_smoothing = {}
        return mapping

    def _normalize_soullink_mapping(
        self,
        raw: Any,
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
        payload = self._parse_soullink_mapping(raw)
        if not payload:
            return self._legacy_soullink_mapping_to_advanced(DEFAULT_VTS_MAPPING)
        if not isinstance(payload.get("rules"), list):
            return self._legacy_soullink_mapping_to_advanced(payload)

        errors: list[str] = []
        composites = dict(SOULLINK_COMPOSITE_DEFAULTS)
        raw_composites = payload.get("composites") if isinstance(payload.get("composites"), dict) else {}
        for key, default in SOULLINK_COMPOSITE_DEFAULTS.items():
            composites[key] = max(
                -10.0,
                min(10.0, self._finite_number(raw_composites.get(key), default)),
            )

        normalized_rules: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for index, raw_rule in enumerate(payload.get("rules", [])[:256]):
            if not isinstance(raw_rule, dict):
                errors.append(f"第 {index + 1} 条规则不是对象")
                continue
            source = str(raw_rule.get("source") or "").strip()[:80]
            targets = raw_rule.get("targets") if isinstance(raw_rule.get("targets"), list) else None
            if targets is None:
                targets = [raw_rule.get("target")]
            targets = [str(item or "").strip()[:120] for item in targets]
            targets = [item for item in targets if item]
            enabled = self._mapping_bool(raw_rule.get("enabled"), True)
            if not source:
                if enabled:
                    errors.append(f"第 {index + 1} 条规则缺少 Soullink 源")
                continue
            if not targets:
                if enabled:
                    errors.append(f"第 {index + 1} 条规则缺少 VTS 目标")
                continue
            meta = SOULLINK_SOURCE_META.get(
                source,
                {"min": -1.0, "neutral": 0.0, "max": 1.0},
            )
            source_min = self._finite_number(raw_rule.get("sourceMin"), meta["min"])
            source_neutral = self._finite_number(raw_rule.get("sourceNeutral"), meta["neutral"])
            source_max = self._finite_number(raw_rule.get("sourceMax"), meta["max"])
            if source_min > source_neutral or source_neutral > source_max:
                errors.append(f"第 {index + 1} 条规则的源范围必须满足 min ≤ 中性 ≤ max")
                continue
            base_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(raw_rule.get("id") or f"rule-{index + 1}"))[:64]
            for target_index, target in enumerate(targets):
                rule_id = base_id if len(targets) == 1 else f"{base_id}-{target_index + 1}"
                original_id = rule_id
                suffix = 2
                while rule_id in used_ids:
                    rule_id = f"{original_id}-{suffix}"
                    suffix += 1
                used_ids.add(rule_id)
                normalized_rules.append(
                    {
                        "id": rule_id,
                        "enabled": enabled,
                        "source": source,
                        "target": target,
                        "sourceMin": source_min,
                        "sourceNeutral": source_neutral,
                        "sourceMax": source_max,
                        "outputMin": self._finite_number(raw_rule.get("outputMin"), -1.0),
                        "outputNeutral": self._finite_number(raw_rule.get("outputNeutral"), 0.0),
                        "outputMax": self._finite_number(raw_rule.get("outputMax"), 1.0),
                        "curve": max(0.05, min(8.0, self._finite_number(raw_rule.get("curve"), 1.0))),
                        "deadzone": max(0.0, min(0.95, self._finite_number(raw_rule.get("deadzone"), 0.0))),
                        "smoothing": max(0.0, min(5.0, self._finite_number(raw_rule.get("smoothing"), 0.0))),
                        "weight": max(0.0, min(1.0, self._finite_number(raw_rule.get("weight"), 1.0))),
                        "invert": self._mapping_bool(raw_rule.get("invert"), False),
                        "clamp": self._mapping_bool(raw_rule.get("clamp"), True),
                        "blend": str(raw_rule.get("blend") or "replace").lower()
                        if str(raw_rule.get("blend") or "replace").lower() in {"replace", "add", "max", "min"}
                        else "replace",
                    }
                )
        if strict and errors:
            raise ValueError("；".join(errors[:6]))
        return {"version": 2, "composites": composites, "rules": normalized_rules}

    def _legacy_soullink_mapping_to_advanced(
        self,
        legacy: dict[str, Any],
    ) -> dict[str, Any]:
        rules: list[dict[str, Any]] = []
        for source, raw_rule in legacy.items():
            if not isinstance(raw_rule, dict):
                continue
            ids = raw_rule.get("ids") or ([raw_rule.get("id")] if raw_rule.get("id") else [])
            if isinstance(ids, str):
                ids = [ids]
            scale = self._finite_number(raw_rule.get("scale"), 1.0)
            offset = self._finite_number(raw_rule.get("offset"), 0.0)
            output_min = self._finite_number(raw_rule.get("min"), -1000000.0)
            output_max = self._finite_number(raw_rule.get("max"), 1000000.0)
            low = min(output_min, output_max)
            high = max(output_min, output_max)
            meta = SOULLINK_SOURCE_META.get(
                str(source),
                {"min": -1.0, "neutral": 0.0, "max": 1.0},
            )
            if abs(scale) < 1e-12:
                source_min = self._number(meta["min"], -1.0)
                source_max = self._number(meta["max"], 1.0)
                invert = False
            elif scale > 0.0:
                source_min = (low - offset) / scale
                source_max = (high - offset) / scale
                invert = False
            else:
                absolute_scale = abs(scale)
                source_min = (offset - high) / absolute_scale
                source_max = (offset - low) / absolute_scale
                invert = True
            source_neutral = max(
                min(source_min, source_max),
                min(max(source_min, source_max), self._number(meta["neutral"])),
            )
            output_neutral = max(low, min(high, source_neutral * scale + offset))
            for target_index, target in enumerate(ids):
                target = str(target or "").strip()
                if not target:
                    continue
                rules.append(
                    {
                        "id": f"legacy-{source}-{target_index + 1}",
                        "enabled": True,
                        "source": str(source),
                        "target": target,
                        "sourceMin": min(source_min, source_max),
                        "sourceNeutral": source_neutral,
                        "sourceMax": max(source_min, source_max),
                        "outputMin": low,
                        "outputNeutral": output_neutral,
                        "outputMax": high,
                        "curve": 1.0,
                        "deadzone": 0.0,
                        "smoothing": 0.0,
                        "weight": self._clamp_number(raw_rule.get("weight"), 0.0, 1.0, 1.0),
                        "invert": invert,
                        "clamp": True,
                        "blend": "replace",
                    }
                )
        return {
            "version": 2,
            "composites": dict(SOULLINK_COMPOSITE_DEFAULTS),
            "rules": rules,
        }

    def _soullink_mapping_editor_payload(self) -> dict[str, Any]:
        raw = self.config.get("soullink_vts_mapping")
        parsed = self._parse_soullink_mapping(raw)
        saved = self._normalize_soullink_mapping(parsed)
        active = self._soullink_vts_mapping()
        return {
            "version": 2,
            "mode": "default" if not parsed else "custom",
            "previewActive": active is getattr(self, "_soullink_mapping_preview", None),
            "previewExpiresIn": max(
                0.0,
                self._number(getattr(self, "_soullink_mapping_preview_until", 0.0))
                - time.monotonic(),
            ),
            "sources": [
                {"id": source, **meta}
                for source, meta in SOULLINK_SOURCE_META.items()
            ],
            "compositeDefaults": dict(SOULLINK_COMPOSITE_DEFAULTS),
            "defaultMapping": self._normalize_soullink_mapping({}),
            "savedMapping": copy.deepcopy(saved),
            "activeMapping": copy.deepcopy(active),
        }

    def _set_soullink_vts_input_catalog(self, inputs: list[dict[str, Any]]) -> None:
        self._soullink_valid_vts_inputs = {
            str(item.get("name") or "").strip()
            for item in inputs
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

    async def _refresh_soullink_vts_input_catalog(self) -> bool:
        vts = getattr(self, "vts", None)
        if not vts or not bool(getattr(vts, "is_authenticated", False)):
            return False
        try:
            inputs = await vts.get_input_parameters()
            self._set_soullink_vts_input_catalog(inputs)
            return bool(inputs)
        except Exception as exc:
            logger.debug(f"[Soullink] 刷新 VTS 输入目录失败: {exc}")
            return False

    def _set_soullink_mapping_preview(self, raw: Any) -> dict[str, Any]:
        mapping = self._normalize_soullink_mapping(raw, strict=True)
        self._soullink_mapping_preview = mapping
        self._soullink_mapping_preview_until = time.monotonic() + 120.0
        self._soullink_mapping_preview_revision = int(
            getattr(self, "_soullink_mapping_preview_revision", 0)
        ) + 1
        self._soullink_mapping_smoothing = {}
        return mapping

    def _clear_soullink_mapping_preview(self) -> None:
        self._soullink_mapping_preview = None
        self._soullink_mapping_preview_until = 0.0
        self._soullink_mapping_preview_revision = int(
            getattr(self, "_soullink_mapping_preview_revision", 0)
        ) + 1
        self._soullink_mapping_smoothing = {}

    @staticmethod
    def _parse_soullink_mapping(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(str(raw or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _soullink_mapping_signature(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        try:
            return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return str(raw)

    @staticmethod
    def _mapping_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no", "off"}
        return bool(value)

    def _finite_number(self, value: Any, default: float = 0.0) -> float:
        number = self._number(value, default)
        return number if math.isfinite(number) else default

    def _soullink_status(self) -> dict[str, Any]:
        runtime = getattr(self, "_soullink_runtime", None)
        scheduler = getattr(self, "_vts_parameter_scheduler", None)
        command_vts = getattr(self, "vts", None)
        parameter_vts = getattr(self, "_parameter_vts", None)
        status = runtime.status() if runtime else {"running": False, "last_error": "运行时未初始化"}
        status.update(
            {
                "enabled": self._is_soullink_enabled(),
                "mode": self._soullink_mode(),
                "style": self._soullink_runtime_options()["style"],
                "prompt_intent": bool(self.config.get("soullink_prompt_intent_enabled", True)),
                "vts_parameters": list(getattr(self, "_soullink_last_vts_parameters", [])),
                "scheduler": scheduler.status() if scheduler else {},
                "vts": {
                    "connected": bool(getattr(command_vts, "is_authenticated", False)),
                    "realtime_connected": bool(
                        getattr(parameter_vts, "is_authenticated", False)
                    ),
                    "url": str(getattr(command_vts, "url", "") or ""),
                },
            }
        )
        return status

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _clamp_number(cls, value: Any, minimum: float, maximum: float, default: float) -> float:
        return max(minimum, min(maximum, cls._number(value, default)))
