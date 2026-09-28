# -*- coding: utf-8 -*-
"""拓展页「下拉选项」用的纯工具函数（不依赖 AstrBot，方便单测）。

解决两处填写麻烦的配置：

* 外部 TTS 服务：从已注册的 LLM 工具反查所属插件，列出该插件公开的合成方法，
  供拓展页渲染成下拉框（``live_tts_external_tool_name`` / ``..._service_method``）；
* 远程 VTS：由「已填写的 vts_host」「页面访问地址」「显式指定的网段」推导候选地址，
  交给 :mod:`vts_discovery` 做实际探测。
"""
from __future__ import annotations

import inspect
import ipaddress
import socket
from typing import Any, Iterable

# 明确属于「语音合成」的方法名
TTS_METHOD_HINTS = (
    "text_to_speech",
    "render_pcm_wav",
    "synthesize_speech",
    "synthesize_voice",
    "generate_audio",
    "generate_voice",
    "tts",
    "speak",
)

# 名称里带这些关键字就当作候选合成方法
TTS_METHOD_KEYWORDS = ("tts", "speech", "voice", "audio", "wav", "pcm")

# 明显是「语音识别」的方法，排除掉（避免把 ASR 当成合成）
TTS_METHOD_DENY_KEYWORDS = (
    "speech_to_text",
    "voice_to_text",
    "transcribe",
    "transcription",
    "recognize",
    "recognition",
    "_asr",
    "asr_",
)

MAX_SUBNET_HOSTS = 254


def iter_handler_owners(handler: Any) -> list[Any]:
    """沿 handler 的绑定对象 / partial 参数 / 闭包 cell / 包装函数收集候选对象。

    工具函数常见包装形式有绑定方法、``functools.partial``、装饰器闭包（例如
    ``@filter.llm_tool`` 在另一个函数里定义 ``async def tool(self, ...)``），
    这些形式都要能顺着找到插件实例，否则就取不到插件的公开合成方法。
    """
    pending: list[Any] = [handler]
    visited: set[int] = set()
    owners: list[Any] = []
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in visited:
            continue
        visited.add(id(current))
        owners.append(current)
        owner = getattr(current, "__self__", None)
        if owner is not None:
            pending.append(owner)
        pending.extend(list(getattr(current, "args", ()) or ()))
        wrapped = getattr(current, "func", None)
        if wrapped is not None and wrapped is not current:
            pending.append(wrapped)
        wrapped_chain = getattr(current, "__wrapped__", None)
        if wrapped_chain is not None and wrapped_chain is not current:
            pending.append(wrapped_chain)
        for cell in getattr(current, "__closure__", None) or ():
            try:
                pending.append(cell.cell_contents)
            except ValueError:
                continue
    return owners


def plugin_name_from_module_path(value: Any) -> str:
    """从 ``handler_module_path`` / ``__module__`` 里提取 ``astrbot_plugin_xxx``。"""
    text = str(value or "")
    for part in text.split("."):
        part = part.strip()
        if part.startswith("astrbot_plugin_"):
            return part
    return ""


def looks_like_plugin(obj: Any) -> bool:
    """粗略判断对象是不是 AstrBot 的插件实例。"""
    if obj is None or inspect.isclass(obj) or inspect.ismodule(obj):
        return False
    for attr in ("metadata", "plugin_id", "star_cls", "context"):
        if hasattr(obj, attr):
            return True
    module = str(getattr(obj, "__module__", "") or "")
    return "data.plugins" in module


def tts_plugin_from_tool(tool: Any) -> Any | None:
    """从 LLM 工具对象反查提供该工具的插件实例。"""
    handler = getattr(tool, "handler", None)
    for owner in iter_handler_owners(handler):
        if looks_like_plugin(owner):
            return owner
    return None


def plugin_identifiers(plugin: Any) -> set[str]:
    """插件可能用到的各种名字（用于校验 / 展示 / 匹配）。"""
    names: set[str] = set()
    for attr in ("name", "plugin_id", "plugin_name"):
        value = str(getattr(plugin, attr, "") or "").strip()
        if value:
            names.add(value)
    metadata = getattr(plugin, "metadata", None)
    for attr in ("name", "plugin_id", "display_name"):
        value = str(getattr(metadata, attr, "") or "").strip()
        if value:
            names.add(value)
    module = str(getattr(plugin, "__module__", "") or "")
    if module:
        for part in module.split("."):
            part = part.strip()
            if part.startswith("astrbot_plugin_"):
                names.add(part)
    return names


