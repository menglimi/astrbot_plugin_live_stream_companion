import asyncio
import datetime
import json
import os
import tempfile
import time
import unittest
from collections import deque
from types import SimpleNamespace

from data.plugins.astrbot_plugin_live_stream_companion.bilibili_live import (
    LiveDanmakuEvent,
)
from data.plugins.astrbot_plugin_live_stream_companion.main import VTubeStudioPlugin
from data.plugins.astrbot_plugin_live_stream_companion.main import LiveStreamCompanionExtensionAPI
from data.plugins.astrbot_plugin_live_stream_companion.subtitle_server import SubtitleServer
from data.plugins.astrbot_plugin_live_stream_companion.vts_parameter_scheduler import (
    VTSParameterScheduler,
)
from data.plugins.astrbot_plugin_live_stream_companion.vts_client import (
    VTSClient,
    VTSRealtimeClient,
    VTSResponseError,
)


class _ActivityAPI:
    def __init__(self) -> None:
        self.requested_dates: list[str] = []

    def activity_overview(self, date: str = "") -> str:
        self.requested_dates.append(date)
        return f"activity:{date or 'today'}"


class LiveReplyRegressionTests(unittest.IsolatedAsyncioTestCase):
    def _plugin(self, **config):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = config
        plugin._bili_last_auto_reply_at = 0.0
        plugin._bili_pending_reply_events = deque()
        plugin._bili_processing_support_event_ids = set()
        plugin._bili_acknowledged_support_event_ids = set()
        return plugin

    async def test_minimum_event_wait_does_not_reschedule_itself(self):
        plugin = self._plugin(
            bili_live_auto_reply_min_events=2,
            bili_live_auto_reply_cooldown_seconds=1,
        )
        plugin._bili_pending_reply_events.append(
            LiveDanmakuEvent("danmaku", "viewer", "first")
        )
        scheduled = []
        plugin._schedule_bili_auto_reply = lambda: scheduled.append(True)

        await plugin._bili_auto_reply_worker()
        await asyncio.sleep(0)

        self.assertEqual(scheduled, [])
        self.assertEqual(len(plugin._bili_pending_reply_events), 1)
    async def test_events_arriving_during_reply_are_rescheduled(self):
        plugin = self._plugin(
            bili_live_auto_reply_min_events=1,
            bili_live_auto_reply_cooldown_seconds=1,
        )
        plugin._bili_pending_reply_events.append(
            LiveDanmakuEvent("danmaku", "viewer", "first")
        )
        scheduled = []

        async def reply(_events):
            plugin._bili_pending_reply_events.append(
                LiveDanmakuEvent("danmaku", "viewer", "second")
            )

        async def fallback(_events, **_kwargs):
            return True

        plugin._reply_to_bili_live_events = reply
        plugin._send_unacknowledged_bili_support_fallback = fallback
        plugin._schedule_bili_auto_reply = lambda: scheduled.append(True)

        await plugin._bili_auto_reply_worker()
        await asyncio.sleep(0)

        self.assertEqual(scheduled, [True])
        self.assertEqual(len(plugin._bili_pending_reply_events), 1)

    def test_each_super_chat_sender_must_be_thanked_in_the_same_clause(self):
        plugin = self._plugin()
        events = [
            LiveDanmakuEvent("super_chat", "Alice", "first", amount=30),
            LiveDanmakuEvent("super_chat", "Bob", "second", amount=50),
        ]

        result = plugin._ensure_bili_support_acknowledgement(
            "谢谢Alice的SC，Bob的问题我接着回答。", events
        )

        self.assertIn("谢谢Bob的50元SC", result)
        self.assertEqual(result.count("谢谢Alice"), 1)

    def test_group_thanks_are_not_duplicated(self):
        plugin = self._plugin()
        events = [
            LiveDanmakuEvent("super_chat", "Alice", "first"),
            LiveDanmakuEvent("super_chat", "Bob", "second"),
        ]

        result = plugin._ensure_bili_support_acknowledgement(
            "谢谢Alice和Bob的SC！", events
        )

        self.assertEqual(result, "谢谢Alice和Bob的SC！")

    def test_recent_activity_reads_three_calendar_days(self):
        plugin = self._plugin(bilibili_ai_memory_integration_enabled=True)
        api = _ActivityAPI()
        plugin._get_bilibili_ai_bot_api = lambda: api

        context = plugin._build_bilibili_ai_self_activity_context(
            [LiveDanmakuEvent("danmaku", "viewer", "你最近看了什么？")]
        )

        today = datetime.date.today()
        expected = [
            (today - datetime.timedelta(days=offset)).isoformat()
            for offset in range(3)
        ]
        self.assertEqual(api.requested_dates, expected)
        self.assertIn("活动范围：最近三天", context)
        for date in expected:
            self.assertIn(date, context)

    def test_vts_command_fallback_keeps_current_chat_context(self):
        plugin = self._plugin()
        event = SimpleNamespace(message_str="/vts_auth")
        request = SimpleNamespace(system_prompt="base")

        plugin._inject_vts_command_fallback_instruction(event, request)

        self.assertIn("本次 AstrBot 会话", request.system_prompt)
        self.assertIn("不要声称用户必须去 QQ", request.system_prompt)

    def test_vts_command_fallback_ignores_normal_chat(self):
        plugin = self._plugin()
        event = SimpleNamespace(message_str="怎么认证 VTS？")
        request = SimpleNamespace(system_prompt="base")

        plugin._inject_vts_command_fallback_instruction(event, request)

        self.assertEqual(request.system_prompt, "base")

    def test_native_live_reply_keeps_danmaku_prompt_clean(self):
        plugin = self._plugin(
            bili_live_auto_reply_system_prompt="自定义主播人格",
            bili_live_auto_reply_force_full_tts=True,
            soullink_enabled=True,
            soullink_prompt_intent_enabled=True,
        )
        events = [LiveDanmakuEvent("danmaku", "Alice", "今天画什么？")]
        formatted = plugin._format_bili_events(events)

        prompt, system_prompt = plugin._build_bili_live_framework_prompt_parts(
            events,
            formatted,
            auxiliary_context="辅助上下文",
            living_context="长期记忆",
        )
        request = SimpleNamespace(system_prompt=system_prompt)
        plugin._inject_soullink_prompt_instruction(request)

        self.assertEqual(prompt, formatted)
        self.assertNotIn("自定义主播人格", prompt)
        self.assertNotIn("辅助上下文", prompt)
        self.assertNotIn("Soullink 实时表演", prompt)
        self.assertIn("自定义主播人格", request.system_prompt)
        self.assertIn("辅助上下文", request.system_prompt)
        self.assertIn("长期记忆", request.system_prompt)
        self.assertIn("Soullink 实时表演", request.system_prompt)


