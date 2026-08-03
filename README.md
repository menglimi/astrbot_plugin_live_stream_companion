# 我会直播圈米养你

`astrbot_plugin_live_stream_companion` 是一个面向 AstrBot 的直播陪伴插件。它把 B 站直播弹幕、AstrBot 回复链路、可选 Soullink 连续情绪表演、VTube Studio 动作、OBS 字幕、TTS 嘴型和“我会永远陪着你”的主动行为连接在一起，让 Bot 可以作为虚拟主播助手参与直播。

- 插件名：`astrbot_plugin_live_stream_companion`
- 中文名：`我会直播圈米养你`
- 当前版本：`1.8.0`
- 适配平台：`aiocqhttp` / OneBot v11
- AstrBot 版本：`>=4.16,<5`
- 编码要求：UTF-8

## 支持开发者（自愿捐款）

**重要声明：**

- **捐款完全自愿** —— 捐不捐功能完全一样，不会有任何功能差异或特殊对待，纯粹是对作者的支持和认可
- **官方唯一捐款渠道：** [爱发电（Afdian）](https://ifdian.net/a/xuhaun) —— ifdian.net/a/xuhaun
- **内部交流群：** QQ 群 `1097283005`（可在群内拷打作者本人）
- **防骗警告：** 除上述爱发电链接和 QQ 群内与作者本人直接联系外，**任何其他渠道声称代表本插件接受捐款的皆为骗子**，请务必提高警惕，谨防上当受骗

## 这插件能做什么

你可以把它理解成一条直播链路：

```text
B 站直播间事件 -> AstrBot 记忆/人格/工具链 -> 回复文本/语音
                                      -> Live2D 表情动作
                                      -> OBS 透明字幕
                                      -> 嘴型联动
                                      -> 直播记忆与下播小结
```

主要功能：

| 功能 | 能力 |
|---|---|
| B 站弹幕监听 | 读取公开直播间弹幕、礼物、SC、点赞、进场、上舰等事件 |
| 分区识别 | 启动时拉取 B 站直播分区列表，支持 `/分区 英雄联盟`、`/分区 yingxionglianmeng`、`/分区 86` |
| 直播上下文 | 把最近直播事件注入给 LLM，让 Bot 知道观众刚刚说了什么 |
| 弹幕自动回应 | 把弹幕事件投递回 AstrBot 原生事件链路，继续吃人格、世界书、记忆、TTS、分段等插件效果 |
| VTube Studio | 自动发现、认证、列出热键/表情、触发热键、切换表情、移动模型、注入参数 |
| 自主 Live2D | LLM 可输出 `<l2d:标签>`，插件截获后触发对应 VTS 热键 |
| Soullink Emotion | 可选连续 VAD、FACS、Idle、视线、呼吸和动作混合；关闭或异常时保留原有热键链路 |
| OBS 字幕 | 本地透明网页字幕层，支持打字机、淡出、描边、位置、最大长度 |
| OBS 开播控制 | 拓展页可启动 OBS/L2DStudio、切场景、开虚拟摄像机、录制、推流 |
| TTS 嘴型 | 等待本地 wav 语音生成后，按音量包络驱动 Live2D 嘴部参数 |
| 直播记忆 | 记录观众活跃、常聊话题、未完问题、高光事件、下播小结 |
| 陪伴插件联动 | 读取关系网和群聊观察，写回直播记忆，并注册“主动开播/下播”外部能力 |

## 推荐使用路线

第一次不要一次性打开所有功能。建议按下面顺序跑通。

### 1. 先连上 VTube Studio

1. 打开 VTube Studio。
2. 在 VTS 设置中开启插件 API，默认端口通常是 `8001`。
3. 在 AstrBot 聊天里发送：

```text
/vts_auth
```

4. VTube Studio 弹出授权窗口后点击允许。
5. 检查连接：

```text
/vts_status
/vts_list
```

如果你只想让 Bot 控制 Live2D，到这里就已经可以开始配置 `l2d_hotkeys` 了。

### 2. 再接入 B 站弹幕

配置里开启：

```text
bilibili_enabled = true
bilibili_type = web
bilibili_room_id = 你的直播间房间号
```

然后启动监听：

```text
/bili_live_start
```

查看最近事件：

```text
/bili_live_recent
```

如果只是临时监听某个房间，也可以：

```text
/bili_live_start 123456
```

### 3. 设置直播分区

插件启动时会拉取 B 站公开直播分区列表，并缓存成映射表。你可以用子分区名、拼音或 `area_id` 设置分区：

```text
/分区 英雄联盟
/分区 yingxionglianmeng
/分区 86
```

例如 `86` 会反查为：

```text
part_id = 2
area_id = 86
网游 / 英雄联盟
```

刷新分区缓存：

```text
/分区 刷新
```

注意：如果 B 站接口标记某个分区 `lock_status=1`，Bot 会提示该分区可能受限。当前插件会保存 `part_id` / `area_id`，但不会直接调用 B 站房间信息接口修改真实直播间标题或分区。

### 4. 让 Bot 自动回应弹幕

在你希望 Bot 输出直播回应的聊天里发送：

```text
/bili_live_bind_here
```

然后配置里开启：

```text
bili_live_auto_reply_enabled = true
bili_live_auto_reply_mode = native
```

推荐使用 `native` 模式。它会把直播事件投递回 AstrBot 原生消息链路，让自动回应继续使用当前人格、世界书、记忆、TTS、字幕和其它插件。

常用限流项：

| 配置 | 说明 |
|---|---|
| `bili_live_auto_reply_cooldown_seconds` | 两次自动回应之间的冷却 |
| `bili_live_auto_reply_max_per_minute` | 每分钟最多回应多少次，`0` 表示不限 |
| `bili_live_auto_reply_min_events` | 至少积累多少条事件再回应 |
| `bili_live_auto_reply_max_events` | 每次参考最近多少条事件 |
| `bili_live_auto_reply_air_guard_enabled` | 启用直播读空气降噪，避免每条轻寒暄都回复 |
| `bili_live_auto_reply_air_guard_model_enabled` | 边界模糊时联动陪伴插件读空气模型 |
| `bili_live_auto_reply_air_guard_threshold` | 本地规则开口阈值，越高越少回复 |
| `bili_live_auto_reply_force_full_tts` | 自动回应是否强制走完整语音链路 |
| `bili_live_auto_reply_sync_tts_subtitle` | 等待 TTS 生成后，同步发送语音、文字和 OBS 打字机字幕 |
| `bili_live_tts_local_playback_enabled` | TTS 音频生成后由直播插件直接本机播放，Windows 会优先走兼容性更好的 MediaPlayer |
| `bili_live_reply_identity_mode` | 直播回复身份：`host` 主播模式，`assistant` 主播助理模式 |
| `bili_live_streamer_identity_from_companion_enabled` | 主播助理模式下从陪伴插件读取主要用户称呼/身份 |
| `bili_live_streamer_display_name` | 主播显示名覆盖，留空则自动推断 |

如果 Bot 一直在和弹幕打招呼，建议保持 `bili_live_auto_reply_air_guard_enabled = true`。默认规则会静默单条“你好 / 来了 / 贴贴 / 哈哈 / 6 / 晚安”等轻互动；有具体问题、请求、纠错、多人连续话题，或礼物、SC、上舰时仍会正常回应。

身份模式：

- `host`：主播模式。Bot 以主播/Bot 本人的身份直接回应弹幕，适合虚拟主播本人开播。
- `assistant`：主播助理模式。Bot 作为辅助用户直播的聊天助手/场控助理回应弹幕，不假装自己是主播，适合真人或另一个主播开播时让 Bot 帮忙看弹幕。

主播助理模式下，插件会优先使用 `bili_live_streamer_display_name`；留空时会从陪伴插件主要用户的昵称、关系网登记名、别名和身份说明中推断主播称呼。仍找不到时回退为“主播”。

### 5. 打开 OBS 字幕

配置里开启：

```text
subtitle_enabled = true
subtitle_scope = bili_live
subtitle_host = 127.0.0.1
subtitle_port = 18081
```

默认字幕地址：

```text
http://127.0.0.1:18081/
```

在 OBS 中添加“浏览器源”，URL 填这个地址，背景保持透明。可以用命令测试：

```text
/subtitle_status
/subtitle_test 这是一条直播字幕测试。
/subtitle_clear
```

字幕会自动清理 `<l2d:...>`、TTS 控制块和常见 HTML/尖括号标签，避免控制指令出现在画面上。

默认 `subtitle_scope=bili_live` 时，只有 B 站直播自动回应、直播 TTS 字幕、手动测试和拓展页预览会进入 OBS 打字机，普通 QQ 聊天不会显示在直播字幕层。

如果你确实希望所有 Bot 回复都进入 OBS 打字机，可以把触发范围改成：

```text
subtitle_scope = all
```

### 5.1 AstrBot 和 OBS 不在同一台机器：让 TTS 从浏览器源出声

`bili_live_tts_local_playback_enabled` 是在 **AstrBot 所在机器**上播放音频。如果 AstrBot 跑在服务器、OBS 在本机，服务器上播出来的声音进不了直播间。这种情况改用网页播放：TTS 音频推送到字幕 overlay 页面，由 OBS 浏览器源播放。

配置里开启：

```text
subtitle_enabled = true
subtitle_host = 0.0.0.0
bili_live_tts_web_playback_enabled = true
```

`subtitle_host` 必须改成 `0.0.0.0` 或服务器局域网 IP，默认的 `127.0.0.1` 只监听本机，直播机连不上。

OBS 浏览器源的 URL 也要换成服务器地址：

```text
http://<服务器局域网IP>:18081/
```

字幕和语音走同一个页面、同一个端口，所以浏览器源只需要加一个。加好之后，在 OBS 混音器里把这个浏览器源的音频路由进直播流的音频通道，观众才能听到。

本机播放和网页播放互不影响，可以同时开；服务器上没有声卡或播放器时，把 `bili_live_tts_local_playback_enabled` 关掉即可。

### 6. 接上 TTS 嘴型

配置里开启：

```text
mouth_sync_enabled = true
mouth_sync_open_parameter = MouthOpen
mouth_sync_form_parameter =
```

测试：

```text
/mouth_sync_test 2
```

嘴型联动依赖本地 `wav` 音频文件。如果 TTS 插件只返回远程 URL，或者格式不是本地 wav，嘴型会跳过。直播时可以继续使用 VTube Studio 自带麦克风/虚拟声卡作为兜底。

### 7. 使用 OBS 开播控制

如果要让插件控制 OBS，先配置：

```text
obs_control_enabled = true
obs_exe_path = C:\Program Files\obs-studio\bin\64bit\obs64.exe
l2dstudio_exe_path = L2DStudio 的 exe 路径
obs_ws_host = 127.0.0.1
obs_ws_port = 4455
obs_ws_password = OBS WebSocket 密码
obs_live_scene_name = 默认直播场景名
```

然后在插件拓展页“直播面板”中操作：

- 打开 OBS / L2DStudio。
- 检查 OBS WebSocket。
- 切换默认直播场景。
- 开启虚拟摄像机。
- 开始/停止录制。
- 开始/停止推流。

真正推流还需要额外开启：

```text
obs_allow_stream_start = true
```

并且拓展页会要求二次确认。建议先在 OBS 内手动确认 B 站推流流程可用。B 站直播可以配合 `obs-bilibili-stream`：

```text
https://github.com/Zarosmm/obs-bilibili-stream/releases
```

## 与“我会永远陪着你”联动

如果同一 AstrBot 中安装并运行了 `astrbot_plugin_private_companion`，本插件会自动尝试接入。
如果同时安装了 `astrbot_plugin_livingmemory`，直播自动回应会用最近弹幕生成轻量召回查询，读取少量长期记忆作为背景，但不会直接写入 LivingMemory，避免临时弹幕污染长期库。

### 直播上下文增强

直播间观众发弹幕时，插件会尝试用直播用户名匹配陪伴插件里的关系网姓名、别名、观察名。匹配到后，可以把这个用户最近在 QQ 群里的公开发言作为候选线索注入给 LLM。

这样 Bot 可以更自然地承接熟人互动，例如：

```text
你刚刚还在群里聊这个，怎么这么快就跑到直播间来了。
```

这是候选匹配，不是强身份认证。提示词会要求模型不要说出 QQ 号、关系网、匹配过程或内部备注。

### 直播事件写回

默认会把直播相关信息写回陪伴插件的数据区：

| 写回内容 | 说明 |
|---|---|
| 观众活跃画像 | 记录谁常来、常聊什么、最近弹幕和重要互动 |
| 重要互动记忆 | 默认只把礼物、SC、上舰等写入关系重要记忆 |
| 候选直播观众 | 陌生观众多次出现后，创建 `bili_live_*` 候选关系节点 |
| LivingMemory 召回 | 自动回应前读取与观众名、弹幕内容、直播主题相关的少量长期记忆 |
| 直播状态余韵 | 礼物、SC、高频互动会影响 Bot 当日状态 |
| 下播小结 | 停止监听或监听结束时生成直播小结/日记 |

### 主动开播/下播

1.5.0 起，本插件会向陪伴插件注册两个“外部主动能力”：

| 能力名 | 作用 |
|---|---|
| `live_stream_start` | 准备开播：选择分区、拟定标题，可启动监听、打开 OBS/L2DStudio，可按配置开始 OBS 推流 |
| `live_stream_stop` | 结束直播：可停止 OBS 推流、停止弹幕监听，并触发下播小结 |

这两个能力默认不启用。需要到：

```text
陪伴面板 / 模块配置 / 外部主动能力
```

手动启用并配置。

安全规则：

- 默认只会准备开播素材，不会推流。
- `live_stream_start` 的外部能力配置里必须设置 `start_obs_stream=true`。
- 本插件配置里也必须设置 `obs_allow_stream_start=true`。
- 两个条件都满足，才会调用 OBS `StartStream`。
- 当前版本只会拟定直播标题并放进主动上下文，不会直接调用 B 站接口设置真实直播间标题。

## 与 Bilibili AI Bot 联动

同一 AstrBot 中安装 `astrbot_plugin_bilibili_ai_bot` 1.3.1+ 后，直播插件会使用弹幕事件
自带的 B站 UID 做精确联动，不依赖昵称猜测身份。

- 收到弹幕、礼物、SC、上舰等事件后，将事件写入 BiliBot 的直播向量记忆，并更新该 UID 的画像统计。
- 自动回应前读取该 UID 的画像与相关交流/直播记忆；视频详细内容只从该用户关联的视频集合里按语义召回。
- 观众询问“今天/最近看了什么”时，直播插件会在生成前直接读取 BiliBot 活动记忆，避免 Agent 重复调用查询工具。
- 用户画像只使用轻量视频关系，不把整段视频总结复制进画像。
- 可通过 `bilibili_ai_memory_integration_enabled` 关闭；未安装 BiliBot 时自动跳过，不影响直播功能。
- 开启直播自动回应后，SC 默认不受普通事件列表、冷却、最少事件数、读空气或每分钟限流影响；同一事件 ID 只鸣谢一次，并会点名发送者后继续回应 SC 正文。

## 拓展页

插件提供 AstrBot Pages 拓展页：

```text
pages/直播面板/
```

在 AstrBot WebUI 的插件详情页打开“直播面板”后，可以查看和操作：

- B 站监听状态。
- OBS 控制状态。
- VTube Studio / 字幕 / 嘴型链路。
- Soullink Emotion 实时测试台、VAD/FACS 状态和 VTS 参数目录。
- 自动回应状态。
- 直播专用记忆。
- 观众活跃画像。
- 最近直播事件。
- 插件主要配置。

后端 API 前缀：

```text
/astrbot_plugin_live_stream_companion/page
```

## 常用命令

### VTube Studio

```text
/vts_auth
/vts_status
/vts_discover
/vts_list
/vts_l2d_list
/soullink_status
/soullink_test happy 0.8
```

### B 站直播

```text
/bili_live_start [房间号]
/bili_live_stop
/bili_live_status
/bili_live_recent [数量]
/bili_live_memory [数量]
/bili_live_integration_status
/bili_live_bind_here
/bili_live_probe <房间号>
/bili_live_debug true|false
/分区 <名称/拼音/area_id>
```

### 字幕与嘴型

```text
/subtitle_status
/subtitle_test [文本]
/subtitle_clear
/mouth_sync_test 2
```

## 核心配置速查

### 直播监听

| 配置 | 默认 | 说明 |
|---|---:|---|
| `bilibili_enabled` | `false` | B 站直播功能总开关 |
| `bilibili_type` | `web` | `web` 或 `open_live` |
| `bilibili_room_id` | `0` | 直播间房间号 |
| `bilibili_web_backend` | `builtin` | `builtin` / `history` / `laplace` / `blivedm` |
| `bilibili_sessdata` | `""` | 可选 B 站 Cookie 或 SESSDATA |
| `part_id` | `0` | 父分区 ID，建议用 `/分区` 自动设置 |
| `area_id` | `0` | 子分区 ID，建议用 `/分区` 自动设置 |

`open_live` 模式还需要：

```text
bilibili_ACCESS_KEY_ID
bilibili_ACCESS_KEY_SECRET
bilibili_APP_ID
bilibili_ROOM_OWNER_AUTH_CODE
```

### 弹幕注入和自动回应

| 配置 | 默认 | 说明 |
|---|---:|---|
| `bili_live_inject_enabled` | `true` | 回复前注入最近直播事件 |
| `bili_live_inject_max_events` | `8` | 每次注入多少条 |
| `bili_live_cache_size` | `80` | 内存事件缓存数量 |
| `bili_live_auto_reply_enabled` | `false` | 是否自动回应弹幕 |
| `bili_live_auto_reply_mode` | `native` | 推荐 `native` |
| `bili_live_auto_reply_max_per_minute` | `6` | 每分钟最多自动回应 |
| `bili_live_auto_reply_sync_tts_subtitle` | `true` | 开启后直播自动回应等待 TTS，并与打字机字幕同步 |
| `bili_live_tts_local_playback_enabled` | `true` | 直播 TTS 生成后由本插件直接本机播放 |
| `bili_live_tts_web_playback_enabled` | `false` | 直播 TTS 推送到字幕 overlay 页面，由 OBS 浏览器源播放；跨机器部署时用它替代本机播放 |

### OBS 和字幕

| 配置 | 默认 | 说明 |
|---|---:|---|
| `subtitle_enabled` | `false` | 启用透明字幕层 |
| `subtitle_scope` | `bili_live` | `bili_live` 只显示直播自动回应，`all` 显示所有 Bot 回复 |
| `subtitle_host` | `127.0.0.1` | 字幕/音频服务监听地址；跨机器时改 `0.0.0.0` 或服务器局域网 IP |
| `subtitle_port` | `18081` | 字幕网页端口 |
| `obs_control_enabled` | `false` | 启用 OBS 控制 |
| `obs_allow_stream_start` | `false` | 是否允许插件调用 OBS 推流 |
| `obs_live_scene_name` | `""` | 默认直播场景 |

### 嘴型

| 配置 | 默认 | 说明 |
|---|---:|---|
| `mouth_sync_enabled` | `false` | 启用嘴型联动 |
| `mouth_sync_open_parameter` | `MouthOpen` | VTS 嘴部开闭追踪输入；不能填写 Live2D 输出 ID |
| `mouth_sync_form_parameter` | `""` | 可选 VTS 追踪输入；Soullink 启用时建议留空 |
| `mouth_sync_fps` | `30` | 每秒推送次数 |

### Soullink Emotion（可选）

| 配置 | 默认 | 说明 |
|---|---:|---|
| `soullink_enabled` | `false` | 总开关，升级后不会改变原有行为 |
| `soullink_mode` | `emotion` | `emotion` 使用提示词意图；`full` 也启用本地文本分类降级 |
| `soullink_motion_style` | `natural` | `natural` / `lively` / `calm` / `shy` |
| `soullink_fps` | `20` | VTS 实时参数帧率 |
| `soullink_prompt_intent_enabled` | `true` | 通过提示词让模型附加不可见的结构化情绪意图 |
| `soullink_parameter_gain` | `1.7` | 表情参数相对中性值的增益 |
| `soullink_body_motion_gain` | `1.6` | 头部、身体与 Idle 动作增益 |
| `soullink_vad_decay_rate` | `0.075` | 情绪回落速度 |
| `soullink_vts_mapping` | `{}` | 高级 JSON 映射；空对象使用内置 VTS 追踪参数映射 |

Soullink 需要 Node.js 18 或更高版本。插件内置固定版本的 `@soullink-emotion/engine@0.1.0-beta.1` ESM 运行文件，只在开启后启动 Node 子进程，不需要安装 `node_modules`。

拓展页的“Soullink 测试台”可以：

- 触发开心、兴奋、害羞、好奇、困惑、关切、难过和生气等情绪。
- 调整强度与 VAD 三轴，并切换动作风格。
- 查看连续 FACS 通道、当前状态和最终 VTS 输入值。
- 读取 VTS 追踪输入及当前 Live2D 模型参数，辅助校准 `soullink_vts_mapping`。
- 从本机选择包含 `.model3.json`、`.moc3`、纹理及关联资源的模型文件夹，在页面内直接渲染 Live2D 模型并接受当前 FACS 参数驱动；文件只在浏览器本地读取，不会上传。模型载入后可使用缩放按钮、滑杆、鼠标滚轮或移动端双指手势调整预览大小，窗口变化时会保留当前倍率。

未导入模型时，测试台使用插件图像做实时状态可视化。页面内 Live2D 预览按需从 Live2D 官方地址加载 Cubism Core，因此首次导入需要网络；VTube Studio 仍负责直播时的真实模型输出。Soullink 与 TTS 嘴型共用帧调度器，嘴型只覆盖同名嘴部通道，不会中断头部、视线和表情参数。

### 陪伴插件联动

| 配置 | 默认 | 说明 |
|---|---:|---|
| `private_companion_live_context_enabled` | `true` | 读取关系网和群聊观察 |
| `private_companion_writeback_enabled` | `true` | 写回直播事件 |
| `private_companion_viewer_activity_enabled` | `true` | 记录观众活跃画像 |
| `private_companion_auto_register_viewers` | `true` | 自动登记候选直播观众 |
| `private_companion_live_summary_enabled` | `true` | 下播生成小结 |
| `live_memory_enabled` | `true` | 启用直播专用记忆 |
| `live_memory_context_enabled` | `true` | 注入直播专用记忆 |

## LLM 工具

插件提供两个直播相关 LLM 工具：

| 工具 | 说明 |
|---|---|
| `bili_live_recent_danmaku` | 读取最近直播弹幕和事件 |
| `bili_live_memory_context` | 读取直播专用记忆上下文 |

模型适合在这些场景调用：

- 用户问“直播间刚刚说什么”。
- 用户要求 Bot 回应某条弹幕。
- 用户问最近直播常聊什么。
- 自动回应需要更多直播上下文。

## 常见问题

### VTube Studio 没有弹授权窗口

检查：

- VTS 是否已启动。
- VTS 插件 API 是否开启。
- `vts_host` / `vts_port` 是否正确。
- 发送 `/vts_discover` 后再试 `/vts_auth`。

### 直播监听启动了但没有弹幕

检查：

- `bilibili_enabled` 是否开启。
- 房间号是否正确。
- 直播间是否正在直播。
- 尝试 `/bili_live_probe <房间号>`。
- `bilibili_web_backend` 建议使用 `builtin`；如果 `getDanmuInfo` 返回 `-352` 但历史弹幕可读，可改成 `history` 只用历史轮询；只有额外启动了 Laplace Event Bridge 时再改成 `laplace`。
- 开启 `/bili_live_debug true` 查看原始事件。

### 自动回应没有输出

检查：

- 是否发送过 `/bili_live_bind_here`。
- `bili_live_auto_reply_enabled` 是否开启。
- 自动回应是否被冷却或每分钟限流挡住。
- 是否已经读到符合触发类型的直播事件。

### OBS 无法推流

检查：

- OBS 是否开启 WebSocket。
- `obs_ws_host` / `obs_ws_port` / `obs_ws_password` 是否正确。
- `obs_control_enabled` 是否开启。
- `obs_allow_stream_start` 是否开启。
- OBS 内是否已配置 B 站推流方式。

### 主动开播没有真正开始推流

这是默认安全行为。需要同时满足：

```text
陪伴插件外部能力 live_stream_start 已启用
live_stream_start 配置 start_obs_stream = true
本插件配置 obs_allow_stream_start = true
OBS WebSocket 可连接
```

否则只会准备开播素材、启动监听或打开 OBS/L2DStudio。

## 文件结构

```text
main.py              插件主体、命令、直播上下文、陪伴插件联动
bilibili_live.py     B 站 Web / Open Live 客户端、分区列表
vts_client.py        VTube Studio API 客户端
vts_discovery.py     VTS 自动发现
subtitle_server.py   透明字幕网页服务
subtitle_mixin.py    字幕配置和推送
mouth_sync_mixin.py  TTS 嘴型联动
l2d_mixin.py         自主 Live2D 标签
soullink_mixin.py    Soullink 提示词、意图解析与 VTS 参数映射
soullink_runtime.py  Python/Node 异步运行桥
soullink_bridge.mjs  Soullink Emotion 无头运行进程
vts_parameter_scheduler.py  情绪与嘴型实时参数合并调度
vendor/soullink_emotion_engine/  固定版本 Soullink Engine ESM 与 MIT 许可证
page_api.py          拓展页后端 API
page_config.py       拓展页配置读写
pages/直播面板/      前端页面
pages/直播面板/vendor/live2d_preview/  页面预览用 PIXI / Live2D 适配器及 MIT 许可证
_conf_schema.json    AstrBot 配置 schema
metadata.yaml        插件元数据
```

## 使用建议

- 先跑通 VTS 认证，再接 B 站弹幕。
- 自动回应先低频开启，确认人格和 TTS 链路稳定后再提高频率。
- OBS 推流和陪伴插件主动开播都属于高风险动作，建议先在线下测试。
- 分区可以交给 `/分区` 命令维护，避免手动填错 `part_id`。
- 直播记忆和陪伴插件写回默认适合长期使用，但如果你只想临时试播，可以关闭 `private_companion_writeback_enabled`。

## 致谢

- `blivedm`：B 站直播弹幕协议解析参考。
- AstrBot 社区：插件框架、LLM 工具和 Pages 扩展页能力。
- VTube Studio：Live2D 模型控制 API。
- Soullink Emotion SDK：连续 VAD、FACS 和角色表演引擎（MIT）。
- PixiJS / pixi-live2d-display：拓展页 Live2D 模型预览（MIT）；Cubism Core 由 Live2D 官方地址按需加载。