def plugin_display_name(plugin: Any) -> str:
    metadata = getattr(plugin, "metadata", None)
    for attr in ("display_name", "name", "plugin_id"):
        value = str(getattr(metadata, attr, "") or "").strip()
        if value:
            return value
    for attr in ("name", "plugin_id"):
        value = str(getattr(plugin, attr, "") or "").strip()
        if value:
            return value
    return ""


def tts_service_methods(plugin: Any) -> list[str]:
    """列出插件上像「语音合成」的公开方法。"""
    if plugin is None or inspect.isclass(plugin):
        return []
    methods: list[str] = []
    for name in dir(plugin):
        if name.startswith("_"):
            continue
        lowered = name.lower()
        if any(token in lowered for token in TTS_METHOD_DENY_KEYWORDS):
            continue
        try:
            attr = getattr(plugin, name)
        except Exception:
            continue
        if not callable(attr):
            continue
        if name in TTS_METHOD_HINTS or any(token in lowered for token in TTS_METHOD_KEYWORDS):
            methods.append(name)
    return sorted(set(methods))


def describe_external_tts_tool(tool: Any) -> dict[str, Any] | None:
    """把一个 LLM 工具描述成下拉选项（即使暂时取不到方法也保留，便于手动填写）。"""
    name = str(getattr(tool, "name", "") or getattr(tool, "func_name", "") or "").strip()
    if not name:
        return None
    plugin = tts_plugin_from_tool(tool)
    methods = tts_service_methods(plugin)
    identifiers = set(plugin_identifiers(plugin)) if plugin is not None else set()
    module_plugin = plugin_name_from_module_path(
        getattr(tool, "handler_module_path", None)
    ) or plugin_name_from_module_path(getattr(getattr(tool, "handler", None), "__module__", None))
    if module_plugin:
        identifiers.add(module_plugin)
    plugin_name = ""
    for candidate in sorted(identifiers):
        if candidate.startswith("astrbot_plugin_"):
            plugin_name = candidate
            break
    if not plugin_name:
        plugin_name = next(iter(sorted(identifiers)), "")
    description = str(getattr(tool, "description", "") or getattr(tool, "desc", "") or "").strip()
    label = plugin_display_name(plugin) or plugin_name or name
    haystack = f"{name} {description}".lower()
    looks_like_asr = any(
        token in haystack
        for token in (
            "speech_to_text",
            "voice_to_text",
            "transcribe",
            "transcription",
            "recognition",
            "asr",
            "转写",
            "语音转",
            "转文本",
        )
    )
    tts_like = bool(methods) or (
        not looks_like_asr
        and any(
            token in haystack
            for token in (
                "tts",
                "speak",
                "speech",
                "voice",
                "audio",
                "wav",
                "pcm",
                "语音",
                "朗读",
                "配音",
                "发声",
                "合成音",
            )
        )
    )
    return {
        "tool": name,
        "plugin": plugin_name,
        "plugin_label": plugin_display_name(plugin),
        "methods": methods,
        "tts_like": tts_like,
        "has_plugin": bool(plugin is not None or plugin_name),
        "label": f"{label} · {name}" if label and label != name else name,
        "description": description[:200],
    }


def build_external_tts_options(tools: Iterable[Any]) -> list[dict[str, Any]]:
    """把工具列表整理成去重、按名称排序的下拉选项。"""
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in tools or []:
        try:
            item = describe_external_tts_tool(tool)
        except Exception:
            item = None
        if not item or item["tool"] in seen:
            continue
        seen.add(item["tool"])
        options.append(item)
    options.sort(
        key=lambda item: (
            0 if item.get("methods") else (1 if item.get("tts_like") else 2),
            item.get("plugin_label") or item.get("plugin") or "",
            item["tool"],
        )
    )
    return options


