"""Tests for the log scanning logic extracted from main.py."""

import datetime
import sys
from unittest.mock import MagicMock

# Mock astrbot modules before importing main
for mod in [
    "astrbot", "astrbot.api", "astrbot.api.event", "astrbot.api.event.filter",
    "astrbot.api.message_components", "astrbot.api.star",
    "astrbot.core", "astrbot.core.utils", "astrbot.core.utils.astrbot_path",
]:
    sys.modules.setdefault(mod, MagicMock())

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
