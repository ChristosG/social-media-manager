import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from app.graph.state import ChatState
from app.graph.context import build_system_prompt
from app.llm.client import build_chat_model
from app.agent.tools import ALL_TOOLS
from app.repo import memory as mem_repo, ledger as ledger_repo, profile as profile_repo
from app.repo import capabilities as cap_repo
from app.repo import prompts as prompts_repo


def _needs_tool_repair(msg) -> bool:
    """True when the model emitted ONLY unparseable tool calls (no valid call, no content) — it tried to
    act but the 9B mangled the args, so without a nudge the turn ends silently."""
    if getattr(msg, "tool_calls", None):
        return False
    if (getattr(msg, "content", "") or "").strip():
        return False
    return bool(getattr(msg, "invalid_tool_calls", None))


def build_graph(model=None, load_memory: bool = True, tools=ALL_TOOLS, checkpointer=None, thinking_model=None):
    base = model or build_chat_model()

    def _bind(m):
        try:
            return m.bind_tools(tools) if tools else m
        except NotImplementedError:
            # Fake/test models that don't support bind_tools: use as-is.
            # tools_condition will route to END (no tool_calls on their output).
            return m

    bound = _bind(base)
    # THINK ONCE: when a thinking model is supplied, it's used ONLY on the first agent step (the planning
    # step, where deliberation actually changes the outcome — understanding a nuanced correction, choosing
    # the right plan). Every later step (narrating a result, calling the next obvious tool) runs on the
    # fast thinking-OFF model, which is itself reliable at structured tool calls. This cuts a multi-tool
    # turn from N+1 thinking passes to exactly 1, without giving up the deliberate planning pass.
    thinking_bound = _bind(thinking_model) if thinking_model is not None else None

    async def load_context(state: ChatState):
        if not load_memory or not state.get("org_id"):
            return {"system_prompt": ""}
        org = state["org_id"]
        entries, profile, programs, posts, caps, overrides = await asyncio.gather(
            mem_repo.list_entries(org),
            profile_repo.get_profile(org),
            profile_repo.list_programs(org),
            ledger_repo.list_posts(org),
            cap_repo.list_effective(org),
            prompts_repo.get_overrides(org),
        )
        recent = [p["title"] for p in posts][:10]
        content_types = [c for c in caps if c["kind"] == "content_type"]
        skill_prompts = [c for c in caps if c["kind"] == "skill_prompt"]
        return {"system_prompt": build_system_prompt(entries, profile, recent, content_types, skill_prompts,
                                                     persona=overrides.get("system_persona"), agent_mode=True,
                                                     programs=programs)}

    async def agent(state: ChatState):
        msgs = list(state["messages"])
        sp = state.get("system_prompt")
        if sp:
            msgs = [SystemMessage(content=sp)] + msgs
        # First agent step this turn = no tool has run yet (the input history carries no ToolMessages —
        # they're stripped to text when persisted, and the per-turn checkpoint thread starts fresh). Think
        # there; fall back to the fast model on every later step.
        first_step = not any(isinstance(m, ToolMessage) for m in state["messages"])
        chosen = thinking_bound if (thinking_bound is not None and first_step) else bound
        return {"messages": [await chosen.ainvoke(msgs)]}

    async def repair(state: ChatState):
        """Inject a corrective nudge when the model emitted only unparseable tool calls.
        Increments repair_count to cap the repair loop at one attempt."""
        nudge = HumanMessage(content=("Your previous tool call had malformed arguments. Re-issue it with "
                                      "valid JSON arguments, or answer in plain text."))
        return {"messages": [nudge], "repair_count": state.get("repair_count", 0) + 1}

    def route_after_agent(state: ChatState):
        """Routing function that replaces the bare tools_condition.

        - Valid tool calls → "tools"  (same as before)
        - Only invalid/unparseable tool calls, first occurrence → "repair"
        - Everything else (plain answer, empty, second malformed call) → END
        """
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        if _needs_tool_repair(last) and state.get("repair_count", 0) < 1:
            return "repair"
        return END

    g = StateGraph(ChatState)
    g.add_node("load_context", load_context)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_node("repair", repair)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "repair": "repair", END: END})
    g.add_edge("tools", "agent")
    g.add_edge("repair", "agent")
    # A checkpointer is required for human-in-the-loop interrupt()/resume (the publish gate). When None
    # (tests, the eval harness) the graph stays stateless exactly as before.
    return g.compile(checkpointer=checkpointer)
