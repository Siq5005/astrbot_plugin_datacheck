from __future__ import annotations

import datetime
import glob
import os
import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.event.filter import PlatformAdapterType
from astrbot.api.message_components import Node, Nodes, Plain
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

_TIMESTAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d{3}\]")
_MAX_ENTRIES = 100


def parse_error_entries(
    lines: list[str],
    cutoff: datetime.datetime,
    levels: tuple[str, ...] = ("[ERRO]", "[CRIT]"),
    keyword_pattern: re.Pattern | None = None,
    max_entries: int = _MAX_ENTRIES,
) -> list[str]:
    entries: list[str] = []
    current_entry: str | None = None
    current_is_match = False
    current_in_range = False

    def _try_append(entry: str) -> bool:
        if keyword_pattern and not keyword_pattern.search(entry):
            return False
        entries.append(entry)
        return len(entries) >= max_entries

    for line in lines:
        m = _TIMESTAMP_RE.match(line)
        if m:
            if current_entry is not None and current_is_match and current_in_range:
                if _try_append(current_entry):
                    break
            ts = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            current_entry = line.rstrip("\r\n")
            current_is_match = any(lvl in line for lvl in levels)
            current_in_range = ts >= cutoff
        else:
            if current_entry is not None:
                current_entry += "\n" + line.rstrip("\r\n")

    if (
        current_entry is not None
        and current_is_match
        and current_in_range
        and len(entries) < max_entries
    ):
        _try_append(current_entry)

    return entries


@register("astrbot_plugin_datacheck", "Coe", "查询 AstrBot 错误日志", "1.0.0")
class DataCheckPlugin(Star):
    """查询 AstrBot 近 N 小时内的错误日志，通过合并转发发送。支持 /查日志 指令和 LLM 意图识别。"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _check_permission(self, event: AstrMessageEvent) -> bool:
        if self.config.get("admin_only", True):
            return event.is_admin()
        return True

    def _build_levels(self) -> tuple[str, ...]:
        level_map = {"WARN": "[WARN]", "ERRO": "[ERRO]", "CRIT": "[CRIT]"}
        log_levels = self.config.get("log_levels", {})
        levels = tuple(v for k, v in level_map.items() if log_levels.get(k, k != "WARN"))
        return levels or ("[ERRO]", "[CRIT]")

    def _build_keyword_pattern(self) -> re.Pattern | None:
        keyword = self.config.get("keyword", "")
        if not keyword:
            return None
        try:
            return re.compile(keyword, re.IGNORECASE)
        except re.error:
            logger.warning(f"无效的关键字正则表达式: {keyword}")
            return None

    def _scan_error_logs(self) -> list[str]:
        hours = self.config.get("hours", 24)
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
        levels = self._build_levels()
        keyword_pattern = self._build_keyword_pattern()

        log_dir = os.path.join(get_astrbot_data_path(), "logs")
        if not os.path.isdir(log_dir):
            return []

        log_files = sorted(glob.glob(os.path.join(log_dir, "astrbot*.log*")))
        if not log_files:
            return []

        all_entries: list[str] = []
        for log_file in log_files:
            try:
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    file_lines = f.readlines()
            except OSError:
                continue
            entries = parse_error_entries(file_lines, cutoff, levels, keyword_pattern)
            all_entries.extend(entries)
            if len(all_entries) >= _MAX_ENTRIES:
                all_entries = all_entries[:_MAX_ENTRIES]
                break

        return all_entries

    @filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)
    @filter.command("查日志")
    async def check_log_command(self, event: AstrMessageEvent):
        """查询近 N 小时内的 AstrBot 错误日志"""
        if not self._check_permission(event):
            yield event.plain_result("权限不足，仅管理员可使用此功能。")
            return

        log_dir = os.path.join(get_astrbot_data_path(), "logs")
        if not os.path.isdir(log_dir):
            yield event.plain_result("未找到日志文件，请确认 AstrBot 已启用文件日志。")
            return

        entries = self._scan_error_logs()
        hours = self.config.get("hours", 24)

        if not entries:
            keyword = self.config.get("keyword", "")
            hint = f"近 {hours} 小时内未发现匹配的日志"
            if keyword:
                hint += f"（关键字: {keyword}）"
            yield event.plain_result(hint + "。")
            return

        nodes = []
        for entry in entries:
            nodes.append(Node(content=[Plain(entry)], uin="0", name="AstrBot 日志"))

        if len(entries) >= _MAX_ENTRIES:
            nodes.append(
                Node(
                    content=[Plain(f"⚠ 错误记录已达上限(100条)，可能还有更多未显示。")],
                    uin="0",
                    name="AstrBot 日志",
                )
            )

        await event.send(MessageChain([Nodes(nodes)]))
        event.stop_event()

    @filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)
    @filter.llm_tool("check_error_log")
    async def check_error_log_tool(self, event: AstrMessageEvent):
        """查询 AstrBot 的错误日志，当用户询问签到是否失败、机器人是否掉线、是否有报错等问题时调用此工具。"""
        if not self._check_permission(event):
            return "用户权限不足，仅管理员可查询错误日志。"

        log_dir = os.path.join(get_astrbot_data_path(), "logs")
        if not os.path.isdir(log_dir):
            return "未找到日志文件，AstrBot 可能未启用文件日志功能。"

        entries = self._scan_error_logs()
        hours = self.config.get("hours", 24)

        if not entries:
            return f"近 {hours} 小时内未发现匹配的日志，AstrBot 运行正常。"

        nodes = []
        for entry in entries:
            nodes.append(Node(content=[Plain(entry)], uin="0", name="AstrBot 日志"))

        await event.send(MessageChain([Nodes(nodes)]))

        return f"已找到 {len(entries)} 条错误记录，已通过合并转发消息发送给用户。"