class ExternalCompanionAPITests(unittest.IsolatedAsyncioTestCase):
    def test_together_subtitle_is_allowed_while_bili_live_is_running(self):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = {"subtitle_scope": "bili_live"}
        plugin._is_bili_live_running = lambda: True

        self.assertTrue(plugin._source_should_push_subtitle("together_companion"))

    async def test_external_subtitle_uses_existing_subtitle_pipeline(self):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = {"subtitle_enabled": True}
        received = []

        async def push(text, *, source=""):
            received.append((text, source))

        plugin._push_subtitle = push
        api = LiveStreamCompanionExtensionAPI(plugin)

        pushed = await api.push_external_subtitle("一起看吧", source="together_companion")

        self.assertTrue(pushed)
        self.assertEqual([("一起看吧", "together_companion")], received)

    async def test_external_mouth_sync_tasks_can_be_stopped_by_source(self):
        plugin = object.__new__(VTubeStudioPlugin)
        blocker = asyncio.create_task(asyncio.Event().wait())
        plugin._external_mouth_sync_tasks = {"together:room": {blocker}}
        api = LiveStreamCompanionExtensionAPI(plugin)

        stopped = await api.stop_external_mouth_sync(source="together:room")

        self.assertEqual(1, stopped)
        self.assertTrue(blocker.cancelling())
        with self.assertRaises(asyncio.CancelledError):
            await blocker


