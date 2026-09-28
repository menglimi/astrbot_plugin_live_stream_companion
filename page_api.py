# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from astrbot.api import logger
from quart import request

from .config_options import (
    build_external_tts_options,
    build_probe_targets,
    candidate_label,
    normalize_host_entries,
    subnet_hosts,
)
from .page_config import PageConfigManager
from .vts_discovery import scan_vts_hosts

PLUGIN_NAME = "astrbot_plugin_live_stream_companion"
PAGE_API_PREFIX = f"/{PLUGIN_NAME}/page"

# 单次扫描的地址上限，避免误操作扫出过大的网段
MAX_VTS_PROBE_HOSTS = 768


class LiveStreamCompanionPageApi:
    """AstrBot 插件拓展页面 API。"""

    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        self.config_manager = PageConfigManager(plugin, PLUGIN_NAME, logger)

    def register_routes(self) -> None:
        register = getattr(self.plugin.context, "register_web_api", None)
        if not callable(register):
            logger.debug("[B站直播] 当前 AstrBot 版本不支持拓展页 API 注册。")
            return
        routes = [
            ("/overview", self.get_overview, ["GET"], "Live Stream Companion overview"),
            ("/memory", self.get_memory, ["GET"], "Live Stream Companion live memory"),
            ("/config/schema", self.get_config_schema, ["GET"], "Live Stream Companion config schema"),
            ("/options/external-tts", self.get_external_tts_options, ["GET"], "Live Stream Companion external TTS services"),
            ("/options/vts-candidates", self.get_vts_candidates, ["GET"], "Live Stream Companion VTS candidates"),
            ("/config/save", self.save_config, ["POST"], "Live Stream Companion save config"),
            ("/subtitle/preview", self.preview_subtitle, ["POST"], "Live Stream Companion subtitle preview"),
            ("/soullink/status", self.get_soullink_status, ["GET"], "Soullink Emotion status"),
            ("/soullink/control", self.soullink_control, ["POST"], "Soullink Emotion control"),
            ("/soullink/gaze/status", self.get_soullink_gaze_status, ["GET"], "Soullink mouse gaze status"),
            ("/soullink/vts-parameters", self.get_soullink_vts_parameters, ["GET"], "Soullink VTS parameters"),
            ("/soullink/mapping", self.get_soullink_mapping, ["GET"], "Soullink advanced mapping"),
            ("/soullink/mapping/apply", self.apply_soullink_mapping, ["POST"], "Soullink mapping preview and save"),
            ("/control/start", self.start_live, ["POST"], "Live Stream Companion start live"),
            ("/control/stop", self.stop_live, ["POST"], "Live Stream Companion stop live"),
            ("/control/obs/status", self.get_obs_control_status, ["GET"], "Live Stream Companion OBS control status"),
            ("/control/obs/action", self.obs_control_action, ["POST"], "Live Stream Companion OBS control action"),
        ]
        for path, handler, methods, desc in routes:
            register(f"{PAGE_API_PREFIX}{path}", handler, methods, desc)

    async def get_overview(self) -> dict[str, Any]:
        try:
            plugin = self.plugin
            companion = plugin._get_private_companion_plugin()
            store = plugin._private_companion_live_state_store(companion) if companion else {}
            events = list(getattr(plugin, "_bili_events", []))
            session_events = list(getattr(plugin, "_bili_session_events", []))
            twitch_events = list(getattr(plugin, "_twitch_events", []))
            recent_events = [
                (item, "bilibili") for item in events[-20:]
            ] + [
                (item, "twitch") for item in twitch_events[-20:]
            ]
            recent_events.sort(
                key=lambda row: float(getattr(row[0], "ts", 0.0) or 0.0),
                reverse=True,
            )
            return self._ok(
                {
                    "plugin": {
                        "name": PLUGIN_NAME,
                        "display_name": "我会直播圈米养你",
                        "version": "1.8.1",
                    },
                    "live": self._live_summary(events, session_events),
                    "twitch": self._twitch_summary(twitch_events),
                    "obs_control": await self._obs_control_status(check_obs_ws=True),
                    "vts": self._vts_summary(),
                    "subtitle": self._subtitle_summary(),
                    "mouth_sync": self._mouth_sync_summary(),
                    "soullink": plugin._soullink_status(),
                    "auto_reply": self._auto_reply_summary(),
                    "companion": self._companion_summary(companion, store),
                    "memory": self._memory_summary(store),
                    "living_memory": plugin._living_memory_summary(),
                    "integration": self._integration_summary(companion, store),
                    "viewers": self._viewer_summary(store),
                    "recent_events": [
                        self._event_payload(item, platform=platform)
                        for item, platform in recent_events[:20]
                    ],
                    "config": self._config_summary(),
                }
            )
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页概览读取失败: {exc}")
            return self._error(str(exc))

    async def get_memory(self) -> dict[str, Any]:
        try:
            companion = self.plugin._get_private_companion_plugin()
            if companion is None:
                return self._ok({"available": False, "message": "未找到“我会永远陪着你”插件实例。"})
            store = self.plugin._private_companion_live_state_store(companion)
            return self._ok(
                {
                    "available": True,
                    "overview": self.plugin._format_live_memory_overview(companion, limit=12),
                    "memory": self._memory_summary(store, detailed=True),
                    "viewers": self._viewer_summary(store, limit=50),
                }
            )
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页记忆读取失败: {exc}")
            return self._error(str(exc))

    async def get_config_schema(self) -> dict[str, Any]:
        try:
            return self._ok(self.config_manager.schema_payload())
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页配置结构读取失败: {exc}")
            return self._error(str(exc))

    async def save_config(self) -> dict[str, Any]:
        try:
            payload = await request.get_json(silent=True) or {}
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            updates = self.config_manager.build_updates(values)
            if not updates:
                return self._ok({"message": "没有可保存的配置变更。", "values": self._config_summary()})

            persisted = await self.config_manager.apply_updates(updates)
            return self._ok(
                {
                    "message": "配置已保存。" if persisted else "配置已应用到当前运行实例，但未确认持久化。",
                    "persisted": persisted,
                    "values": self._config_summary(),
                }
            )
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页配置保存失败: {exc}")
            return self._error(str(exc))

    async def get_external_tts_options(self) -> dict[str, Any]:
        """列出可用的外部 TTS 注册服务，供拓展页渲染下拉选项。"""
        try:
            manager = self.plugin.context.get_llm_tool_manager()
        except Exception as exc:
            logger.warning(f"[B站直播] 读取 LLM 工具管理器失败: {exc}")
            return self._error(f"读取工具管理器失败：{exc}")
        tools = list(getattr(manager, "func_list", []) or [])
        described = build_external_tts_options(tools)
        services = [item for item in described if item.get("methods")]
        others = [item for item in described if not item.get("methods")]
        if not tools:
            logger.info("[B站直播] 外部 TTS 工具清单：LLM 工具管理器里目前没有已注册工具。")
        elif not services:
            logger.info(
                "[B站直播] 外部 TTS 工具清单：已注册 %d 个工具，但没有识别到带公开合成方法的服务（已回退列出全部工具）。",
                len(tools),
            )
        else:
            logger.info(
                "[B站直播] 外部 TTS 工具清单：已注册 %d 个工具，识别到 %d 个合成服务：%s",
                len(tools),
                len(services),
                ", ".join(item["tool"] for item in services[:5]),
            )
        config = getattr(self.plugin, "config", {}) or {}
        return self._ok(
            {
                # services: 能取到公开合成方法的工具；tools: 其余已注册工具（供手动选择）
                "services": services,
                "tools": others,
                "totalTools": len(tools),
                "resolvedTools": sum(1 for item in described if item.get("has_plugin")),
                "current": {
                    "tool": str(config.get("live_tts_external_tool_name", "") or ""),
                    "plugin": str(config.get("live_tts_external_plugin_name", "") or ""),
                    "method": str(
                        config.get("live_tts_external_service_method", "text_to_speech") or ""
                    ),
                },
            }
        )

    async def get_vts_candidates(self) -> dict[str, Any]:
        """探测本机 / 已配置地址 / 指定网段上的 VTS，作为 ``vts_host`` 下拉选项。"""
        config = getattr(self.plugin, "config", {}) or {}
        configured_host = str(config.get("vts_host", "") or "").strip()
        try:
            configured_port = int(config.get("vts_port") or 8001)
        except (TypeError, ValueError):
            configured_port = 8001
        args = getattr(request, "args", None)
        mode = str(args.get("mode") if args else "" or "quick").strip().lower()
        extra_hosts = normalize_host_entries(args.get("hosts") if args else "")
        explicit_subnet = str(args.get("subnet") if args else "" or "").strip()
        extra_subnets = [explicit_subnet] if explicit_subnet else []
        include_scan = mode == "scan" or bool(explicit_subnet) or bool(extra_hosts)
        plan = build_probe_targets(
            configured_host=configured_host,
            configured_port=configured_port,
            request_host=str(getattr(request, "host", "") or ""),
            extra_hosts=extra_hosts,
            extra_subnets=extra_subnets,
            include_scan=include_scan,
        )
        hosts = list(plan["hosts"])
        scanned_subnets: list[str] = []
        for subnet in plan["subnets"]:
            scanned_subnets.append(subnet)
            for host in subnet_hosts(subnet):
                if host not in hosts:
                    hosts.append(host)
        truncated = False
        if len(hosts) > MAX_VTS_PROBE_HOSTS:
            hosts = hosts[:MAX_VTS_PROBE_HOSTS]
            truncated = True
        try:
            found = await scan_vts_hosts(
                hosts,
                ports=plan["ports"],
                timeout=0.8 if include_scan else 1.5,
                concurrency=96,
            )
        except Exception as exc:
            logger.warning(f"[B站直播] VTS 地址探测失败: {exc}")
            return self._error(f"VTS 地址探测失败：{exc}")
        candidates = []
        for item in found:
            host = str(item.get("host", ""))
            port = int(item.get("port") or 8001)
            version = str(item.get("version", "") or "")
            candidates.append(
                {
                    "host": host,
                    "port": port,
                    "version": version,
                    "label": candidate_label(host, port, version),
                    "configured": host == configured_host and port == configured_port,
                }
            )
        return self._ok(
            {
                "mode": "scan" if include_scan else "quick",
                "candidates": candidates,
                "configured": {"host": configured_host, "port": configured_port},
                "scanned": {
                    "hosts": len(hosts),
                    "ports": plan["ports"],
                    "subnets": scanned_subnets,
                    "truncated": truncated,
                },
            }
        )

    async def preview_subtitle(self) -> dict[str, Any]:
        try:
            payload = await request.get_json(silent=True) or {}
            text = str(payload.get("text") or "谢谢喜欢，今天也一起把直播间热起来吧。")
            server = getattr(self.plugin, "_subtitle_server", None)
            if server is None:
                return self._ok(
                    {
                        "sent": False,
                        "message": "字幕服务未运行，已在页面内播放本地预览。",
                        "style": self.plugin._get_subtitle_style(),
                    }
                )
            await self.plugin._push_subtitle(text, source="preview")
            return self._ok(
                {
                    "sent": True,
                    "message": "已发送到字幕 overlay，同时页面内播放预览。",
                    "style": self.plugin._get_subtitle_style(),
                }
            )
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页字幕预览失败: {exc}")
            return self._error(str(exc))

    async def get_soullink_status(self) -> dict[str, Any]:
        try:
            return self._ok(self.plugin._soullink_status())
        except Exception as exc:
            logger.warning(f"[Soullink] 拓展页状态读取失败: {exc}")
            return self._error(str(exc))

    async def soullink_control(self) -> dict[str, Any]:
        payload = await request.get_json(silent=True) or {}
        action = self._single_line(payload.get("action"), 40)
        try:
            if action == "start":
                if not self.plugin._is_soullink_enabled():
                    return self._error("Soullink 尚未启用，请先在配置页开启并保存")
                success = await self.plugin._start_soullink_runtime()
                message = "Soullink 已启动。" if success else "Soullink 启动失败。"
            elif action == "stop":
                await self.plugin._stop_soullink_runtime()
                success = True
                message = "Soullink 已停止，原有 L2D 热键仍可使用。"
            elif action == "reset":
                runtime = getattr(self.plugin, "_soullink_runtime", None)
                success = bool(runtime and runtime.running and await runtime.reset())
                message = "情绪状态已回到中性。" if success else "Soullink 未运行。"
            elif action == "configure":
                runtime = getattr(self.plugin, "_soullink_runtime", None)
                if not runtime or not runtime.running:
                    return self._error("Soullink 未运行")
                style = self._single_line(payload.get("style"), 20)
                if style not in {"natural", "lively", "calm", "shy"}:
                    return self._error("未知动作风格")
                success = await runtime.configure(style=style)
                message = f"实时预览已切换到 {style} 风格。"
            elif action == "test":
                vad = payload.get("vad") if isinstance(payload.get("vad"), dict) else {}
                intent = {
                    "emotion": self._single_line(payload.get("emotion") or "happy", 40).lower(),
                    "variant": self._single_line(payload.get("variant"), 60),
                    "intensity": max(0.0, min(1.0, self._float(payload.get("intensity"), 0.8))),
                    "vad": {
                        "valence": max(-1.0, min(1.0, self._float(vad.get("valence"), 0.0))),
                        "arousal": max(-1.0, min(1.0, self._float(vad.get("arousal"), 0.0))),
                        "dominance": max(-1.0, min(1.0, self._float(vad.get("dominance"), 0.0))),
                    },
                    "contextTags": ["page_test_bench"],
                    "sourceMessage": "Soullink 实时测试台",
                }
                success = await self.plugin._test_soullink_intent(intent)
                message = f"已触发 {intent['emotion']} 表演。" if success else "Soullink 触发失败。"
            else:
                return self._error("未知 Soullink 控制动作")
            return self._ok(
                {
                    "success": success,
                    "message": message,
                    "status": self.plugin._soullink_status(),
                }
            )
        except Exception as exc:
            logger.warning(f"[Soullink] 拓展页控制失败: {exc}")
            return self._error(str(exc))

    async def get_soullink_gaze_status(self) -> dict[str, Any]:
        """鼠标视线追踪状态。"""
        try:
            return self._ok(self.plugin._soullink_gaze_status())
        except Exception as exc:
            logger.warning(f"[Soullink] 鼠标追踪状态读取失败: {exc}")
            return self._error(str(exc))

    async def get_soullink_vts_parameters(self) -> dict[str, Any]:
        try:
            catalog = await self._soullink_vts_catalog()
            if not catalog.get("connected"):
                return self._error("VTube Studio 未连接")
            return self._ok(
                {
                    **catalog,
                    "mapped": list(getattr(self.plugin, "_soullink_last_vts_parameters", [])),
                }
            )
        except Exception as exc:
            logger.warning(f"[Soullink] VTS 参数读取失败: {exc}")
            return self._error(str(exc))

    async def get_soullink_mapping(self) -> dict[str, Any]:
        try:
            mapping = self.plugin._soullink_mapping_editor_payload()
            catalog = await self._soullink_vts_catalog(allow_disconnected=True)
            mapping.update(catalog)
            mapping["validation"] = self._validate_soullink_mapping(
                mapping.get("activeMapping"),
                catalog.get("inputs", []),
                catalog.get("live2d", []),
            )
            return self._ok(mapping)
        except Exception as exc:
            logger.warning(f"[Soullink] 高级映射读取失败: {exc}")
            return self._error(str(exc))

    async def apply_soullink_mapping(self) -> dict[str, Any]:
        payload = await request.get_json(silent=True) or {}
        action = self._single_line(payload.get("action"), 30).lower()
        try:
            persisted = False
            catalog = await self._soullink_vts_catalog(
                allow_disconnected=True,
                refresh=False,
            )
            if action == "discard":
                self.plugin._clear_soullink_mapping_preview()
                message = "已撤销未保存的映射预览。"
            elif action == "reset":
                self.plugin._clear_soullink_mapping_preview()
                persisted = await self.config_manager.apply_updates(
                    {"soullink_vts_mapping": "{}"}
                )
                message = "已恢复跟随插件内置映射。"
            elif action in {"preview", "save"}:
                mapping = self.plugin._normalize_soullink_mapping(
                    payload.get("mapping"),
                    strict=True,
                )
                if action == "preview":
                    self.plugin._set_soullink_mapping_preview(mapping)
                    message = "高级映射预览已应用，120 秒内未保存会自动恢复。"
                else:
                    self.plugin._clear_soullink_mapping_preview()
                    serialized = json.dumps(
                        mapping,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    persisted = await self.config_manager.apply_updates(
                        {"soullink_vts_mapping": serialized}
                    )
                    message = "高级映射已保存。"
            else:
                return self._error("未知映射操作")

            mapping_payload = self.plugin._soullink_mapping_editor_payload()
            mapping_payload.update(catalog)
            mapping_payload["persisted"] = persisted
            mapping_payload["message"] = message
            mapping_payload["validation"] = self._validate_soullink_mapping(
                mapping_payload.get("activeMapping"),
                catalog.get("inputs", []),
                catalog.get("live2d", []),
            )
            return self._ok(mapping_payload)
        except Exception as exc:
            logger.warning(f"[Soullink] 高级映射操作失败: {exc}")
            return self._error(str(exc))

    async def _soullink_vts_catalog(
        self,
        *,
        allow_disconnected: bool = False,
        refresh: bool = True,
    ) -> dict[str, Any]:
        cached = getattr(self, "_soullink_catalog_cache", None)
        if (
            not refresh
            and isinstance(cached, dict)
            and time.monotonic() - self._float(cached.get("at")) < 30.0
            and bool(getattr(getattr(self.plugin, "vts", None), "is_authenticated", False))
        ):
            return cached.get("data", {})
        if not await self.plugin._check_and_reconnect():
            if allow_disconnected:
                return {
                    "connected": False,
                    "model": {},
                    "inputs": [],
                    "live2d": [],
                    "bindingsAvailable": False,
                }
            return {"connected": False}
        model_info, input_parameters, live2d_parameters = await asyncio.gather(
            self.plugin.vts.get_model_info(),
            self.plugin.vts.get_input_parameters(),
            self.plugin.vts.get_live2d_parameters(),
        )
        bindings = self._soullink_model_bindings(model_info)
        bindings_available = bool(bindings)
        enriched_inputs: list[dict[str, Any]] = []
        for item in input_parameters:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            enriched_inputs.append(
                {
                    **item,
                    "usedByModel": name in bindings if bindings_available else None,
                    "mappedOutputs": bindings.get(name, []),
                }
            )
        self.plugin._set_soullink_vts_input_catalog(enriched_inputs)
        catalog = {
            "connected": True,
            "model": {
                "loaded": bool(model_info.get("modelLoaded")),
                "id": str(model_info.get("modelID") or ""),
                "name": str(model_info.get("modelName") or ""),
                "vtsModelName": str(model_info.get("vtsModelName") or ""),
            },
            "inputs": enriched_inputs,
            "live2d": live2d_parameters,
            "bindingsAvailable": bindings_available,
        }
        self._soullink_catalog_cache = {"at": time.monotonic(), "data": catalog}
        return catalog

    def _soullink_model_bindings(
        self,
        model_info: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        vts_model_name = str(model_info.get("vtsModelName") or "").strip()
        model_id = str(model_info.get("modelID") or "").strip()
        if not vts_model_name:
            return {}
        cache = getattr(self, "_soullink_binding_cache", None)
        cache_key = f"{model_id}:{vts_model_name}"
        if isinstance(cache, dict) and cache.get("key") == cache_key:
            return cache.get("bindings", {})
        try:
            from .vts_discovery import get_install_info

            install_path = str(get_install_info().get("install_path") or "")
            models_root = (
                Path(install_path)
                / "VTube Studio_Data"
                / "StreamingAssets"
                / "Live2DModels"
            )
            model_path = next(models_root.glob(f"*/{vts_model_name}"), None)
            if model_path is None:
                return {}
            with model_path.open("r", encoding="utf-8") as handle:
                model_config = json.load(handle)
            settings = (
                model_config.get("ParameterSettings")
                if isinstance(model_config, dict)
                and isinstance(model_config.get("ParameterSettings"), list)
                else []
            )
            bindings: dict[str, list[dict[str, Any]]] = {}
            for setting in settings:
                if not isinstance(setting, dict):
                    continue
                input_name = str(setting.get("Input") or "").strip()
                output_name = str(setting.get("OutputLive2D") or "").strip()
                if not input_name or not output_name:
                    continue
                bindings.setdefault(input_name, []).append(
                    {
                        "id": output_name,
                        "inputMin": self._float(setting.get("InputRangeLower")),
                        "inputMax": self._float(setting.get("InputRangeUpper")),
                        "outputMin": self._float(setting.get("OutputRangeLower")),
                        "outputMax": self._float(setting.get("OutputRangeUpper")),
                        "smoothing": self._float(setting.get("Smoothing")),
                        "clampInput": bool(setting.get("ClampInput", False)),
                        "clampOutput": bool(setting.get("ClampOutput", False)),
                    }
                )
            self._soullink_binding_cache = {"key": cache_key, "bindings": bindings}
            return bindings
        except Exception as exc:
            logger.debug(f"[Soullink] 读取本地 VTS 模型映射失败: {exc}")
            return {}

    def _validate_soullink_mapping(
        self,
        mapping: Any,
        inputs: list[dict[str, Any]],
        live2d: list[dict[str, Any]],
    ) -> dict[str, Any]:
        rules = mapping.get("rules") if isinstance(mapping, dict) and isinstance(mapping.get("rules"), list) else []
        input_by_name = {
            str(item.get("name") or ""): item
            for item in inputs
            if isinstance(item, dict) and item.get("name")
        }
        live2d_names = {
            str(item.get("name") or "")
            for item in live2d
            if isinstance(item, dict) and item.get("name")
        }
        issues: list[dict[str, Any]] = []
        target_rules: dict[str, list[dict[str, Any]]] = {}
        active_count = 0
        for rule in rules:
            if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                continue
            active_count += 1
            rule_id = str(rule.get("id") or "")
            target = str(rule.get("target") or "")
            target_rules.setdefault(target, []).append(rule)
            if not target:
                issues.append({"ruleId": rule_id, "level": "error", "message": "缺少 VTS 目标输入"})
                continue
            input_meta = input_by_name.get(target)
            if input_meta is None:
                if target in live2d_names:
                    issues.append(
                        {
                            "ruleId": rule_id,
                            "level": "error",
                            "message": f"{target} 是 Live2D 输出，不能通过 VTS API 注入；当前会安全跳过",
                        }
                    )
                elif inputs:
                    issues.append(
                        {
                            "ruleId": rule_id,
                            "level": "warning",
                            "message": f"{target} 不在当前 VTS 输入目录；当前模型会跳过，可保留给其他模型或自定义输入",
                        }
                    )
                continue
            if input_meta.get("usedByModel") is False:
                issues.append(
                    {
                        "ruleId": rule_id,
                        "level": "warning",
                        "message": f"{target} 可写，但当前模型没有绑定任何 Live2D 输出",
                    }
                )
            input_min = self._float(input_meta.get("min"), -1000000.0)
            input_max = self._float(input_meta.get("max"), 1000000.0)
            output_values = [
                self._float(rule.get("outputMin")),
                self._float(rule.get("outputNeutral")),
                self._float(rule.get("outputMax")),
            ]
            if min(output_values) < input_min or max(output_values) > input_max:
                issues.append(
                    {
                        "ruleId": rule_id,
                        "level": "warning",
                        "message": f"输出锚点超出 {target} 的 VTS 范围 {input_min:g} ~ {input_max:g}",
                    }
                )
        for target, duplicates in target_rules.items():
            if target and len(duplicates) > 1 and all(
                str(item.get("blend") or "replace") == "replace" for item in duplicates[1:]
            ):
                issues.append(
                    {
                        "ruleId": str(duplicates[-1].get("id") or ""),
                        "level": "warning",
                        "message": f"{target} 被多条 replace 规则占用，最后一条会覆盖前面的值",
                    }
                )
        return {
            "activeRules": active_count,
            "errors": sum(1 for item in issues if item["level"] == "error"),
            "warnings": sum(1 for item in issues if item["level"] == "warning"),
            "issues": issues,
        }

    async def start_live(self) -> dict[str, Any]:
        try:
            payload = await request.get_json(silent=True) or {}
            room_id = self._int(payload.get("room_id")) or self.plugin._get_config_room_id()
            message = await self.plugin._start_bili_live(room_id)
            return self._ok({"message": message})
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页启动监听失败: {exc}")
            return self._error(str(exc))

    async def stop_live(self) -> dict[str, Any]:
        try:
            message = await self.plugin._stop_bili_live()
            return self._ok({"message": message})
        except Exception as exc:
            logger.warning(f"[B站直播] 拓展页停止监听失败: {exc}")
            return self._error(str(exc))

    async def get_obs_control_status(self) -> dict[str, Any]:
        try:
            return self._ok(await self._obs_control_status(check_obs_ws=True))
        except Exception as exc:
            logger.warning(f"[B站直播] OBS 控制状态读取失败: {exc}")
            return self._error(str(exc))

    async def obs_control_action(self) -> dict[str, Any]:
        payload = await request.get_json(silent=True) or {}
        action = self._single_line(payload.get("action"), 40)
        if not action:
            return self._error("缺少 OBS 控制动作")
        if not bool(self.plugin.config.get("obs_control_enabled", False)):
            return self._error("OBS 开播控制未启用")
        try:
            messages: list[str] = []
            if action == "open_obs":
                messages.append(self._start_configured_app("obs"))
            elif action == "open_l2dstudio":
                messages.append(self._start_configured_app("l2dstudio"))
            elif action == "start_apps":
                messages.append(self._start_configured_app("obs"))
                messages.append(self._start_configured_app("l2dstudio"))
            elif action == "check":
                pass
            elif action == "debug":
                messages.append(self._start_configured_app("obs"))
                messages.append(self._start_configured_app("l2dstudio"))
                wait_seconds = max(0, min(20, self._int(self.plugin.config.get("obs_startup_wait_seconds"), 3)))
                if wait_seconds:
                    await asyncio.sleep(wait_seconds)
                scene = self._single_line(self.plugin.config.get("obs_live_scene_name"), 120)
                if scene:
                    await self._obs_request("SetCurrentProgramScene", {"sceneName": scene})
                    messages.append(f"OBS 已切换到场景：{scene}")
                if bool(self.plugin.config.get("obs_debug_start_virtual_camera", True)):
                    try:
                        await self._obs_request("StartVirtualCam")
                        messages.append("OBS 虚拟摄像机已开启")
                    except Exception as exc:
                        messages.append(f"OBS 虚拟摄像机未重复开启：{self._single_line(exc, 80)}")
            elif action == "switch_scene":
                scene = self._single_line(payload.get("scene") or self.plugin.config.get("obs_live_scene_name"), 120)
                if not scene:
                    return self._error("未配置 OBS 场景名")
                await self._obs_request("SetCurrentProgramScene", {"sceneName": scene})
                messages.append(f"OBS 已切换到场景：{scene}")
            elif action == "start_virtual_camera":
                await self._obs_request("StartVirtualCam")
                messages.append("OBS 虚拟摄像机已开启")
            elif action == "stop_virtual_camera":
                await self._obs_request("StopVirtualCam")
                messages.append("OBS 虚拟摄像机已关闭")
            elif action == "start_record":
                await self._obs_request("StartRecord")
                messages.append("OBS 录制已开始")
            elif action == "stop_record":
                await self._obs_request("StopRecord")
                messages.append("OBS 录制已停止")
            elif action == "start_stream":
                if not bool(self.plugin.config.get("obs_allow_stream_start", False)):
                    return self._error("未允许从插件启动推流，请先开启“允许插件开始推流”")
                if not bool(payload.get("confirm")):
                    return self._error("开播需要二次确认")
                scene = self._single_line(payload.get("scene") or self.plugin.config.get("obs_live_scene_name"), 120)
                if scene:
                    await self._obs_request("SetCurrentProgramScene", {"sceneName": scene})
                    messages.append(f"OBS 已切换到场景：{scene}")
                await self._obs_request("StartStream")
                messages.append("OBS 推流已开始")
            elif action == "stop_stream":
                await self._obs_request("StopStream")
                messages.append("OBS 推流已停止")
            else:
                return self._error(f"未知 OBS 控制动作：{action}")
            return self._ok(
                {
                    "message": "；".join(item for item in messages if item) or "OBS 控制检查完成",
                    "obs_control": await self._obs_control_status(check_obs_ws=True),
                }
            )
        except Exception as exc:
            logger.warning(f"[B站直播] OBS 控制动作失败: {exc}")
            return self._error(str(exc))

    async def _obs_control_status(self, *, check_obs_ws: bool = True) -> dict[str, Any]:
        settings = self._obs_control_settings()
        obs_process = self._configured_app_process_status("obs")
        l2d_process = self._configured_app_process_status("l2dstudio")
        obs = {
            "configured": bool(settings.get("obs_exe_path")),
            "running": obs_process.get("running", False),
            "process": obs_process,
            "websocket": {
                "configured": bool(settings.get("obs_ws_host") and settings.get("obs_ws_port")),
                "connected": False,
                "error": "",
            },
            "current_scene": "",
            "streaming": False,
            "recording": False,
            "virtual_camera": False,
        }
        if check_obs_ws and obs["websocket"]["configured"] and obs["running"]:
            try:
                responses = await self._obs_requests(
                    [
                        ("GetVersion", {}),
                        ("GetCurrentProgramScene", {}),
                        ("GetStreamStatus", {}),
                        ("GetRecordStatus", {}),
                        ("GetVirtualCamStatus", {}),
                    ],
                    timeout=3.0,
                )
                obs["websocket"]["connected"] = True
                version = responses.get("GetVersion", {})
                obs["websocket"]["obs_version"] = self._single_line(version.get("obsVersion"), 40)
                obs["websocket"]["websocket_version"] = self._single_line(version.get("obsWebSocketVersion"), 40)
                scene = responses.get("GetCurrentProgramScene", {})
                obs["current_scene"] = self._single_line(scene.get("currentProgramSceneName"), 120)
                obs["streaming"] = bool((responses.get("GetStreamStatus", {}) or {}).get("outputActive"))
                obs["recording"] = bool((responses.get("GetRecordStatus", {}) or {}).get("outputActive"))
                obs["virtual_camera"] = bool((responses.get("GetVirtualCamStatus", {}) or {}).get("outputActive"))
            except Exception as exc:
                obs["websocket"]["error"] = self._single_line(exc, 180)
        return {
            "enabled": bool(self.plugin.config.get("obs_control_enabled", False)),
            "settings": settings,
            "obs": obs,
            "l2dstudio": {
                "configured": bool(settings.get("l2dstudio_exe_path")),
                "running": l2d_process.get("running", False),
                "process": l2d_process,
            },
            "safety": {
                "stream_start_allowed": bool(self.plugin.config.get("obs_allow_stream_start", False)),
                "stream_start_requires_confirm": True,
            },
        }

    def _obs_control_settings(self) -> dict[str, Any]:
        return {
            "obs_control_enabled": bool(self.plugin.config.get("obs_control_enabled", False)),
            "obs_exe_path": self._single_line(self.plugin.config.get("obs_exe_path"), 500),
            "l2dstudio_exe_path": self._single_line(self.plugin.config.get("l2dstudio_exe_path"), 500),
            "obs_ws_host": self._single_line(self.plugin.config.get("obs_ws_host") or "127.0.0.1", 120) or "127.0.0.1",
            "obs_ws_port": self._int(self.plugin.config.get("obs_ws_port"), 4455) or 4455,
            "obs_live_scene_name": self._single_line(self.plugin.config.get("obs_live_scene_name"), 120),
            "obs_startup_wait_seconds": max(0, min(20, self._int(self.plugin.config.get("obs_startup_wait_seconds"), 3))),
            "obs_debug_start_virtual_camera": bool(self.plugin.config.get("obs_debug_start_virtual_camera", True)),
            "obs_allow_stream_start": bool(self.plugin.config.get("obs_allow_stream_start", False)),
            "obs_ws_password_configured": bool(str(self.plugin.config.get("obs_ws_password") or "")),
        }

    def _configured_app_process_status(self, app: str) -> dict[str, Any]:
        raw_path = self._app_path(app)
        exe = Path(raw_path).expanduser() if raw_path else None
        name = exe.name if exe else ""
        exists = bool(exe and exe.exists())
        return {
            "path": str(exe) if exe else "",
            "name": name,
            "exists": exists,
            "running": self._process_name_running(name) if name else False,
        }

    def _app_path(self, app: str) -> str:
        if app == "obs":
            return str(self.plugin.config.get("obs_exe_path") or "").strip()
        if app == "l2dstudio":
            return str(self.plugin.config.get("l2dstudio_exe_path") or "").strip()
        return ""

    def _start_configured_app(self, app: str) -> str:
        raw_path = self._app_path(app)
        label = "OBS" if app == "obs" else "L2DStudio"
        if not raw_path:
            raise RuntimeError(f"未配置 {label} 程序路径")
        exe = Path(raw_path).expanduser()
        if not exe.exists():
            raise RuntimeError(f"{label} 程序不存在：{exe}")
        if self._process_name_running(exe.name):
            return f"{label} 已在运行"
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
        return f"{label} 已启动"

    @staticmethod
    def _process_name_running(name: str) -> bool:
        process_name = str(name or "").strip()
        if not process_name:
            return False
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return process_name.casefold() in (result.stdout or "").casefold()
            result = subprocess.run(["pgrep", "-f", process_name], capture_output=True, text=True, timeout=3)
            return result.returncode == 0
        except Exception:
            return False

    async def _obs_request(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        responses = await self._obs_requests([(request_type, request_data or {})], timeout=5.0)
        return responses.get(request_type, {})

    async def _obs_requests(self, requests: list[tuple[str, dict[str, Any]]], *, timeout: float = 5.0) -> dict[str, Any]:
        try:
            import websockets
        except Exception as exc:
            raise RuntimeError("缺少 websockets 依赖，无法连接 OBS WebSocket") from exc
        host = self._single_line(self.plugin.config.get("obs_ws_host") or "127.0.0.1", 120) or "127.0.0.1"
        port = self._int(self.plugin.config.get("obs_ws_port"), 4455) or 4455
        password = str(self.plugin.config.get("obs_ws_password") or "")
        uri = f"ws://{host}:{port}"
        responses: dict[str, Any] = {}
        try:
            connector = websockets.connect(uri, open_timeout=timeout, close_timeout=timeout)
        except TypeError:
            connector = websockets.connect(uri)
        async with connector as ws:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            hello_data = hello.get("d") if isinstance(hello, dict) else {}
            auth = hello_data.get("authentication") if isinstance(hello_data, dict) else None
            identify_data: dict[str, Any] = {"rpcVersion": 1}
            if isinstance(auth, dict):
                if not password:
                    raise RuntimeError("OBS WebSocket 需要密码")
                secret = base64.b64encode(hashlib.sha256((password + str(auth.get("salt", ""))).encode("utf-8")).digest()).decode()
                identify_data["authentication"] = base64.b64encode(
                    hashlib.sha256((secret + str(auth.get("challenge", ""))).encode("utf-8")).digest()
                ).decode()
            await ws.send(json.dumps({"op": 1, "d": identify_data}, ensure_ascii=False))
            while True:
                packet = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if packet.get("op") == 2:
                    break
                if packet.get("op") == 9:
                    raise RuntimeError(self._single_line(packet.get("d"), 180) or "OBS WebSocket 鉴权失败")
            for index, (request_type, request_data) in enumerate(requests):
                request_id = f"live-stream-companion-{int(time.time() * 1000)}-{index}"
                await ws.send(
                    json.dumps(
                        {
                            "op": 6,
                            "d": {
                                "requestType": request_type,
                                "requestId": request_id,
                                "requestData": request_data or {},
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                while True:
                    packet = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                    if packet.get("op") != 7:
                        continue
                    data = packet.get("d") if isinstance(packet.get("d"), dict) else {}
                    if data.get("requestId") != request_id:
                        continue
                    status = data.get("requestStatus") if isinstance(data.get("requestStatus"), dict) else {}
                    if not status.get("result", False):
                        comment = self._single_line(status.get("comment"), 180) or request_type
                        raise RuntimeError(f"OBS 请求失败：{comment}")
                    responses[request_type] = data.get("responseData") if isinstance(data.get("responseData"), dict) else {}
                    break
        return responses

    def _live_summary(self, events: list[Any], session_events: list[Any]) -> dict[str, Any]:
        plugin = self.plugin
        running = bool(plugin._is_bili_live_running())
        latest = events[-1] if events else None
        counts: dict[str, int] = {}
        viewers: dict[str, int] = {}
        for item in session_events:
            event_type = str(getattr(item, "event_type", "") or "")
            counts[event_type] = counts.get(event_type, 0) + 1
            username = plugin._single_line_text(getattr(item, "username", ""), 40)
            if username and username != "系统":
                viewers[username] = viewers.get(username, 0) + 1
        top_viewers = sorted(viewers.items(), key=lambda item: item[1], reverse=True)[:8]
        started = float(getattr(plugin, "_bili_session_started_at", 0.0) or 0.0)
        return {
            "enabled": bool(plugin._is_bili_live_enabled()),
            "running": running,
            "type": plugin._get_bili_live_type(),
            "backend": plugin._get_bili_web_backend(),
            "room_id": getattr(getattr(plugin, "_bili_live_client", None), "real_room_id", None) or plugin._get_config_room_id(),
            "cache_count": len(events),
            "session_count": len(session_events),
            "session_started_at": started,
            "duration_seconds": int(time.time() - started) if started else 0,
            "latest": self._event_payload(latest) if latest else None,
            "counts": counts,
            "top_viewers": [{"name": name, "count": count} for name, count in top_viewers],
            "last_error": getattr(getattr(plugin, "_bili_live_client", None), "last_error", "") or plugin._get_bili_live_task_error(),
        }

    def _twitch_summary(self, events: list[Any]) -> dict[str, Any]:
        plugin = self.plugin
        client = getattr(plugin, "_twitch_client", None)
        started = float(getattr(plugin, "_twitch_session_started_at", 0.0) or 0.0)
        now = time.time()
        marks = list(getattr(plugin, "_twitch_auto_reply_minute_marks", []))
        return {
            "enabled": bool(plugin._is_twitch_enabled()),
            "running": bool(plugin._is_twitch_live_running()),
            "connected": bool(plugin._is_twitch_connected()),
            "channel": getattr(plugin, "_twitch_channel_name", "") or plugin._get_twitch_channel(),
            "cache_count": len(events),
            "pending": len(getattr(plugin, "_twitch_pending_reply_events", [])),
            "session_started_at": started,
            "duration_seconds": int(now - started) if started else 0,
            "last_error": getattr(client, "last_error", "") if client else "",
            "auto_reply_enabled": bool(plugin.config.get("twitch_auto_reply_enabled", False)),
            "used_this_minute": len([item for item in marks if now - float(item) < 60]),
            "max_per_minute": self._int(plugin.config.get("twitch_auto_reply_max_per_minute"), 6),
        }

    def _vts_summary(self) -> dict[str, Any]:
        plugin = self.plugin
        return {
            "connected": bool(getattr(plugin, "_connected", False)),
            "url": getattr(getattr(plugin, "vts", None), "url", ""),
            "auto_connect": bool(plugin.config.get("auto_connect", True)),
            "auto_discover": bool(plugin.config.get("auto_discover", True)),
        }

    def _subtitle_summary(self) -> dict[str, Any]:
        server = getattr(self.plugin, "_subtitle_server", None)
        return {
            "enabled": bool(self.plugin.config.get("subtitle_enabled", False)),
            "running": server is not None,
            "url": getattr(server, "url", "") if server else "",
        }

    def _mouth_sync_summary(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.plugin.config.get("mouth_sync_enabled", False)),
            "fps": self._int(self.plugin.config.get("mouth_sync_fps"), 30),
            "parameter": str(self.plugin.config.get("mouth_sync_open_parameter") or "MouthOpen"),
        }

    def _auto_reply_summary(self) -> dict[str, Any]:
        marks = list(getattr(self.plugin, "_bili_auto_reply_minute_marks", []))
        now = time.time()
        recent_marks = [item for item in marks if now - float(item) < 60]
        return {
            "enabled": bool(self.plugin.config.get("bili_live_auto_reply_enabled", False)),
            "mode": str(self.plugin.config.get("bili_live_auto_reply_mode") or "native"),
            "identity_mode": self.plugin._bili_live_reply_identity_mode(),
            "identity_label": self.plugin._bili_live_reply_identity_label(),
            "streamer": self.plugin._bili_live_streamer_identity(),
            "pending": len(getattr(self.plugin, "_bili_pending_reply_events", [])),
            "cooldown_seconds": self._float(self.plugin.config.get("bili_live_auto_reply_cooldown_seconds"), 12.0),
            "max_per_minute": self._int(self.plugin.config.get("bili_live_auto_reply_max_per_minute"), 6),
            "used_this_minute": len(recent_marks),
            "last_reply_at": float(getattr(self.plugin, "_bili_last_auto_reply_at", 0.0) or 0.0),
            "exempt_event_types": list(self.plugin._bili_auto_reply_priority_types()),
            "skip_rich_danmaku": bool(
                self.plugin.config.get(
                    "bili_live_auto_reply_skip_emoticon_danmaku", True
                )
            ),
            "air_guard": bool(self.plugin.config.get("bili_live_auto_reply_air_guard_enabled", True)),
            "air_guard_model": bool(self.plugin.config.get("bili_live_auto_reply_air_guard_model_enabled", True)),
            "air_guard_threshold": self._float(self.plugin.config.get("bili_live_auto_reply_air_guard_threshold"), 2.5),
            "force_full_tts": bool(self.plugin.config.get("bili_live_auto_reply_force_full_tts", True)),
            "sync_tts_subtitle": bool(self.plugin.config.get("bili_live_auto_reply_sync_tts_subtitle", True)),
            "local_playback": bool(self.plugin.config.get("bili_live_tts_local_playback_enabled", True)),
        }

    def _companion_summary(self, companion: Any | None, store: dict[str, Any]) -> dict[str, Any]:
        return {
            "available": companion is not None,
            "context_enabled": bool(self.plugin.config.get("private_companion_live_context_enabled", True)),
            "writeback_enabled": bool(self.plugin.config.get("private_companion_writeback_enabled", True)),
            "viewer_activity_enabled": bool(self.plugin.config.get("private_companion_viewer_activity_enabled", True)),
            "summary_count": len(store.get("summaries") if isinstance(store.get("summaries"), list) else []),
        }

    def _integration_summary(self, companion: Any | None, store: dict[str, Any]) -> dict[str, Any]:
        living = self.plugin._living_memory_summary()
        subtitle_server = getattr(self.plugin, "_subtitle_server", None)
        checks = [
            {
                "id": "bili_live",
                "label": "B站监听",
                "ok": bool(self.plugin._is_bili_live_running()),
                "note": "正在接收直播事件" if self.plugin._is_bili_live_running() else "未运行",
            },
            {
                "id": "auto_reply",
                "label": "自动回应",
                "ok": bool(self.plugin.config.get("bili_live_auto_reply_enabled", False)),
                "note": str(self.plugin.config.get("bili_live_auto_reply_mode") or "native"),
            },
            {
                "id": "subtitle",
                "label": "打字机字幕",
                "ok": subtitle_server is not None,
                "note": getattr(subtitle_server, "url", "") if subtitle_server else "未运行",
            },
            {
                "id": "private_companion",
                "label": "陪伴插件",
                "ok": companion is not None,
                "note": "关系网/状态可用" if companion is not None else "未找到运行实例",
            },
            {
                "id": "live_memory",
                "label": "直播专用记忆",
                "ok": bool(self.plugin.config.get("live_memory_enabled", True)) and companion is not None,
                "note": f"{len(store.get('memory_items') if isinstance(store.get('memory_items'), list) else [])} 条可承接记忆",
            },
            {
                "id": "living_memory",
                "label": "LivingMemory",
                "ok": bool(living.get("ready")),
                "note": living.get("message") or "",
            },
        ]
        return {
            "checks": checks,
            "ok_count": sum(1 for item in checks if item.get("ok")),
            "total": len(checks),
        }

    def _memory_summary(self, store: dict[str, Any], detailed: bool = False) -> dict[str, Any]:
        memory_items = store.get("memory_items") if isinstance(store.get("memory_items"), list) else []
        highlights = store.get("highlight_events") if isinstance(store.get("highlight_events"), list) else []
        open_threads = store.get("open_threads") if isinstance(store.get("open_threads"), list) else []
        summaries = store.get("summaries") if isinstance(store.get("summaries"), list) else []
        topics = store.get("topic_memory") if isinstance(store.get("topic_memory"), dict) else {}
        topic_rows = []
        for topic, item in topics.items():
            if not isinstance(item, dict):
                continue
            topic_rows.append(
                {
                    "topic": str(topic),
                    "count": self._int(item.get("count")),
                    "last_seen": self._float(item.get("last_seen")),
                    "samples": item.get("samples") if isinstance(item.get("samples"), list) else [],
                }
            )
        topic_rows.sort(key=lambda item: (item["count"], item["last_seen"]), reverse=True)
        payload = {
            "enabled": bool(self.plugin.config.get("live_memory_enabled", True)),
            "context_enabled": bool(self.plugin.config.get("live_memory_context_enabled", True)),
            "memory_count": len(memory_items),
            "highlight_count": len(highlights),
            "topic_count": len(topic_rows),
            "open_thread_count": len(open_threads),
            "summary_count": len(summaries),
            "topics": topic_rows[:12],
            "recent_items": memory_items[:8],
            "highlights": highlights[:8],
            "open_threads": open_threads[:8],
            "summaries": list(reversed(summaries[-5:])),
        }
        if detailed:
            payload["all_recent_items"] = memory_items[:30]
        return payload

    def _viewer_summary(self, store: dict[str, Any], limit: int = 20) -> dict[str, Any]:
        activity = store.get("viewer_activity") if isinstance(store.get("viewer_activity"), dict) else {}
        rows = []
        for key, item in activity.items():
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "key": str(key),
                    "display_name": self._single_line(item.get("display_name") or item.get("live_username"), 40),
                    "live_username": self._single_line(item.get("live_username"), 40),
                    "user_id": self._single_line(item.get("user_id"), 40),
                    "total_events": self._int(item.get("total_events")),
                    "event_counts": item.get("event_counts") if isinstance(item.get("event_counts"), dict) else {},
                    "recent_danmaku": item.get("recent_danmaku") if isinstance(item.get("recent_danmaku"), list) else [],
                    "last_seen": self._float(item.get("last_seen")),
                }
            )
        rows.sort(key=lambda item: (item["total_events"], item["last_seen"]), reverse=True)
        observations = store.get("viewer_observations") if isinstance(store.get("viewer_observations"), dict) else {}
        return {
            "count": len(rows),
            "candidate_count": len(observations),
            "items": rows[:limit],
        }

    def _config_summary(self) -> dict[str, Any]:
        return self.config_manager.summary()

    def _event_payload(self, event: Any, *, platform: str = "") -> dict[str, Any]:
        if event is None:
            return {}
        raw = getattr(event, "raw", None)
        raw_platform = raw.get("platform") if isinstance(raw, dict) else ""
        return {
            "platform": str(platform or raw_platform or "bilibili"),
            "type": str(getattr(event, "event_type", "") or ""),
            "dm_type": self._int(getattr(event, "dm_type", 0)),
            "username": self._single_line(getattr(event, "username", ""), 60),
            "content": self._single_line(getattr(event, "content", ""), 180),
            "display": self._single_line(event.display_text() if hasattr(event, "display_text") else "", 220),
            "ts": self._float(getattr(event, "ts", 0.0)),
        }

    @staticmethod
    def _single_line(value: Any, limit: int = 120) -> str:
        text = " ".join(str(value or "").strip().split())
        if limit > 0 and len(text) > limit:
            return text[:limit].rstrip() + "..."
        return text

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
    def _ok(data: Any = None) -> dict[str, Any]:
        return {"success": True, "data": data, "ts": int(time.time())}

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"success": False, "error": str(message), "ts": int(time.time())}
