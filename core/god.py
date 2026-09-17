"""
God Agent — maps free-form character intentions to world actions (or idle/reject).
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, Field

try:
    from .models import AgentState, ToolCall
    from .parse_tool import parse_tool_call_from_dict
    from .gateway import gateway
except ImportError:
    from models import AgentState, ToolCall
    from parse_tool import parse_tool_call_from_dict
    from gateway import gateway


@dataclass
class GodDecision:
    kind: str  # "action" | "idle" | "reject"
    tool: Optional[ToolCall] = None
    reason: str = ""
    raw_response: str = ""


class GodDecisionOutput(BaseModel):
    kind: Literal["action", "idle", "reject"] = Field(
        ..., description="The type of decision: 'action', 'idle', or 'reject'"
    )
    tool: Optional[ToolCall] = Field(
        None, description="The tool call to execute, required if kind is 'action'"
    )
    reason: str = Field(..., description="Brief reason for the decision")


class GodAgent:
    """World engine that translates natural language into executable actions."""

    SYSTEM = """You are the world engine for a multi-agent simulation.

A character has described what they want to do in natural language.
Your job is to decide how that maps onto the physical world.

You may choose EXACTLY ONE of these outcomes:

1) action — emit exactly one tool call, using ONLY people/places/objects listed in the observation.
   Available tools (exact formats):
   - tool: "walk", args: {"destination": "LocationName"}
   - tool: "chat", args: {"target": "PersonName", "message": "opening line to say"}
   - tool: "interact", args: {"object": "ObjectName", "action": "what they do with it"}

2) idle — the character is only thinking, resting, or staying put with no world change.

3) reject — the intention is impossible, hallucinated, contradictory, or cannot be mapped safely
   (e.g. unknown place/person, walking to a non-adjacent place, chatting with someone not present).

Rules:
- Prefer 'action' when there is a clear, valid world effect.
- Prefer 'idle' for pure internal thought / waiting with no world effect.
- Prefer 'reject' for invalid or hallucinated targets — do not invent places, people, or objects.
- For chat, set message to a natural opening line the character would say."""

    def __init__(self, llm=None):
        # llm parameter is ignored in favor of the singleton gateway
        pass

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

Decide: 'action', 'idle', or 'reject'."""

        try:
            output = await gateway.generate_structured(
                system_prompt=self.SYSTEM,
                user_prompt=user,
                response_model=GodDecisionOutput,
                temperature=0.2,
            )
        except Exception as e:
            return GodDecision(
                kind="reject",
                reason=f"God agent LLM error: {e}",
                raw_response="",
            )

        if not output:
             return GodDecision(
                kind="reject",
                reason="God agent failed to produce valid structured output",
                raw_response="",
            )

        # Build raw string representation
        raw_resp = output.model_dump_json() if hasattr(output, 'model_dump_json') else output.json()

        parsed_tool = None
        if output.kind == "action" and output.tool:
            # We enforce Pydantic dict representation
            tool_dict = output.tool.model_dump() if hasattr(output.tool, 'model_dump') else output.tool.dict()
            parsed_tool = parse_tool_call_from_dict(tool_dict)
            if not parsed_tool:
                return GodDecision(
                    kind="reject",
                    reason="Invalid tool call structure",
                    raw_response=raw_resp,
                )

        return GodDecision(
            kind=output.kind,
            tool=parsed_tool,
            reason=output.reason,
            raw_response=raw_resp,
        )
