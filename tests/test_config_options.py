# -*- coding: utf-8 -*-
"""拓展页下拉选项（外部 TTS / 远程 VTS）纯函数回归测试。"""

import unittest
from types import SimpleNamespace

try:  # AstrBot 运行环境（容器内 pytest / unittest）
    from data.plugins.astrbot_plugin_live_stream_companion.config_options import (
        build_external_tts_options,
        build_probe_targets,
        candidate_label,
        describe_external_tts_tool,
        derive_subnet_seeds,
        normalize_host_entries,
        plugin_display_name,
        plugin_identifiers,
        private_ipv4,
        subnet_hosts,
        tts_service_methods,
    )
except ModuleNotFoundError:  # 本地直接跑单测：纯模块不依赖 AstrBot
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from config_options import (  # type: ignore[no-redef]
        build_external_tts_options,
        build_probe_targets,
        candidate_label,
        describe_external_tts_tool,
        derive_subnet_seeds,
        normalize_host_entries,
        plugin_display_name,
        plugin_identifiers,
        private_ipv4,
        subnet_hosts,
        tts_service_methods,
    )


class _TtsPlugin:
    def __init__(self, display="Demo TTS", plugin_id="astrbot_plugin_demo_tts"):
        self.metadata = SimpleNamespace(name=plugin_id, display_name=display, plugin_id=plugin_id)

    async def synthesize_speech(self, text: str):  # noqa: D401 - 方法名即契约
        return f"/tmp/{text}.wav"

    async def render_wav(self, text: str):
        return {"path": f"/tmp/{text}.wav"}

    async def speech_to_text(self, audio: str):
        return "不该被当成合成方法"

    def _private_helper(self):
        return "私有方法不参与"


class _AsrOnlyPlugin:
    def __init__(self):
        self.metadata = SimpleNamespace(name="astrbot_plugin_asr", display_name="ASR")

    async def transcribe(self, audio: str):
        return "text"


def _tool(handler, name="demo_tts_tool", description="把文本合成语音"):
    return SimpleNamespace(name=name, handler=handler, description=description)


class ExternalTtsOptionTests(unittest.TestCase):
    def test_lists_plugin_and_methods(self):
        plugin = _TtsPlugin()
        options = build_external_tts_options([_tool(plugin.synthesize_speech)])
        self.assertEqual(len(options), 1)
        item = options[0]
        self.assertEqual(item["tool"], "demo_tts_tool")
        self.assertEqual(item["plugin"], "astrbot_plugin_demo_tts")
        self.assertEqual(item["plugin_label"], "Demo TTS")
        self.assertEqual(item["methods"], ["render_wav", "synthesize_speech"])
        self.assertIn("Demo TTS", item["label"])

    def test_keeps_tools_without_methods(self):
        """取不到合成方法也要保留（供手动填写），但标记为非 tts_like。"""
        asr = _AsrOnlyPlugin()
        tools = [
            _tool(asr.transcribe, name="asr_transcribe", description="把语音转成文本"),
            _tool(lambda text: text, name="plain_tool", description="普通工具"),
        ]
        options = build_external_tts_options(tools)
        by_tool = {item["tool"]: item for item in options}
        self.assertEqual(len(options), 2)
        self.assertEqual(by_tool["asr_transcribe"]["methods"], [])
        self.assertFalse(by_tool["asr_transcribe"]["tts_like"])
        self.assertFalse(by_tool["plain_tool"]["has_plugin"])

    def test_resolves_plugin_from_closure_handler(self):
        """工具定义在另一个函数里、靠闭包捕获插件实例的注册方式：工具定义在另一个函数里，靠闭包捕获插件实例。"""
        plugin = _TtsPlugin()

        def factory():
            async def tool_handler(text: str = ""):
                return await plugin.synthesize_speech(text)

            return tool_handler

        handler = factory()
        item = describe_external_tts_tool(_tool(handler, name="demo_tts_tool"))
        self.assertIsNotNone(item)
        self.assertEqual(item["plugin"], "astrbot_plugin_demo_tts")
        self.assertIn("render_wav", item["methods"])
        self.assertTrue(item["tts_like"])

    def test_resolves_plugin_from_module_path(self):
        """只有 handler_module_path 时也要能定位插件，并按名字判断像不像 TTS。"""
        tool = _tool(lambda text: text, name="tts_speak", description="朗读文本")
        tool.handler_module_path = "data.plugins.astrbot_plugin_my_voice.main"
        item = describe_external_tts_tool(tool)
        self.assertEqual(item["plugin"], "astrbot_plugin_my_voice")
        self.assertEqual(item["methods"], [])
        self.assertTrue(item["tts_like"])

    def test_sorts_services_before_plain_tools(self):
        plugin = _TtsPlugin()
        tools = [
            _tool(lambda text: text, name="plain_tool", description="普通工具"),
            _tool(plugin.synthesize_speech, name="voice_tool"),
        ]
        options = build_external_tts_options(tools)
        self.assertEqual(options[0]["tool"], "voice_tool")

    def test_deduplicates_and_sorts(self):
        plugin = _TtsPlugin(display="Zeta", plugin_id="astrbot_plugin_zeta")
        plugin2 = _TtsPlugin(display="Alpha", plugin_id="astrbot_plugin_alpha")
        tools = [
            _tool(plugin.synthesize_speech, name="zeta_speak"),
            _tool(plugin2.synthesize_speech, name="alpha_speak"),
            _tool(plugin.synthesize_speech, name="zeta_speak"),
        ]
        options = build_external_tts_options(tools)
        self.assertEqual([item["tool"] for item in options], ["alpha_speak", "zeta_speak"])

    def test_helper_functions(self):
        plugin = _TtsPlugin()
        self.assertIn("astrbot_plugin_demo_tts", plugin_identifiers(plugin))
        self.assertEqual(plugin_display_name(plugin), "Demo TTS")
        methods = tts_service_methods(plugin)
        self.assertIn("synthesize_speech", methods)
        self.assertIn("render_wav", methods)
        self.assertNotIn("speech_to_text", methods)
        self.assertNotIn("_private_helper", methods)