def normalize_host_entries(values: Iterable[str] | str | None) -> list[str]:
    """把 ``host`` / ``host:port`` / 逗号或空白分隔的字符串整理成地址列表。"""
    if values is None:
        return []
    if isinstance(values, str):
        raw_items = [item for item in values.replace(";", ",").replace("\n", ",").split(",")]
    else:
        raw_items = []
        for value in values:
            raw_items.extend(str(value).replace(";", ",").replace("\n", ",").split(","))
    hosts: list[str] = []
    for item in raw_items:
        item = item.strip()
        if not item:
            continue
        if item.startswith("[") and "]" in item:  # [ipv6]:port
            host = item[1 : item.index("]")]
        elif item.count(":") == 1 and item.rsplit(":", 1)[1].isdigit():
            host = item.rsplit(":", 1)[0]
        else:
            host = item
        host = host.strip()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def private_ipv4(value: str | None) -> str | None:
    """返回私有 IPv4 字符串；不是私有 IPv4（含 localhost）则返回 None。"""
    if not value:
        return None
    candidate = value.strip().strip("[]")
    if not candidate:
        return None
    try:
        addr = ipaddress.IPv4Address(candidate)
    except ipaddress.AddressValueError:
        return None
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
        return None
    if not addr.is_private:
        return None
    return str(addr)


def subnet_hosts(value: str | None, prefix_len: int = 24, limit: int = MAX_SUBNET_HOSTS) -> list[str]:
    """把 IPv4 / CIDR 展开成可扫描的主机地址（默认 /24，最多 ``limit`` 个）。"""
    if not value:
        return []
    text = value.strip()
    if not text:
        return []
    try:
        if "/" in text:
            network = ipaddress.ip_network(text, strict=False)
            if network.version != 4 or network.num_addresses > limit + 2:
                return []
        else:
            addr = ipaddress.IPv4Address(text)
            network = ipaddress.ip_network(f"{addr}/{prefix_len}", strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return []
    hosts: list[str] = []
    for host in network.hosts():
        if host.is_loopback or host.is_link_local or host.is_multicast:
            continue
        hosts.append(str(host))
        if len(hosts) >= limit:
            break
    return hosts


def derive_subnet_seeds(ips: Iterable[str], prefix_len: int = 24) -> list[str]:
    """从若干 IPv4 里推导出去重的 /24 网段（形如 ``192.168.1.0/24``）。"""
    subnets: list[str] = []
    for value in ips:
        addr = private_ipv4(value)
        if not addr:
            continue
        network = ipaddress.ip_network(f"{addr}/{prefix_len}", strict=False)
        text = str(network)
        if text not in subnets:
            subnets.append(text)
    return subnets


def local_ipv4_candidates() -> list[str]:
    """本机（容器内）可能的 IPv4 地址，用于兜底探测。"""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = str(info[4][0])
            if addr and addr not in ips:
                ips.append(addr)
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            addr = str(sock.getsockname()[0])
            if addr and addr not in ips:
                ips.append(addr)
        finally:
            sock.close()
    except Exception:
        pass
    return ips


def build_probe_targets(
    *,
    configured_host: str = "",
    configured_port: int | None = None,
    request_host: str = "",
    extra_hosts: Iterable[str] = (),
    extra_subnets: Iterable[str] = (),
    include_scan: bool = False,
    default_port: int = 8001,
) -> dict[str, Any]:
    """推导需要探测的 hosts / ports / subnets（纯函数，便于单测）。"""
    port = int(configured_port or 0) or default_port
    single_hosts: list[str] = []
    for value in (configured_host, request_host, "127.0.0.1"):
        for host in normalize_host_entries(value):
            if host and host not in single_hosts:
                single_hosts.append(host)
    for host in normalize_host_entries(extra_hosts):
        if host not in single_hosts:
            single_hosts.append(host)
    ports: list[int] = []
    for candidate in (port, default_port):
        if candidate and candidate not in ports:
            ports.append(candidate)
    subnets = list(extra_subnets)
    if include_scan:
        seeds = list(subnets)
        seeds.extend(derive_subnet_seeds([configured_host, request_host]))
        for addr in local_ipv4_candidates():
            seeds.extend(derive_subnet_seeds([addr]))
        subnets = []
        for item in seeds:
            if item and item not in subnets:
                subnets.append(item)
    return {
        "hosts": single_hosts,
        "ports": ports,
        "subnets": subnets,
    }


def candidate_label(host: str, port: int, version: str = "") -> str:
    label = f"{host}:{port}"
    version = str(version or "").strip()
    if version:
        label = f"{label} · VTS {version}"
    return label
