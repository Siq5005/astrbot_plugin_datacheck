# astrbot_plugin_datacheck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AstrBot plugin that scans AstrBot log files for recent errors and sends them as OneBot V11 forward messages, triggered by `/查日志` command or LLM intent recognition.

**Architecture:** Single-file plugin (`main.py`) with a shared `_scan_error_logs()` method called by both a `@filter.command` handler and a `@filter.llm_tool` handler. Plugin config (`_conf_schema.json`) controls admin-only access and scan time window. Platform restricted to OneBot V11 via `@filter.platform_adapter_type`.

**Tech Stack:** Python 3, AstrBot plugin API (`astrbot.api`), OneBot V11 (`aiocqhttp` adapter), loguru log files.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `main.py` | Rewrite | Plugin class with command handler, LLM tool, log scanning logic |
| `metadata.yaml` | Modify | Plugin identity (name, author, desc, version) |
| `_conf_schema.json` | Create | Plugin configuration schema (admin_only, hours) |
| `tests/test_log_scanner.py` | Create | Unit tests for log parsing logic |

---

### Task 1: Update plugin metadata

**Files:**
- Modify: `metadata.yaml`

- [ ] **Step 1: Rewrite metadata.yaml**

```yaml
name: astrbot_plugin_datacheck
display_name: 日志错误查询
desc: 查询 AstrBot 近 N 小时内的错误日志，通过合并转发发送。支持指令和 LLM 意图识别触发。
version: v1.0.0
author: Coe
repo: ""
```

- [ ] **Step 2: Commit**

```bash
git add metadata.yaml
git commit -m "chore: update metadata for datacheck plugin"
```

---

### Task 2: Create plugin configuration schema

**Files:**
- Create: `_conf_schema.json`

- [ ] **Step 1: Create _conf_schema.json**

```json
{
  "admin_only": {
    "description": "仅管理员可查询日志",
    "type": "bool",
    "default": true
  },
  "hours": {
    "description": "扫描最近多少小时内的日志",
    "type": "int",
    "default": 24
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add _conf_schema.json
git commit -m "feat: add plugin config schema for admin_only and hours"
```

---

### Task 3: Write tests for log scanning logic

**Files:**
- Create: `tests/test_log_scanner.py`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p tests
```

- [ ] **Step 2: Write test file**

The log scanner is a pure function that takes lines of text and a cutoff datetime, and returns a list of error entry strings. We test it in isolation.

```python
"""Tests for the log scanning logic extracted from main.py."""

import datetime

from main import parse_error_entries


class TestParseErrorEntries:
    def test_basic_error_line(self):
        lines = [
            "[2026-05-13 10:00:00.000] [Core] [ERRO] [module.file:42]: something broke\n"
        ]
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff)
        assert len(result) == 1
        assert "something broke" in result[0]

    def test_filters_out_info_lines(self):
        lines = [
            "[2026-05-13 10:00:00.000] [Core] [INFO] [module.file:1]: all good\n",
            "[2026-05-13 10:00:01.000] [Core] [ERRO] [module.file:2]: bad thing\n",
        ]
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff)
        assert len(result) == 1
        assert "bad thing" in result[0]

    def test_filters_out_old_entries(self):
        lines = [
            "[2026-05-12 08:00:00.000] [Core] [ERRO] [module.file:1]: old error\n",
            "[2026-05-13 10:00:00.000] [Core] [ERRO] [module.file:2]: new error\n",
        ]
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff)
        assert len(result) == 1
        assert "new error" in result[0]

    def test_multiline_traceback(self):
        lines = [
            "[2026-05-13 10:00:00.000] [Core] [ERRO] [module.file:1]: error with traceback\n",
            "Traceback (most recent call last):\n",
            '  File "foo.py", line 10, in bar\n',
            "ValueError: oops\n",
            "[2026-05-13 10:00:01.000] [Core] [INFO] [module.file:2]: next entry\n",
        ]
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff)
        assert len(result) == 1
        assert "Traceback" in result[0]
        assert "ValueError: oops" in result[0]

    def test_crit_level_included(self):
        lines = [
            "[2026-05-13 10:00:00.000] [Core] [CRIT] [module.file:1]: critical failure\n"
        ]
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff)
        assert len(result) == 1
        assert "critical failure" in result[0]

    def test_empty_input(self):
        result = parse_error_entries([], datetime.datetime(2026, 5, 13, 9, 0, 0))
        assert result == []

    def test_max_entries_cap(self):
        lines = []
        for i in range(150):
            lines.append(
                f"[2026-05-13 10:00:00.000] [Core] [ERRO] [module.file:{i}]: error {i}\n"
            )
        cutoff = datetime.datetime(2026, 5, 13, 9, 0, 0)
        result = parse_error_entries(lines, cutoff, max_entries=100)
        assert len(result) == 100
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/coe/project/astrbot_plugin_datacheck && python -m pytest tests/test_log_scanner.py -v
```

Expected: FAIL — `ImportError: cannot import name 'parse_error_entries' from 'main'`

- [ ] **Step 4: Commit**

```bash
git add tests/test_log_scanner.py
git commit -m "test: add unit tests for log entry parser"
```

---

### Task 4: Implement log scanning logic

**Files:**
- Modify: `main.py`

This task implements the pure parsing function `parse_error_entries()` and the file-scanning wrapper `_scan_error_logs()` as a method on the plugin class.

- [ ] **Step 1: Write parse_error_entries and the plugin skeleton in main.py**

Replace the entire contents of `main.py` with:

```python
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
_ERROR_LEVELS = ("[ERRO]", "[CRIT]")


