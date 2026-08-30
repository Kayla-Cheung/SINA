"""
God Agent — maps free-form character intentions to world actions (or idle/reject).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .llm import LLMClient
from .models import AgentState, ToolCall
from .parse_tool import parse_tool_call


@dataclass
class GodDecision:
    kind: str  # "action" | "idle" | "reject"
    tool: Optional[ToolCall] = None
    reason: str = ""
    raw_response: str = ""


class GodAgent:
    """World engine that translates natural language into executable actions."""

    SYSTEM = """You are the world engine for a multi-agent simulation.

A character has described what they want to do in natural language.
Your job is to decide how that maps onto the physical world.

You may choose EXACTLY ONE of these outcomes:

1) ACTION — emit exactly one tool call, using ONLY people/places/objects listed in the observation.
   Available tools (exact formats):
   - walk(destination="LocationName")
   - chat(target="PersonName", message="opening line to say")
   - interact(object="ObjectName", action="what they do with it")

2) IDLE — the character is only thinking, resting, or staying put with no world change.
   Format: IDLE: <brief reason>

3) REJECT — the intention is impossible, hallucinated, contradictory, or cannot be mapped safely
   (e.g. unknown place/person, walking to a non-adjacent place, chatting with someone not present).
   Format: REJECT: <brief reason>

Rules:
- Prefer ACTION when there is a clear, valid world effect.
- Prefer IDLE for pure internal thought / waiting with no world effect.
- Prefer REJECT for invalid or hallucinated targets — do not invent places, people, or objects.
- For chat, set message to a natural opening line the character would say.
- Output ONLY the ACTION tool call line, or an IDLE:/REJECT: line. No other commentary."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _format_observation(self, obs: Dict[str, Any], agent: AgentState) -> str:
        locs = obs.get("locations") or []
        chars = obs.get("characters") or []
        objs = obs.get("objects") or []
        loc_lines = (
            "\n".join(f"- {x['name']} (id={x['id']}, {x['distance']}m)" for x in locs)
            or "- (none)"
        )
        char_lines = (
            "\n".join(f"- {x['name']} (id={x['id']})" for x in chars) or "- (none)"
        )
        obj_lines = (
            "\n".join(f"- {x['name']} (id={x['id']})" for x in objs) or "- (none)"
        )
        return f"""Character: {agent.name} (id={agent.id})
Current location id: {agent.current_location}

Adjacent locations:
{loc_lines}

People present (same location only):
{char_lines}

Objects present:
{obj_lines}"""

    async def translate(
        self,
        intention: str,
        agent: AgentState,
        observation: Dict[str, Any],
    ) -> GodDecision:
        user = f"""{self._format_observation(observation, agent)}

Character's intention (natural language):
\"\"\"{intention.strip()}\"\"\"

Decide: ACTION tool call, IDLE:, or REJECT:"""

        try:
            raw = await self.llm.chat(
                system_prompt=self.SYSTEM,
                user_prompt=user,
                temperature=0.2,
                max_tokens=512,
            )
        except Exception as e:
            return GodDecision(
                kind="reject",
                reason=f"God agent LLM error: {e}",
                raw_response="",
            )

        return self._parse_decision(raw or "")

    def _parse_decision(self, raw: str) -> GodDecision:
        text = raw.strip()
        upper = text.upper()

        # Explicit REJECT / IDLE markers (check before tool parse)
        for prefix, kind in (("REJECT:", "reject"), ("IDLE:", "idle")):
            idx = upper.find(prefix)
            if idx != -1:
                reason = text[idx + len(prefix):].strip() or kind
                return GodDecision(
                    kind=kind,
                    reason=reason,
                    raw_response=raw,
                )

        tool = parse_tool_call(text)
        if tool and tool.tool in ("walk", "chat", "interact"):
            return GodDecision(
                kind="action",
                tool=tool,
                reason="mapped to tool",
                raw_response=raw,
            )

        # Fallback keywords
        if upper.startswith("IDLE") or "\nIDLE" in upper:
            return GodDecision(
                kind="idle",
                reason=text[:200],
                raw_response=raw,
            )
        if upper.startswith("REJECT") or "\nREJECT" in upper:
            return GodDecision(
                kind="reject",
                reason=text[:200],
                raw_response=raw,
            )

        return GodDecision(
            kind="reject",
            reason="God output could not be parsed into a valid action",
            raw_response=raw,
        )
