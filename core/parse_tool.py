"""
Shared tool-call parsing for the God Agent (walk / chat / interact only).
"""
import re
from typing import Optional
from .models import ToolCall


GOD_TOOLS = ("walk", "chat", "interact")


def parse_tool_call(text: str) -> Optional[ToolCall]:
    """Parse the first matching walk/chat/interact call from text."""
    if not text:
        return None

    patterns = {
        "walk": r'walk\s*\(\s*destination\s*=\s*["\']([^"\']+)["\']\s*\)',
        "chat": (
            r'chat\s*\(\s*target\s*=\s*["\']([^"\']+)["\']\s*,\s*'
            r'message\s*=\s*["\'](.+?)["\']\s*\)'
        ),
        "interact": (
            r'interact\s*\(\s*object\s*=\s*["\']([^"\']+)["\']\s*,\s*'
            r'action\s*=\s*["\'](.+?)["\']\s*\)'
        ),
    }

    for tool, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        if tool == "walk":
            return ToolCall(tool="walk", args={"destination": match.group(1).strip()})
        if tool == "chat":
            return ToolCall(
                tool="chat",
                args={
                    "target": match.group(1).strip(),
                    "message": match.group(2).strip(),
                },
            )
        if tool == "interact":
            return ToolCall(
                tool="interact",
                args={
                    "object": match.group(1).strip(),
                    "action": match.group(2).strip(),
                },
            )
    return None