def parse_error_entries(
    lines: list[str],
    cutoff: datetime.datetime,
    max_entries: int = 100,
) -> list[str]:
    """Parse log lines and return error entries newer than cutoff.

    Args:
        lines: Raw log file lines.
        cutoff: Only include entries at or after this time.
        max_entries: Maximum number of entries to return.

    Returns:
        List of error entry strings (may include multi-line tracebacks).
    """
    entries: list[str] = []
    current_entry: str | None = None
    current_is_error = False
    current_in_range = False

    for line in lines:
        m = _TIMESTAMP_RE.match(line)
        if m:
            if current_entry is not None and current_is_error and current_in_range:
                entries.append(current_entry)
                if len(entries) >= max_entries:
                    break
            ts = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            current_entry = line.rstrip("\n")
            current_is_error = any(lvl in line for lvl in _ERROR_LEVELS)
            current_in_range = ts >= cutoff
        else:
            if current_entry is not None:
                current_entry += "\n" + line.rstrip("\n")

    if (
        current_entry is not None
        and current_is_error
        and current_in_range
        and len(entries) < max_entries
    ):
        entries.append(current_entry)

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

    def _scan_error_logs(self) -> list[str]:
        hours = self.config.get("hours", 24)
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)

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
            entries = parse_error_entries(file_lines, cutoff)
            all_entries.extend(entries)
            if len(all_entries) >= 100:
                all_entries = all_entries[:100]
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
            yield event.plain_result(f"近 {hours} 小时内未发现错误日志。")
            return

        nodes = []
        for entry in entries:
            nodes.append(Node(content=[Plain(entry)], uin="0", name="AstrBot 日志"))

        if len(entries) >= 100:
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
            return f"近 {hours} 小时内未发现任何错误日志，AstrBot 运行正常。"

        nodes = []
        for entry in entries:
            nodes.append(Node(content=[Plain(entry)], uin="0", name="AstrBot 日志"))

        await event.send(MessageChain([Nodes(nodes)]))

        return f"已找到 {len(entries)} 条错误记录，已通过合并转发消息发送给用户。"
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd /Users/coe/project/astrbot_plugin_datacheck && python -m pytest tests/test_log_scanner.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: implement log scanner with command and LLM tool handlers"
```

---

### Task 5: Verify tests pass end-to-end

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/coe/project/astrbot_plugin_datacheck && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 2: Verify imports resolve correctly**

```bash
cd /Users/coe/project/astrbot_plugin_datacheck && python -c "from main import parse_error_entries; print('import OK')"
```

Expected: `import OK`

---

### Task 6: Final review and cleanup

**Files:**
- Possibly modify: `main.py` (if any issues found)

- [ ] **Step 1: Review main.py against the design spec**

Check that all spec requirements are covered:
1. ✅ `/查日志` command handler with `@filter.command`
2. ✅ `@filter.llm_tool("check_error_log")` for LLM intent
3. ✅ `@filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)` on both handlers
4. ✅ `_scan_error_logs()` shared logic
5. ✅ `parse_error_entries()` with timestamp regex, level filter, multiline merge, max cap
6. ✅ `Node`/`Nodes` forward message construction
7. ✅ Permission check via `config.get("admin_only", True)`
8. ✅ Edge cases: no errors, no log dir, cap at 100

- [ ] **Step 2: Commit any fixes if needed**

```bash
git add -A && git commit -m "fix: address review feedback"
```

Only run this if changes were made.
