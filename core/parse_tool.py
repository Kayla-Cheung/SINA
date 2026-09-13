"""
Shared tool-call parsing for the God Agent (walk / chat / interact only).
"""
import re
import json
from typing import Optional
from .models import ToolCall
from pydantic import BaseModel, ValidationError

GOD_TOOLS = ("walk", "chat", "interact")

class WalkArgs(BaseModel):
    destination: str

class ChatArgs(BaseModel):
    target: str
    message: str

class InteractArgs(BaseModel):
    object: str
    action: str

def parse_tool_call_from_dict(data: dict) -> Optional[ToolCall]:
    """Parse a tool call from a dictionary using Pydantic models."""
    try:
        if not isinstance(data, dict):
            return None

        tool = data.get("tool")
        args = data.get("args")

        if not tool or not isinstance(args, dict):
            return None

        if tool == "walk":
            WalkArgs(**args)
        elif tool == "chat":
            ChatArgs(**args)
        elif tool == "interact":
            InteractArgs(**args)
        else:
            return None

        return ToolCall(**data)
    except (ValidationError, Exception):
        return None

def parse_tool_call(text: str) -> Optional[ToolCall]:
    """Parse the first matching walk/chat/interact call from text."""
    if not text:
        return None

    # Try parsing as JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return parse_tool_call_from_dict(data)
    except (json.JSONDecodeError, TypeError):
        pass

    # Legacy regex fallback for text strings
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
            return parse_tool_call_from_dict({"tool": "walk", "args": {"destination": match.group(1).strip()}})
        if tool == "chat":
            return parse_tool_call_from_dict(
                {"tool": "chat", "args": {"target": match.group(1).strip(), "message": match.group(2).strip()}}
            )
        if tool == "interact":
            return parse_tool_call_from_dict(
                {"tool": "interact", "args": {"object": match.group(1).strip(), "action": match.group(2).strip()}}
            )
    return None