class VtsProbeTargetTests(unittest.TestCase):
    def test_private_ipv4_filters(self):
        self.assertEqual(private_ipv4("192.168.1.10"), "192.168.1.10")
        self.assertEqual(private_ipv4("10.0.0.7"), "10.0.0.7")
        self.assertIsNone(private_ipv4("127.0.0.1"))
        self.assertIsNone(private_ipv4("8.8.8.8"))
        self.assertIsNone(private_ipv4("not-an-ip"))

    def test_normalize_host_entries(self):
        self.assertEqual(
            normalize_host_entries("192.168.1.10:8001, 127.0.0.1;host.docker.internal"),
            ["192.168.1.10", "127.0.0.1", "host.docker.internal"],
        )

    def test_build_probe_targets_quick(self):
        plan = build_probe_targets(
            configured_host="192.168.1.10",
            configured_port=8001,
            request_host="192.168.1.11:11451",
        )
        self.assertEqual(plan["hosts"], ["192.168.1.10", "192.168.1.11", "127.0.0.1"])
        self.assertEqual(plan["ports"], [8001])
        self.assertEqual(plan["subnets"], [])

    def test_build_probe_targets_scan_adds_subnets(self):
        plan = build_probe_targets(
            configured_host="192.168.1.10",
            configured_port=8001,
            request_host="192.168.1.11",
            include_scan=True,
        )
        # 同网段地址只推导一次；本机地址可能额外补一个网段，所以不锁总数
        self.assertEqual(plan["subnets"][0], "192.168.1.0/24")
        self.assertEqual(plan["subnets"].count("192.168.1.0/24"), 1)

    def test_subnet_hosts(self):
        hosts = subnet_hosts("192.168.1.0/24")
        self.assertEqual(len(hosts), 254)
        self.assertIn("192.168.1.10", hosts)
        self.assertNotIn("192.168.1.255", hosts)
        self.assertEqual(subnet_hosts("192.168.1.0/16"), [])
        self.assertEqual(subnet_hosts("bad-value"), [])

    def test_derive_subnet_seeds_ignores_public_and_loopback(self):
        seeds = derive_subnet_seeds(["192.168.1.10", "127.0.0.1", "8.8.8.8"])
        self.assertEqual(seeds, ["192.168.1.0/24"])

    def test_candidate_label(self):
        self.assertEqual(candidate_label("192.168.1.10", 8001, "1.35.10"), "192.168.1.10:8001 · VTS 1.35.10")
        self.assertEqual(candidate_label("127.0.0.1", 8001), "127.0.0.1:8001")


if __name__ == "__main__":
    unittest.main()
