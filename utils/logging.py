"""
Logging utilities for the Butler Agent.

This module provides functionality for logging tool calls and other operations
in a structured, readable format for debugging and monitoring purposes.
"""

import json
from datetime import datetime

from config.settings import TOOL_CALL_LOG_PATH


def shorten_text(text: str, limit: int = 400) -> str:
    """
    Shorten text for logging purposes by removing newlines and truncating.

    Args:
        text: The text to shorten
        limit: Maximum length before truncation (default: 400)

    Returns:
        Shortened text with ellipsis if truncated
    """
    s = text.strip().replace("\n", " ")
    return (s[:limit] + "…") if len(s) > limit else s


def log_tool_call(name: str, args: dict, result: str | dict) -> None:
    """
    Log a tool call with its arguments and result in markdown format.

    Creates a structured log entry with timestamp, tool name, arguments,
    and truncated result. The log is appended to the configured log file.

    Args:
        name: Name of the tool that was called
        args: Dictionary of arguments passed to the tool
        result: Result returned by the tool (string or dictionary)

    Note:
        Errors during logging are caught and printed to avoid disrupting
        the main application flow.
    """
    try:
        TOOL_CALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y‑%m‑%d %H:%M:%S")

        md = [
            f"### {ts} — {name}\n",
        ]

        if args:
            args_str = json.dumps(args, ensure_ascii=False)
            label = "Args"
            if len(args_str) > 600:
                args_str = shorten_text(args_str, 600)
                label += " (truncated)"
            md.append(f"**{label}:** `{args_str}`\n")

        label = "Result"
        if len(result) > 600:
            result = shorten_text(result, 600)
            label += " (truncated)"
        md.append(f"**{label}:** `{result}`\n")

        with open(TOOL_CALL_LOG_PATH, "a", encoding="utf-8") as lf:
            lf.writelines(md)

    except Exception as e:
        print(f"[log-error] {e}")
