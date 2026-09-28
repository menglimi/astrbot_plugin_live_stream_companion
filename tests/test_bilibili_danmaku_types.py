# -*- coding: utf-8 -*-
"""Regression tests for Bilibili text, emoticon, and voice danmaku types."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from data.plugins.astrbot_plugin_live_stream_companion.bilibili_live import (
    BilibiliBlivedmClient,
    BilibiliLaplaceClient,
    BilibiliLiveClient,
    BilibiliOpenLiveClient,
    LiveDanmakuEvent,
)
from data.plugins.astrbot_plugin_live_stream_companion.blivedm.models import (
    message as unified_models,
)
from data.plugins.astrbot_plugin_live_stream_companion.blivedm.models import (
    open_live as open_models,
)
from data.plugins.astrbot_plugin_live_stream_companion.blivedm.models import (
    web as web_models,
)
from data.plugins.astrbot_plugin_live_stream_companion.main import VTubeStudioPlugin
from data.plugins.astrbot_plugin_live_stream_companion.page_api import (
    LiveStreamCompanionPageApi,
)
from data.plugins.astrbot_plugin_live_stream_companion.page_config import (
    PageConfigManager,
)


class LiveDanmakuTypeTests(unittest.TestCase):
    def test_event_normalizes_type_and_emoticon(self):
        event = LiveDanmakuEvent(
            "danmaku",
            "viewer",
            "[doge]",
            dm_type="1",
            emoticon='{"url":"https://example.test/doge.png"}',
        )

        self.assertEqual(event.dm_type, 1)
        self.assertTrue(event.is_emoticon_danmaku)
        self.assertFalse(event.is_voice_danmaku)
        self.assertEqual(event.emoticon["url"], "https://example.test/doge.png")

    def test_native_websocket_payload_preserves_emoticon(self):
        info0 = [0] * 13
        info0[12] = 1
        info0.append({"url": "https://example.test/native.png"})
        payload = {
            "cmd": "DANMU_MSG",
            "info": [info0, "[打call]", [1001, "Alice"]],
        }

        event = object.__new__(BilibiliLiveClient)._payload_to_event(payload)

        self.assertIsNotNone(event)
        self.assertTrue(event.is_emoticon_danmaku)
        self.assertEqual(event.emoticon["url"], "https://example.test/native.png")

    def test_history_laplace_and_open_live_preserve_type(self):
        history = object.__new__(BilibiliLiveClient)._history_row_to_event(
            {
                "text": "[妙啊]",
                "nickname": "HistoryUser",
                "dm_type": "1",
                "emoticon": '{"url":"https://example.test/history.png"}',
            }
        )
        laplace = object.__new__(BilibiliLaplaceClient)._payload_to_event(
            {
                "type": "message",
                "username": "LaplaceUser",
                "message": "voice",
                "dm_type": 2,
            }
        )
        open_live = object.__new__(BilibiliOpenLiveClient)._payload_to_event(
            {
                "cmd": "LIVE_OPEN_PLATFORM_DM",
                "data": {
                    "uname": "OpenUser",
                    "msg": "[干杯]",
                    "dm_type": 1,
                    "emoji_img_url": "https://example.test/open.png",
                },
            }
        )

        self.assertTrue(history.is_emoticon_danmaku)
        self.assertEqual(history.emoticon["url"], "https://example.test/history.png")
        self.assertTrue(laplace.is_voice_danmaku)
        self.assertTrue(open_live.is_emoticon_danmaku)
        self.assertEqual(open_live.emoticon["url"], "https://example.test/open.png")

    def test_blivedm_web_and_open_models_preserve_type(self):
        web_source = web_models.DanmakuMessage(
            dm_type=1,
            emoticon_options='{"url":"https://example.test/web.png"}',
            msg="[doge]",
            uid=1002,
            uname="WebUser",
        )
        web_message = unified_models.DanmakuMessage.from_web_message(
            web_source,
            room_id=123,
            raw_data={"source": "web"},
        )
        web_event = object.__new__(BilibiliBlivedmClient)._message_to_event(
            web_message
        )

        open_source = open_models.DanmakuMessage(
            dm_type=1,
            emoji_img_url="https://example.test/open-model.png",
            msg="[花]",
            open_id="open-user",
            uname="OpenModelUser",
        )
        open_message = unified_models.DanmakuMessage.from_open_live_message(
            open_source,
            raw_data={"source": "open"},
        )
        open_event = object.__new__(BilibiliBlivedmClient)._message_to_event(
            open_message
        )

        self.assertEqual(web_message.dm_type, 1)
        self.assertEqual(web_event.emoticon["url"], "https://example.test/web.png")
        self.assertTrue(web_event.is_emoticon_danmaku)
        self.assertEqual(open_message.dm_type, 1)
        self.assertEqual(
            open_event.emoticon["url"],
            "https://example.test/open-model.png",
        )


class AutoReplyRichDanmakuTests(unittest.TestCase):
    @staticmethod
    def _plugin(**config):
        plugin = object.__new__(VTubeStudioPlugin)
        plugin.config = {"bili_live_auto_reply_enabled": True, **config}
        return plugin

    def test_rich_danmaku_is_skipped_by_default(self):
        plugin = self._plugin()

        self.assertTrue(
            plugin._should_collect_for_auto_reply(
                LiveDanmakuEvent("danmaku", "viewer", "hello", dm_type=0)
            )
        )
        self.assertFalse(
            plugin._should_collect_for_auto_reply(
                LiveDanmakuEvent("danmaku", "viewer", "[doge]", dm_type=1)
            )
        )
        self.assertFalse(
            plugin._should_collect_for_auto_reply(
                LiveDanmakuEvent("danmaku", "viewer", "voice", dm_type=2)
            )
        )

    def test_skip_can_be_disabled(self):
        plugin = self._plugin(bili_live_auto_reply_skip_emoticon_danmaku=False)

        self.assertTrue(
            plugin._should_collect_for_auto_reply(
                LiveDanmakuEvent("danmaku", "viewer", "[doge]", dm_type=1)
            )
        )

    def test_management_schema_exposes_skip_switch(self):
        key = "bili_live_auto_reply_skip_emoticon_danmaku"
        manager = PageConfigManager(SimpleNamespace(config={}), "test", Mock())
        schema = manager.read_schema()

        self.assertEqual(schema[key]["type"], "bool")
        self.assertTrue(schema[key]["default"])
        self.assertIn(key, manager.editable_keys())
        reply_group = next(
            item for item in manager.groups() if item.get("id") == "reply"
        )
        self.assertIn(key, reply_group["keys"])

        event = LiveDanmakuEvent("danmaku", "viewer", "[doge]", dm_type=1)
        payload = object.__new__(LiveStreamCompanionPageApi)._event_payload(event)
        self.assertEqual(payload["dm_type"], 1)

    def test_management_page_exposes_external_live_tts_settings(self):
        manager = PageConfigManager(SimpleNamespace(config={}), "test", Mock())
        expected_keys = {
            "bili_live_auto_reply_force_full_tts",
            "twitch_auto_reply_tts_enabled",
            "live_tts_backend",
            "live_tts_external_tool_name",
            "live_tts_external_service_method",
            "live_tts_external_plugin_name",
            "live_tts_external_timeout_seconds",
            "bili_live_auto_reply_sync_tts_subtitle",
            "bili_live_tts_local_playback_enabled",
            "bili_live_tts_web_playback_enabled",
        }

        self.assertTrue(expected_keys.issubset(manager.editable_keys()))
        audio_group = next(
            item for item in manager.groups() if item.get("id") == "audio"
        )
        self.assertEqual(audio_group["title"], "直播语音（TTS）")
        self.assertEqual(set(audio_group["keys"]), expected_keys)
        payload = manager.schema_payload()
        self.assertTrue(expected_keys.issubset(payload["schema"]))
        updates = manager.build_updates(
            {
                "live_tts_backend": "auto",
                "live_tts_external_tool_name": "demo_tts_tool",
                "live_tts_external_timeout_seconds": "75",
            }
        )
        self.assertEqual(updates["live_tts_backend"], "auto")
        self.assertEqual(updates["live_tts_external_tool_name"], "demo_tts_tool")
        self.assertEqual(updates["live_tts_external_timeout_seconds"], 75)


if __name__ == "__main__":
    unittest.main()
