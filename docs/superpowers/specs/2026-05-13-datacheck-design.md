# astrbot_plugin_datacheck 设计文档

## 概述

AstrBot 插件，用于查询 AstrBot 自身日志中近 N 小时内的错误记录，通过 OneBot V11 合并转发消息发送给用户。支持两种触发方式：用户指令 `/查日志` 和 LLM 意图识别（用户提到签到失败、掉线等场景时自动调用）。

## 架构

单文件插件（`main.py`），包含三个核心部分：

1. **指令处理器** `@filter.command("查日志")` — 确定性触发
2. **LLM 工具** `@filter.llm_tool("check_error_log")` — LLM 意图识别触发
3. **日志扫描核心** `_scan_error_logs()` — 共享的日志解析逻辑

两种触发路径共享权限检查和日志扫描逻辑。使用 `@filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)` 限制仅 OneBot V11 平台生效。

## 数据流

```
用户消息 ──┬── "/查日志" ──> command handler ──┐
           │                                    │
           └── "签到失败了吗" ──> LLM ──> llm_tool ──> _scan_error_logs()
                                                │
                                                ├── 读取 AstrBot 日志文件
                                                ├── 筛选近 N 小时内的 ERROR/CRIT 记录
                                                ├── 构造 Node/Nodes 合并转发消息
                                                └── event.send() 发送给用户
```

## 日志文件定位

- 路径：`{astrbot_data_path}/logs/astrbot.log`，通过 `astrbot.core.utils.astrbot_path.get_astrbot_data_path()` 获取
- 同时扫描轮转文件（`astrbot.log.1`、`astrbot.log.2` 等）
- 日志格式：`[YYYY-MM-DD HH:mm:ss.SSS] [Core/Plug] [ERRO] [vX.X.X] [module.file:line]: message`

## 日志扫描逻辑

1. 收集 `logs/` 目录下 `astrbot.log*` 文件
2. 逐行解析，用正则匹配行首时间戳 `\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]`
3. 时间过滤：仅保留 `now - hours` 之内的记录
4. 级别过滤：仅保留包含 `[ERRO]` 或 `[CRIT]` 的行
5. 多行合并：无时间戳开头的行属于上一条日志的延续（如 traceback）
6. 结果上限：最多 100 条错误记录

## 消息构造

错误记录封装为 `Nodes`（合并转发），每条错误一个 `Node`：

```python
Node(content=[Plain(error_text)], uin="0", name="AstrBot 日志")
```

通过 `event.send(MessageChain([Nodes(nodes)]))` 发送。aiocqhttp 适配器自动调用 `send_group_forward_msg` / `send_private_forward_msg`。

## 权限控制

- 配置项 `admin_only`（默认 `true`）控制是否仅管理员可用
- 指令和 LLM 工具共用同一权限检查
- 权限不足时：指令返回提示文本，LLM 工具返回字符串由 LLM 转述

## 插件配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `admin_only` | bool | true | 仅管理员可用 |
| `hours` | number | 24 | 扫描多少小时内的日志 |

## 边界情况

- 无错误记录：返回纯文本 "近 N 小时内未发现错误日志"
- 日志文件不存在：返回 "未找到日志文件，请确认 AstrBot 已启用文件日志"
- LLM 工具返回：简要摘要字符串（如 "发现 5 条错误记录，已通过合并转发发送"），LLM 据此回复用户
- 错误记录超过 100 条：截断并提示