class ExternalLiveTtsTests(unittest.IsolatedAsyncioTestCase):
    def _plugin(self, **config):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = config
        return plugin

    async def test_registered_service_uses_plugin_method_not_tool_handler(self):
        class VoiceService:
            plugin_id = "astrbot_plugin_demo_tts"

            async def text_to_speech(self, text, *, session_id=""):
                return f"{session_id}:{text}.wav"

        service = VoiceService()
        handler_calls = []

        async def tool_handler(*_args, **_kwargs):
            handler_calls.append(True)
            return "should-not-run.wav"

        tool = SimpleNamespace(handler=tool_handler)
        manager = SimpleNamespace(get_tool=lambda name: tool if name == "demo_tts_tool" else None)
        plugin = self._plugin(
            live_tts_external_tool_name="demo_tts_tool",
            live_tts_external_service_method="text_to_speech",
            live_tts_external_plugin_name="astrbot_plugin_demo_tts",
        )
        plugin.context = SimpleNamespace(get_llm_tool_manager=lambda: manager)

        # A partial is a common AstrBot tool registration shape.
        import functools

        tool.handler = functools.partial(tool_handler, service)
        found = plugin._find_live_tts_registered_service()

        self.assertIs(found, service)
        self.assertEqual(
            await plugin._synthesize_live_tts_with_registered_service(found, "hello", "live:1"),
            "live:1:hello.wav",
        )
        self.assertEqual(handler_calls, [])

    def test_registered_service_rejects_wrong_plugin_name(self):
        class VoiceService:
            plugin_id = "another_plugin"

            async def text_to_speech(self, text):
                return text

        service = VoiceService()
        tool = SimpleNamespace(handler=__import__("functools").partial(lambda _service: None, service))
        manager = SimpleNamespace(get_tool=lambda _name: tool)
        plugin = self._plugin(
            live_tts_external_tool_name="demo_tts_tool",
            live_tts_external_service_method="text_to_speech",
            live_tts_external_plugin_name="astrbot_plugin_demo_tts",
        )
        plugin.context = SimpleNamespace(get_llm_tool_manager=lambda: manager)

        self.assertIsNone(plugin._find_live_tts_registered_service())

    def test_registered_service_accepts_plugin_id_from_metadata(self):
        class VoiceService:
            metadata = SimpleNamespace(name="astrbot_plugin_demo_tts")

            async def text_to_speech(self, text):
                return text

        service = VoiceService()
        tool = SimpleNamespace(handler=__import__("functools").partial(lambda _service: None, service))
        manager = SimpleNamespace(get_tool=lambda _name: tool)
        plugin = self._plugin(
            live_tts_external_tool_name="demo_tts_tool",
            live_tts_external_service_method="text_to_speech",
            live_tts_external_plugin_name="astrbot_plugin_demo_tts",
        )
        plugin.context = SimpleNamespace(get_llm_tool_manager=lambda: manager)

        self.assertIs(plugin._find_live_tts_registered_service(), service)

    async def test_external_tts_accepts_path_mapping_and_invalid_timeout(self):
        class VoiceService:
            async def render_pcm_wav(self, text, *, session_id=""):
                return {"path": f"{session_id}-{text}.wav"}

        plugin = self._plugin(
            live_tts_external_service_method="render_pcm_wav",
            live_tts_external_timeout_seconds="not-a-number",
        )

        self.assertEqual(
            await plugin._synthesize_live_tts_with_registered_service(
                VoiceService(), "hello", "live:2"
            ),
            "live:2-hello.wav",
        )

    async def test_auto_backend_falls_back_to_session_provider_when_external_returns_empty(self):
        class ExternalService:
            async def text_to_speech(self, _text):
                return ""

        class SessionProvider:
            def __init__(self):
                self.calls = []

            async def get_audio(self, text):
                self.calls.append(text)
                return "fallback.wav"

        provider = SessionProvider()
        plugin = self._plugin(live_tts_backend="auto")
        plugin._find_live_tts_registered_service = lambda: ExternalService()
        plugin._get_live_tts_provider = lambda _session_id: provider
        plugin._strip_tts_blocks_from_text = lambda text: text
        plugin._convert_bili_live_tts_spoken_text = (
            lambda _session_id, text, _service: asyncio.sleep(0, result=text)
        )
        plugin._sanitize_bili_live_tts_spoken_text = lambda text, **_kwargs: text
        plugin._prepare_bili_live_audio_for_record = lambda path: path
        plugin._build_bili_live_tts_subtitle_text = lambda **_kwargs: "subtitle"
        plugin._schedule_bili_live_tts_local_playback = lambda _path: None
        plugin._bili_live_tts_web_playback_enabled = lambda: False
        plugin._after_bili_live_tts_audio_generated = lambda *_args, **_kwargs: asyncio.sleep(0)
        plugin._companion_tts_live_subtitle_enabled = lambda: True

        payload = await plugin._build_bili_live_tts_payload(
            "live:3", "hello", schedule_local_playback=False
        )

        self.assertEqual(provider.calls, ["hello"])
        self.assertEqual(payload["source_audio_path"], "fallback.wav")


class SubtitleServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_registration_requires_running_server_and_real_file(self):
        server = SubtitleServer("127.0.0.1", 0, {})
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as audio:
            audio.write(b"RIFF-test")
            audio_path = audio.name
        try:
            self.assertFalse(await server.register_audio("before-start", audio_path))
            await server.start()
            sent = []

            async def broadcast(payload):
                sent.append(payload)

            server._broadcast = broadcast
            self.assertTrue(await server.register_audio("audio-token", audio_path))
            self.assertEqual(sent, [{"type": "audio", "token": "audio-token"}])
            self.assertEqual(server._audio_files["audio-token"], os.path.abspath(audio_path))
            self.assertFalse(await server.register_audio("directory", os.path.dirname(audio_path)))
            self.assertIn("/audio/", server._render_html())
            self.assertIn("ttsAudio.play", server._render_html())
        finally:
            await server.stop()
            os.unlink(audio_path)


class SoullinkIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _plugin(self, **config):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = config
        plugin._soullink_tasks = set()
        plugin._soullink_last_vts_parameters = []
        return plugin

    def test_prompt_instruction_is_optional(self):
        disabled = self._plugin(soullink_enabled=False)
        request = SimpleNamespace(system_prompt="base")
        disabled._inject_soullink_prompt_instruction(request)
        self.assertEqual(request.system_prompt, "base")

        enabled = self._plugin(
            soullink_enabled=True,
            soullink_prompt_intent_enabled=True,
        )
        enabled._inject_soullink_prompt_instruction(request)
        self.assertIn("Soullink 实时表演", request.system_prompt)
        self.assertIn("不要为了触发表演改变正文", request.system_prompt)
        self.assertIn("不要把用户的情绪", request.system_prompt)
        self.assertIn("别难过", request.system_prompt)

    def test_soullink_tag_is_parsed_and_removed(self):
        plugin = self._plugin(soullink_enabled=True)
        intent, cleaned = plugin._parse_soullink_intent(
            '今天真的很开心！\n<soullink>{"emotion":"happy",'
            '"intensity":0.82,"vad":{"valence":0.75,'
            '"arousal":0.5,"dominance":0.3}}</soullink>'
        )

        self.assertEqual(cleaned, "今天真的很开心！")
        self.assertEqual(intent["emotion"], "happy")
        self.assertEqual(intent["intensity"], 0.82)
        self.assertEqual(intent["vad"]["valence"], 0.75)

    def test_soullink_frame_maps_to_vts_inputs(self):
        plugin = self._plugin(soullink_enabled=True, soullink_vts_mapping="{}")
        parameters = plugin._map_soullink_frame_to_vts(
            {
                "facs": {
                    "headX": 0.5,
                    "headY": -0.25,
                    "headZ": 0.1,
                    "gazeX": 0.2,
                    "gazeY": -0.1,
                    "eyeOpen": 0.9,
                    "mouthSmile": 0.6,
                    "browInnerUp": 0.4,
                    "browOuterUp": 0.2,
                    "browDown": 0.1,
                }
            }
        )
        values = {item["id"]: item["value"] for item in parameters}

        self.assertEqual(values["FaceAngleX"], 18.0)
        self.assertEqual(values["FaceAngleY"], -8.0)
        self.assertAlmostEqual(values["EyeLeftX"], 0.18)
        self.assertAlmostEqual(values["Brows"], 0.605)
        self.assertAlmostEqual(values["MouthSmile"], 0.9592)
        self.assertAlmostEqual(values["EyeOpenLeft"], 0.4736835)

    def test_soullink_neutral_frame_uses_model_tracking_neutral_points(self):
        plugin = self._plugin(soullink_enabled=True, soullink_vts_mapping="{}")

        parameters = plugin._map_soullink_frame_to_vts(
            {
                "live2dParams": {
                    "eyeOpen": 1.0,
                    "mouthSmile": 0.04,
                    "mouthFrown": 0.0,
                    "browInnerUp": 0.0,
                    "browOuterUp": 0.0,
                    "browDown": 0.0,
                }
            }
        )
        values = {item["id"]: item["value"] for item in parameters}

        self.assertAlmostEqual(values["Brows"], 0.5)
        self.assertAlmostEqual(values["MouthSmile"], 0.78)
        self.assertAlmostEqual(values["EyeOpenLeft"], 0.526315)
        self.assertAlmostEqual(values["EyeOpenRight"], 0.526315)

    def test_soullink_prefers_smoothed_params_and_mixes_body_motion(self):
        plugin = self._plugin(soullink_enabled=True, soullink_vts_mapping="{}")

        parameters = plugin._map_soullink_frame_to_vts(
            {
                "facs": {"headX": -0.8, "bodyX": 0.0},
                "live2dParams": {
                    "headX": 0.04,
                    "bodyX": 0.06,
                    "eyeOpen": 1.0,
                    "mouthSmile": 0.04,
                },
            }
        )
        values = {item["id"]: item["value"] for item in parameters}

        self.assertAlmostEqual(values["FaceAngleX"], (0.04 + 0.06 * 0.65) * 36)

    def test_soullink_blink_reaches_individual_eye_inputs(self):
        plugin = self._plugin(soullink_enabled=True, soullink_vts_mapping="{}")

        parameters = plugin._map_soullink_frame_to_vts(
            {
                "live2dParams": {
                    "eyeOpen": 1.0,
                    "eyeBlinkL": 1.0,
                    "eyeBlinkR": 0.25,
                    "mouthSmile": 0.04,
                }
            }
        )
        values = {item["id"]: item["value"] for item in parameters}

        self.assertEqual(values["EyeOpenLeft"], 0.0)
        self.assertAlmostEqual(values["EyeOpenRight"], 0.75 * 0.526315)

    def test_legacy_mapping_keeps_negative_scale_and_weight(self):
        plugin = self._plugin(
            soullink_enabled=True,
            soullink_vts_mapping=json.dumps(
                {
                    "headX": {
                        "id": "FaceAngleX",
                        "scale": -2.0,
                        "offset": 1.0,
                        "min": -3.0,
                        "max": 4.0,
                        "weight": 0.4,
                    }
                }
            ),
        )

        parameters = plugin._map_soullink_frame_to_vts(
            {"facs": {"headX": 0.5}}
        )

        self.assertEqual(parameters[0]["id"], "FaceAngleX")
        self.assertAlmostEqual(parameters[0]["value"], 0.0)
        self.assertAlmostEqual(parameters[0]["weight"], 0.4)

    def test_advanced_mapping_supports_asymmetric_three_point_curve(self):
        mapping = {
            "version": 2,
            "rules": [
                {
                    "id": "mouth-asymmetric",
                    "source": "mouthShape",
                    "target": "MouthSmile",
                    "sourceMin": -1.0,
                    "sourceNeutral": 0.0,
                    "sourceMax": 0.5,
                    "outputMin": 0.2,
                    "outputNeutral": 0.78,
                    "outputMax": 1.0,
                    "curve": 1.0,
                }
            ],
        }
        plugin = self._plugin(
            soullink_enabled=True,
            soullink_vts_mapping=json.dumps(mapping),
        )

        positive = plugin._map_soullink_frame_to_vts(
            {"facs": {"mouthSmile": 0.54}}
        )
        negative = plugin._map_soullink_frame_to_vts(
            {"facs": {"mouthSmile": 0.04, "mouthFrown": 0.5}}
        )

        self.assertAlmostEqual(positive[0]["value"], 1.0)
        self.assertAlmostEqual(negative[0]["value"], 0.49)

    def test_advanced_mapping_can_add_multiple_sources_to_one_target(self):
        mapping = {
            "version": 2,
            "rules": [
                {
                    "id": "head",
                    "source": "headX",
                    "target": "FaceAngleX",
                    "sourceMin": -1,
                    "sourceNeutral": 0,
                    "sourceMax": 1,
                    "outputMin": -1,
                    "outputNeutral": 0,
                    "outputMax": 1,
                },
                {
                    "id": "body",
                    "source": "bodyX",
                    "target": "FaceAngleX",
                    "sourceMin": -1,
                    "sourceNeutral": 0,
                    "sourceMax": 1,
                    "outputMin": -2,
                    "outputNeutral": 0,
                    "outputMax": 2,
                    "blend": "add",
                },
            ],
        }
        plugin = self._plugin(
            soullink_enabled=True,
            soullink_vts_mapping=json.dumps(mapping),
        )

        parameters = plugin._map_soullink_frame_to_vts(
            {"facs": {"headX": 0.5, "bodyX": 0.25}}
        )

        self.assertAlmostEqual(parameters[0]["value"], 1.0)

    def test_advanced_mapping_exposes_vad_sources_and_skips_invalid_vts_input(self):
        mapping = {
            "version": 2,
            "rules": [
                {
                    "id": "valence",
                    "source": "vadValence",
                    "target": "CustomMood",
                    "sourceMin": -1,
                    "sourceNeutral": 0,
                    "sourceMax": 1,
                    "outputMin": -1,
                    "outputNeutral": 0,
                    "outputMax": 1,
                }
            ],
        }
        plugin = self._plugin(
            soullink_enabled=True,
            soullink_vts_mapping=json.dumps(mapping),
        )
        plugin._set_soullink_vts_input_catalog([{"name": "FaceAngleX"}])

        parameters = plugin._map_soullink_frame_to_vts(
            {
                "facs": {"headX": 0.0},
                "vad": {"current": {"valence": 0.75}, "intensity": 0.6},
            }
        )

        self.assertEqual(parameters, [])
        payload = plugin._soullink_mapping_editor_payload()
        self.assertIn("vadValence", {item["id"] for item in payload["sources"]})

    def test_advanced_mapping_strict_validation_rejects_inverted_source_range(self):
        plugin = self._plugin(soullink_enabled=True, soullink_vts_mapping="{}")

        with self.assertRaisesRegex(ValueError, "源范围"):
            plugin._normalize_soullink_mapping(
                {
                    "version": 2,
                    "rules": [
                        {
                            "source": "headX",
                            "target": "FaceAngleX",
                            "sourceMin": 1,
                            "sourceNeutral": 0,
                            "sourceMax": -1,
                        }
                    ],
                },
                strict=True,
            )

    async def test_parameter_scheduler_merges_layers_with_mouth_priority(self):
        scheduler = VTSParameterScheduler(
            SimpleNamespace(),
            lambda: asyncio.sleep(0, result=True),
        )
        scheduler.set_layer(
            "soullink",
            [
                {"id": "MouthSmile", "value": 0.7},
                {"id": "FaceAngleX", "value": 12.0},
            ],
        )
        scheduler.set_layer("mouth", [{"id": "MouthSmile", "value": 0.2}])

        values = {item["id"]: item["value"] for item in scheduler.merged_parameters()}

        self.assertEqual(values["MouthSmile"], 0.2)
        self.assertEqual(values["FaceAngleX"], 12.0)

    async def test_parameter_scheduler_throttles_offline_reconnects(self):
        attempts = []

        async def ensure_connection():
            attempts.append(True)
            return False

        scheduler = VTSParameterScheduler(
            SimpleNamespace(is_connected=False),
            ensure_connection,
        )
        scheduler.set_layer("soullink", [{"id": "FaceAngleX", "value": 12.0}])

        self.assertFalse(await scheduler.flush())
        self.assertFalse(await scheduler.flush())

        self.assertEqual(attempts, [True])
        self.assertEqual(scheduler.status()["connection_error"], "VTube Studio 未连接")

    async def test_parameter_scheduler_uses_only_active_source_fps(self):
        scheduler = VTSParameterScheduler(
            SimpleNamespace(),
            lambda: asyncio.sleep(0, result=True),
            fps=20,
        )
        scheduler.set_source_fps("soullink", 20)
        scheduler.set_layer("soullink", [{"id": "FaceAngleX", "value": 1.0}])
        scheduler.set_source_fps("mouth", 30)

        self.assertEqual(scheduler.effective_fps(), 20)

        scheduler.set_layer("mouth", [{"id": "MouthOpen", "value": 0.5}])
        self.assertEqual(scheduler.effective_fps(), 30)

        scheduler.clear_layer("mouth")
        self.assertEqual(scheduler.effective_fps(), 20)

    async def test_parameter_scheduler_drops_stale_realtime_layer(self):
        scheduler = VTSParameterScheduler(
            SimpleNamespace(),
            lambda: asyncio.sleep(0, result=True),
        )
        scheduler.set_layer(
            "soullink",
            [{"id": "FaceAngleX", "value": 1.0}],
            ttl=0.1,
        )
        scheduler._layer_updated_at["soullink"] = time.monotonic() - 0.2

        self.assertEqual(scheduler.merged_parameters(), [])
        self.assertEqual(scheduler.stale_layers_dropped, 1)

    def test_soullink_gaze_input_is_clamped_and_timestamped(self):
        plugin = self._plugin()
        plugin._soullink_gaze_last_error = "old error"
        before = time.monotonic()

        plugin._set_soullink_gaze(2.0, -1.0)

        self.assertEqual(plugin._soullink_gaze_x, 1.0)
        self.assertEqual(plugin._soullink_gaze_y, 0.0)
        self.assertGreaterEqual(plugin._soullink_gaze_last_update_at, before)
        self.assertEqual(plugin._soullink_gaze_last_error, "")

    async def test_soullink_gaze_drives_both_eyes_with_bounded_values(self):
        class _Scheduler:
            def __init__(self):
                self.parameters = []
                self.ttl = None

            def set_layer(self, _source, parameters, *, ttl=None):
                self.parameters = parameters
                self.ttl = ttl

            def clear_layer(self, _source):
                self.parameters = []

        plugin = self._plugin()
        scheduler = _Scheduler()
        plugin._vts_parameter_scheduler = scheduler
        plugin._set_soullink_gaze(1.0, 0.0)
        task = asyncio.create_task(plugin._soullink_gaze_loop())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        values = {item["id"]: item["value"] for item in scheduler.parameters}
        self.assertEqual(
            set(values),
            {"FaceAngleX", "FaceAngleY", "EyeLeftX", "EyeRightX", "EyeLeftY", "EyeRightY"},
        )
        self.assertEqual(values["EyeLeftX"], values["EyeRightX"])
        self.assertEqual(values["EyeLeftY"], values["EyeRightY"])
        self.assertTrue(all(-1.0 <= values[key] <= 1.0 for key in values if key.startswith("Eye")))
        self.assertEqual(scheduler.ttl, 0.25)

    async def test_soullink_gaze_releases_layer_when_input_is_stale(self):
        class _Scheduler:
            def __init__(self):
                self.cleared = []

            def set_layer(self, _source, _parameters, *, ttl=None):
                return None

            def clear_layer(self, source):
                self.cleared.append(source)

        plugin = self._plugin()
        scheduler = _Scheduler()
        plugin._vts_parameter_scheduler = scheduler
        plugin._set_soullink_gaze(0.8, 0.2)
        task = asyncio.create_task(plugin._soullink_gaze_loop())
        await asyncio.sleep(0.06)
        plugin._soullink_gaze_last_update_at = time.monotonic() - 2.0
        await asyncio.sleep(0.06)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertIn("soullink_gaze", scheduler.cleared)

    async def test_soullink_gaze_tasks_restart_independently(self):
        async def wait_forever():
            await asyncio.Event().wait()

        plugin = self._plugin(soullink_enabled=True, soullink_gaze_enabled=True)
        plugin._soullink_runtime = SimpleNamespace(running=True)
        plugin._vts_parameter_scheduler = SimpleNamespace(clear_layer=lambda _source: None)
        plugin._soullink_gaze_loop = wait_forever
        plugin._soullink_gaze_vts_poller = wait_forever
        gaze_task = asyncio.create_task(wait_forever())
        completed_poll_task = asyncio.create_task(asyncio.sleep(0))
        await completed_poll_task
        plugin._soullink_gaze_task = gaze_task
        plugin._soullink_gaze_poll_task = completed_poll_task

        plugin._ensure_soullink_gaze()

        self.assertIs(plugin._soullink_gaze_task, gaze_task)
        self.assertIsNot(plugin._soullink_gaze_poll_task, completed_poll_task)
        self.assertFalse(plugin._soullink_gaze_poll_task.done())
        plugin._stop_soullink_gaze()
        await asyncio.sleep(0)

    def test_soullink_gaze_does_not_start_before_runtime(self):
        plugin = self._plugin(soullink_enabled=True, soullink_gaze_enabled=True)
        plugin._soullink_runtime = SimpleNamespace(running=False)

        plugin._ensure_soullink_gaze()

        self.assertIsNone(getattr(plugin, "_soullink_gaze_task", None))
        self.assertIsNone(getattr(plugin, "_soullink_gaze_poll_task", None))

    async def test_soullink_gaze_status_reports_tracking_and_errors(self):
        async def wait_forever():
            await asyncio.Event().wait()

        plugin = self._plugin(soullink_enabled=True, soullink_gaze_enabled=True)
        plugin._soullink_runtime = SimpleNamespace(running=True)
        plugin._soullink_gaze_task = asyncio.create_task(wait_forever())
        plugin._soullink_gaze_poll_task = asyncio.create_task(wait_forever())
        plugin._soullink_gaze_last_update_at = time.monotonic()
        plugin._soullink_gaze_last_error = ""

        status = plugin._soullink_gaze_status()
        self.assertTrue(status["running"])
        self.assertTrue(status["tracking"])
        self.assertIsNotNone(status["last_update_age"])

        plugin._soullink_gaze_last_update_at = time.monotonic() - 2.0
        plugin._soullink_gaze_last_error = "VTS offline"
        status = plugin._soullink_gaze_status()
        self.assertFalse(status["tracking"])
        self.assertEqual(status["last_error"], "VTS offline")
        plugin._stop_soullink_gaze()
        await asyncio.sleep(0)

    async def test_vts_parameter_value_request_uses_parameter_name(self):
        client = VTSClient()
        calls = []

        async def send_request(message_type, data):
            calls.append((message_type, data))
            return {"data": {"name": data["name"], "value": 0.25}}

        client._send_request = send_request
        result = await client.get_parameter_value("MousePositionX")

        self.assertEqual(calls, [("ParameterValueRequest", {"name": "MousePositionX"})])
        self.assertEqual(result["value"], 0.25)

    async def test_vts_api_error_is_not_reported_as_success(self):
        class _FakeWebSocket:
            closed = False

            async def send(self, _payload):
                return None

            async def recv(self):
                return json.dumps(
                    {
                        "messageType": "APIError",
                        "data": {"errorID": 453, "message": "invalid parameter"},
                    }
                )

        client = VTSClient()
        client._ws = _FakeWebSocket()
        client._is_connected = True

        with self.assertRaisesRegex(VTSResponseError, "453"):
            await client.inject_parameters([{"id": "ParamMouthOpenY", "value": 0.5}])

    async def test_vts_reconnect_reauthenticates_before_parameter_frame(self):
        class _FakeWebSocket:
            closed = False

            def __init__(self):
                self.sent = []
                self.responses = deque(
                    [
                        {
                            "messageType": "AuthenticationResponse",
                            "data": {"authenticated": True},
                        },
                        {
                            "messageType": "InjectParameterDataResponse",
                            "data": {},
                        },
                    ]
                )

            async def send(self, payload):
                self.sent.append(json.loads(payload))

            async def recv(self):
                return json.dumps(self.responses.popleft())

        client = VTSClient()
        socket = _FakeWebSocket()
        client.auth_token = "saved-token"

        async def connect():
            client._ws = socket
            client._is_connected = True
            client._authenticated = False

        client._connect = connect

        await client.inject_parameters([{"id": "FaceAngleX", "value": 1.0}])

        self.assertEqual(
            [item["messageType"] for item in socket.sent],
            ["AuthenticationRequest", "InjectParameterDataRequest"],
        )
        self.assertTrue(client.is_authenticated)

    async def test_cancelled_reconnect_authentication_discards_socket(self):
        class _FakeWebSocket:
            closed = False

            def __init__(self):
                self.waiting = asyncio.Event()

            async def send(self, _payload):
                return None

            async def recv(self):
                self.waiting.set()
                await asyncio.Event().wait()

            async def close(self):
                self.closed = True

        client = VTSClient()
        socket = _FakeWebSocket()
        client.auth_token = "saved-token"

        async def connect():
            client._ws = socket
            client._is_connected = True
            client._authenticated = False

        client._connect = connect
        task = asyncio.create_task(
            client.inject_parameters([{"id": "FaceAngleX", "value": 1.0}])
        )
        await socket.waiting.wait()
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertIsNone(client._ws)
        self.assertFalse(client.is_connected)

    async def test_vts_authentication_api_error_invalidates_session(self):
        class _FakeWebSocket:
            closed = False

            async def send(self, _payload):
                return None

            async def recv(self):
                return json.dumps(
                    {
                        "messageType": "APIError",
                        "data": {"errorID": 8, "message": "Authentication required"},
                    }
                )

        client = VTSClient()
        client._ws = _FakeWebSocket()
        client._is_connected = True
        client._authenticated = True

        with self.assertRaises(VTSResponseError):
            await client.inject_parameters([{"id": "FaceAngleX", "value": 1.0}])

        self.assertFalse(client.is_authenticated)

    async def test_realtime_parameter_connection_uses_saved_token(self):
        class _FakeParameterVTS:
            is_authenticated = False

            def __init__(self):
                self.tokens = []

            async def authenticate(self, token):
                self.tokens.append(token)
                self.is_authenticated = True
                return True

        plugin = object.__new__(VTubeStudioPlugin)
        plugin._parameter_vts = _FakeParameterVTS()

        async def load_token():
            return "saved-token"

        plugin._load_token = load_token

        self.assertTrue(await plugin._check_parameter_connection())
        self.assertEqual(plugin._parameter_vts.tokens, ["saved-token"])

    async def test_realtime_parameter_frames_do_not_wait_for_responses(self):
        class _SlowResponseWebSocket:
            closed = False

            def __init__(self):
                self.sent = []
                self.recv_started = asyncio.Event()

            async def send(self, payload):
                self.sent.append(json.loads(payload))

            async def recv(self):
                self.recv_started.set()
                await asyncio.Event().wait()

            async def close(self):
                self.closed = True

        client = VTSRealtimeClient()
        socket = _SlowResponseWebSocket()
        client._ws = socket
        client._is_connected = True
        client._authenticated = True

        for value in range(5):
            await asyncio.wait_for(
                client.inject_parameters(
                    [{"id": "FaceAngleX", "value": float(value)}]
                ),
                timeout=0.1,
            )

        await socket.recv_started.wait()
        self.assertEqual(len(socket.sent), 5)
        await client.disconnect()


if __name__ == "__main__":
    unittest.main()
