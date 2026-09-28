# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any


class PageConfigManager:
    """拓展页配置读写与运行时同步。"""

    SENSITIVE_KEYS = frozenset(
        {
            "bilibili_sessdata",
            "laplace_event_bridge_token",
            "obs_ws_password",
        }
    )

    def __init__(self, plugin: Any, plugin_name: str, logger: Any) -> None:
        self.plugin = plugin
        self.plugin_name = plugin_name
        self.logger = logger

    def schema_payload(self) -> dict[str, Any]:
        schema = self.read_schema()
        keys = self.editable_keys()
        return {
            "schema": {key: schema.get(key, {}) for key in keys},
            "values": self.values(keys),
            "groups": self.groups(),
        }

    def summary(self) -> dict[str, Any]:
        return self.values(self.editable_keys())

    def values(self, keys: list[str]) -> dict[str, Any]:
        schema = self.read_schema()
        return {
            key: "" if key in self.SENSITIVE_KEYS else self.plugin.config.get(key, schema.get(key, {}).get("default"))
            for key in keys
        }

    def build_updates(self, values: dict[str, Any]) -> dict[str, Any]:
        schema = self.read_schema()
        editable_keys = set(self.editable_keys())
        updates: dict[str, Any] = {}
        for key, value in values.items():
            if key not in editable_keys or key not in schema:
                continue
            # The page never receives existing credentials. An empty value means
            # "keep the current credential", rather than clearing it by accident.
            if key in self.SENSITIVE_KEYS and not str(value or "").strip():
                continue
            updates[key] = self.coerce_value(value, schema[key])
        return updates

    async def apply_updates(self, updates: dict[str, Any]) -> bool:
        subtitle_before = self.subtitle_snapshot()
        stage_before = self.stage_snapshot()
        twitch_before = self.twitch_snapshot()
        for key, value in updates.items():
            self.plugin.config[key] = value
        persisted = await self.persist()
        await self.sync_runtime_after_change(subtitle_before, stage_before, twitch_before)
        return persisted

    def read_schema(self) -> dict[str, Any]:
        path = Path(__file__).with_name("_conf_schema.json")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            self.logger.warning(f"[B站直播] 读取配置 schema 失败: {exc}")
            return {}

    async def persist(self) -> bool:
        config = self.plugin.config
        for name in ("save", "save_config", "dump", "flush"):
            method = getattr(config, name, None)
            if not callable(method):
                continue
            try:
                result = method()
                if inspect.isawaitable(result):
                    await result
                return True
            except TypeError:
                continue
            except Exception as exc:
                self.logger.debug(f"[B站直播] 调用配置保存方法 {name} 失败: {exc}")

        path = Path(os.path.expanduser("~")) / ".astrbot" / "data" / "config" / f"{self.plugin_name}_config.json"
        try:
            existing: dict[str, Any] = {}
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    existing = loaded
            try:
                existing.update(dict(config))
            except Exception:
                existing.update(self.summary())
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(existing, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            return True
        except Exception as exc:
            self.logger.warning(f"[B站直播] 写入插件配置文件失败: {exc}")
            return False

    def subtitle_snapshot(self) -> dict[str, Any]:
        return {
            key: self.plugin.config.get(key)
            for key in self.editable_keys()
            if key.startswith("subtitle_")
        }

    def stage_snapshot(self) -> dict[str, Any]:
        return {
            key: self.plugin.config.get(key)
            for key in self.editable_keys()
            if key.startswith("soullink_") or key in {"mouth_sync_fps", "mouth_sync_mode"}
        }

    def twitch_snapshot(self) -> dict[str, Any]:
        return {
            key: self.plugin.config.get(key)
            for key in self.editable_keys()
            if key.startswith("twitch_")
        }

    async def sync_runtime_after_change(
        self,
        subtitle_before: dict[str, Any],
        stage_before: dict[str, Any],
        twitch_before: dict[str, Any] | None = None,
    ) -> None:
        subtitle_after = self.subtitle_snapshot()
        if subtitle_before != subtitle_after:
            server = getattr(self.plugin, "_subtitle_server", None)
            subtitle_enabled = bool(self.plugin.config.get("subtitle_enabled", False))
            if subtitle_enabled:
                if server is None:
                    await self.plugin._start_subtitle_server_if_enabled()
                else:
                    host = str(self.plugin.config.get("subtitle_host") or "127.0.0.1")
                    port = self._int(self.plugin.config.get("subtitle_port"), 18081)
                    if getattr(server, "host", "") != host or getattr(server, "port", 0) != port:
                        await self.plugin._stop_subtitle_server()
                        await self.plugin._start_subtitle_server_if_enabled()
                    else:
                        server.style = self.plugin._get_subtitle_style()
            elif server is not None:
                await self.plugin._stop_subtitle_server()

        if stage_before != self.stage_snapshot():
            await self.plugin._sync_soullink_runtime()

        if twitch_before is not None and twitch_before != self.twitch_snapshot():
            sync = getattr(self.plugin, "_sync_twitch_runtime", None)
            if callable(sync):
                try:
                    await sync()
                except Exception as exc:
                    self.logger.warning(f"[Twitch] 运行时同步失败: {exc}")

    @staticmethod
    def editable_keys() -> list[str]:
        return [
            "bilibili_enabled",
            "bilibili_type",
            "bilibili_room_id",
            "part_id",
            "area_id",
            "bilibili_web_backend",
            "laplace_event_bridge_url",
            "laplace_event_bridge_token",
            "bilibili_sessdata",
            "bili_live_inject_enabled",
            "bili_live_inject_max_events",
            "bili_live_cache_size",
            "bili_live_log_events",
            "bili_live_debug_log",
            "twitch_enabled",
            "twitch_channel",
            "twitch_auto_start",
            "twitch_live_cache_size",
            "twitch_live_log_events",
            "twitch_live_debug_log",
            "twitch_auto_reply_enabled",
            "twitch_auto_reply_session_id",
            "twitch_auto_reply_cooldown_seconds",
            "twitch_auto_reply_max_per_minute",
            "twitch_auto_reply_min_events",
            "twitch_auto_reply_max_events",
            "twitch_auto_reply_air_guard_enabled",
            "twitch_auto_reply_tts_enabled",
            "twitch_auto_reply_air_guard_threshold",
            "twitch_auto_reply_max_length",
            "twitch_auto_reply_system_prompt",
            "obs_control_enabled",
            "obs_exe_path",
            "l2dstudio_exe_path",
            "obs_ws_host",
            "obs_ws_port",
            "obs_ws_password",
            "obs_live_scene_name",
            "obs_startup_wait_seconds",
            "obs_debug_start_virtual_camera",
            "obs_allow_stream_start",
            "bili_live_auto_reply_enabled",
            "bili_live_auto_reply_mode",
            "bili_live_auto_reply_session_id",
            "bili_live_auto_reply_event_types",
            "bili_live_auto_reply_skip_emoticon_danmaku",
            "bili_live_auto_reply_guaranteed_event_types",
            "bili_live_auto_reply_cooldown_seconds",
            "bili_live_auto_reply_max_per_minute",
            "bili_live_auto_reply_rate_limit_exempt_event_types",
            "bili_live_auto_reply_min_events",
            "bili_live_auto_reply_max_events",
            "bili_live_auto_reply_air_guard_enabled",
            "bili_live_auto_reply_air_guard_model_enabled",
            "bili_live_auto_reply_air_guard_threshold",
            "bili_live_auto_reply_max_length",
            "bili_live_auto_reply_force_full_tts",
            "bili_live_auto_reply_sync_tts_subtitle",
            "live_tts_backend",
            "live_tts_external_tool_name",
            "live_tts_external_service_method",
            "live_tts_external_plugin_name",
            "live_tts_external_timeout_seconds",
            "live_tts_emotion_passthrough_enabled",
            "live_tts_style_hint_enabled",
            "bili_live_tts_local_playback_enabled",
            "bili_live_tts_web_playback_enabled",
            "bili_live_reply_identity_mode",
            "bili_live_streamer_identity_from_companion_enabled",
            "bili_live_streamer_display_name",
            "bili_live_auto_reply_system_prompt",
            "live_memory_enabled",
            "bilibili_ai_memory_integration_enabled",
            "bilibili_ai_memory_event_types",
            "live_memory_context_enabled",
            "live_memory_context_max_lines",
            "live_memory_max_items",
            "live_memory_topic_enabled",
            "live_memory_max_topics",
            "live_memory_max_open_threads",
            "live_memory_max_highlights",
            "private_companion_live_context_enabled",
            "private_companion_live_context_max_age_seconds",
            "private_companion_live_context_recent_limit",
            "private_companion_live_context_max_users",
            "private_companion_live_context_include_identity_note",
            "private_companion_relationship_style_context_enabled",
            "private_companion_relationship_style_include_profile",
            "private_companion_relationship_style_include_memories",
            "private_companion_writeback_enabled",
            "private_companion_viewer_activity_enabled",
            "private_companion_viewer_activity_context_enabled",
            "private_companion_auto_register_viewers",
            "private_companion_auto_register_min_events",
            "private_companion_live_state_enabled",
            "private_companion_live_state_cooldown_seconds",
            "private_companion_live_state_duration_hours",
            "private_companion_live_summary_enabled",
            "subtitle_enabled",
            "subtitle_scope",
            "subtitle_host",
            "subtitle_port",
            "subtitle_typing_speed_ms",
            "subtitle_hold_seconds",
            "subtitle_max_length",
            "subtitle_font_size",
            "subtitle_font_weight",
            "subtitle_text_color",
            "subtitle_stroke_color",
            "subtitle_stroke_size",
            "subtitle_cursor_color",
            "subtitle_show_cursor",
            "subtitle_fade_out",
            "subtitle_position",
            "subtitle_padding",
            "subtitle_max_width",
            "subtitle_strip_l2d_tags",
            "subtitle_strip_tts_blocks",
            "subtitle_voice_use_following_plain",
            "subtitle_prefer_chinese_text",
            "subtitle_use_tts_spoken_text",
            "subtitle_strip_html_tags",
            "mouth_sync_enabled",
            "mouth_sync_open_parameter",
            "mouth_sync_form_parameter",
            "mouth_sync_fps",
            "mouth_sync_gain",
            "mouth_sync_smoothing",
            "mouth_sync_noise_gate",
            "mouth_sync_form_strength",
            "mouth_sync_mode",
            "soullink_enabled",
            "soullink_mode",
            "soullink_motion_style",
            "soullink_fps",
            "soullink_prompt_intent_enabled",
            "soullink_local_fallback_enabled",
            "soullink_parameter_gain",
            "soullink_body_motion_gain",
            "soullink_vad_decay_rate",
            "soullink_node_path",
            "soullink_vts_mapping",
            "soullink_gaze_enabled",
        ]

    @staticmethod
    def groups() -> list[dict[str, Any]]:
        return [
            {
                "id": "live",
                "title": "直播监听",
                "description": "房间、后端和事件缓存。",
                "keys": [
                    "bilibili_enabled",
                    "bilibili_type",
                    "bilibili_room_id",
                    "part_id",
                    "area_id",
                    "bilibili_web_backend",
                    "laplace_event_bridge_url",
                    "laplace_event_bridge_token",
                    "bilibili_sessdata",
                    "bili_live_inject_enabled",
                    "bili_live_inject_max_events",
                    "bili_live_cache_size",
                    "bili_live_log_events",
                    "bili_live_debug_log",
                ],
            },
            {
                "id": "twitch",
                "title": "Twitch 直播",
                "description": "Twitch 频道监听、弹幕自动回应和字幕来源。",
                "keys": [
                    "twitch_enabled",
                    "twitch_channel",
                    "twitch_auto_start",
                    "twitch_live_cache_size",
                    "twitch_live_log_events",
                    "twitch_live_debug_log",
                    "twitch_auto_reply_enabled",
                    "twitch_auto_reply_session_id",
                    "twitch_auto_reply_cooldown_seconds",
                    "twitch_auto_reply_max_per_minute",
                    "twitch_auto_reply_min_events",
                    "twitch_auto_reply_max_events",
                    "twitch_auto_reply_air_guard_enabled",
                    "twitch_auto_reply_air_guard_threshold",
                    "twitch_auto_reply_max_length",
                    "twitch_auto_reply_system_prompt",
                ],
            },
            {
                "id": "obs",
                "title": "OBS 开播控制",
                "description": "启动 OBS/L2DStudio、连接 OBS WebSocket、调试场景和二次确认开播。",
                "keys": [
                    "obs_control_enabled",
                    "obs_exe_path",
                    "l2dstudio_exe_path",
                    "obs_ws_host",
                    "obs_ws_port",
                    "obs_ws_password",
                    "obs_live_scene_name",
                    "obs_startup_wait_seconds",
                    "obs_debug_start_virtual_camera",
                    "obs_allow_stream_start",
                ],
            },
            {
                "id": "reply",
                "title": "自动回应",
                "description": "触发频率、限流和提示词。",
                "keys": [
                    "bili_live_auto_reply_enabled",
                    "bili_live_auto_reply_mode",
                    "bili_live_auto_reply_session_id",
                    "bili_live_auto_reply_event_types",
                    "bili_live_auto_reply_skip_emoticon_danmaku",
                    "bili_live_auto_reply_guaranteed_event_types",
                    "bili_live_auto_reply_cooldown_seconds",
                    "bili_live_auto_reply_max_per_minute",
                    "bili_live_auto_reply_rate_limit_exempt_event_types",
                    "bili_live_auto_reply_min_events",
                    "bili_live_auto_reply_max_events",
                    "bili_live_auto_reply_air_guard_enabled",
                    "bili_live_auto_reply_air_guard_model_enabled",
                    "bili_live_auto_reply_air_guard_threshold",
                    "bili_live_auto_reply_max_length",
                    "bili_live_reply_identity_mode",
                    "bili_live_streamer_identity_from_companion_enabled",
                    "bili_live_streamer_display_name",
                    "bili_live_auto_reply_system_prompt",
                ],
            },
            {
                "id": "audio",
                "title": "直播语音（TTS）",
                "description": "B站和 Twitch 的语音生成、TTS 来源、外部服务与播放方式。",
                "keys": [
                    "bili_live_auto_reply_force_full_tts",
                    "twitch_auto_reply_tts_enabled",
                    "live_tts_backend",
                    "live_tts_external_tool_name",
                    "live_tts_external_service_method",
                    "live_tts_external_plugin_name",
                    "live_tts_external_timeout_seconds",
                    "live_tts_emotion_passthrough_enabled",
                    "live_tts_style_hint_enabled",
                    "bili_live_auto_reply_sync_tts_subtitle",
                    "bili_live_tts_local_playback_enabled",
                    "bili_live_tts_web_playback_enabled",
                ],
            },
            {
                "id": "memory",
                "title": "记忆与陪伴",
                "description": "直播专用记忆、关系网线索和下播小结。",
                "keys": [
                    "bilibili_ai_memory_integration_enabled",
                    "bilibili_ai_memory_event_types",
                    "live_memory_enabled",
                    "live_memory_context_enabled",
                    "live_memory_context_max_lines",
                    "live_memory_max_items",
                    "live_memory_topic_enabled",
                    "live_memory_max_topics",
                    "live_memory_max_open_threads",
                    "live_memory_max_highlights",
                    "private_companion_live_context_enabled",
                    "private_companion_live_context_max_age_seconds",
                    "private_companion_live_context_recent_limit",
                    "private_companion_live_context_max_users",
                    "private_companion_live_context_include_identity_note",
                    "private_companion_relationship_style_context_enabled",
                    "private_companion_relationship_style_include_profile",
                    "private_companion_relationship_style_include_memories",
                    "private_companion_writeback_enabled",
                    "private_companion_viewer_activity_enabled",
                    "private_companion_viewer_activity_context_enabled",
                    "private_companion_auto_register_viewers",
                    "private_companion_auto_register_min_events",
                    "private_companion_live_state_enabled",
                    "private_companion_live_state_cooldown_seconds",
                    "private_companion_live_state_duration_hours",
                    "private_companion_live_summary_enabled",
                ],
            },
            {
                "id": "subtitle",
                "title": "打字机字幕",
                "description": "OBS overlay 样式、清理规则和页面预览。",
                "keys": [
                    "subtitle_enabled",
                    "subtitle_scope",
                    "subtitle_host",
                    "subtitle_port",
                    "subtitle_typing_speed_ms",
                    "subtitle_hold_seconds",
                    "subtitle_max_length",
                    "subtitle_font_size",
                    "subtitle_font_weight",
                    "subtitle_text_color",
                    "subtitle_stroke_color",
                    "subtitle_stroke_size",
                    "subtitle_cursor_color",
                    "subtitle_show_cursor",
                    "subtitle_fade_out",
                    "subtitle_position",
                    "subtitle_padding",
                    "subtitle_max_width",
                    "subtitle_strip_l2d_tags",
                    "subtitle_strip_tts_blocks",
                    "subtitle_voice_use_following_plain",
                    "subtitle_prefer_chinese_text",
                    "subtitle_use_tts_spoken_text",
                    "subtitle_strip_html_tags",
                ],
            },
            {
                "id": "stage",
                "title": "Soullink 与嘴型",
                "description": "可选连续情绪表演引擎、VTS 参数映射和 TTS 嘴型。",
                "keys": [
                    "soullink_enabled",
                    "soullink_mode",
                    "soullink_motion_style",
                    "soullink_fps",
                    "soullink_prompt_intent_enabled",
                    "soullink_local_fallback_enabled",
                    "soullink_parameter_gain",
                    "soullink_body_motion_gain",
                    "soullink_vad_decay_rate",
                    "soullink_node_path",
                    "soullink_vts_mapping",
                    "soullink_gaze_enabled",
                    "mouth_sync_enabled",
                    "mouth_sync_open_parameter",
                    "mouth_sync_form_parameter",
                    "mouth_sync_fps",
                    "mouth_sync_gain",
                    "mouth_sync_smoothing",
                    "mouth_sync_noise_gate",
                    "mouth_sync_form_strength",
                    "mouth_sync_mode",
                ],
            },
        ]

    @staticmethod
    def coerce_value(value: Any, meta: dict[str, Any]) -> Any:
        value_type = str(meta.get("type") or "string")
        if value_type == "bool":
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "开启"}
            return bool(value)
        if value_type == "int":
            number = PageConfigManager._int(value, PageConfigManager._int(meta.get("default")))
            return int(PageConfigManager._clamp_by_slider(number, meta))
        if value_type == "float":
            number = PageConfigManager._float(value, PageConfigManager._float(meta.get("default")))
            return PageConfigManager._clamp_by_slider(number, meta)
        if value_type == "list":
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            return [item.strip() for item in str(value or "").split(",") if item.strip()]
        if value_type == "text":
            return str(value or "")
        return str(value or "")

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp_by_slider(value: float, meta: dict[str, Any]) -> float:
        slider = meta.get("slider") if isinstance(meta.get("slider"), dict) else {}
        if "min" in slider:
            value = max(value, PageConfigManager._float(slider.get("min"), value))
        if "max" in slider:
            value = min(value, PageConfigManager._float(slider.get("max"), value))
        return value

