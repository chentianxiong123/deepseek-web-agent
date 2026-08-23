"""MCP 专属编排管线 — 独立、干净。

就做一件事：query → backend.chat_turn() → 纯文本。
不搞审批、拦截、buffer、system_prompt 注入等花里胡哨的东西。
"""

from __future__ import annotations

import accounts
from backends.registry import get_backend


async def mcp_ask_deepseek(
    query: str,
    *,
    model: str = "deepseek-v4-flash",
    thinking: bool = True,
    search: bool = False,
) -> str:
    """MCP 工具：向 DeepSeek 网页端发一条对话请求，返回纯文本结果。

    独立管线，不经过 agent 适配、rules 过滤、审批等。
    """
    backend = get_backend()
    account_config = accounts.get_active_account() or {}

    if not account_config.get("token"):
        return "Error: No active account. Please login at /admin first."

    answer_parts: list[str] = []
    error_occurred = False
    error_msg = ""

    try:
        async for ev in backend.chat_turn(
            query,
            model=model,
            account_config=account_config,
            thinking_enabled=thinking,
            search_enabled=search,
            system_prompt="",
        ):
            if ev.type == "content" and isinstance(ev.val, str) and ev.val:
                answer_parts.append(ev.val)
            elif ev.type == "error":
                error_occurred = True
                error_msg = str(ev.val)
                break
    except Exception as e:
        error_occurred = True
        error_msg = str(e)

    if error_occurred:
        return f"Error: {error_msg}"

    return "".join(answer_parts) if answer_parts else "(no response)"


async def mcp_deepseek_models() -> str:
    """MCP 工具：列出可用模型、当前 backend 及认证状态。"""
    backend = get_backend()
    account_config = accounts.get_active_account() or {}
    active_model = backend.active_model()
    return (
        "Available models:\n"
        "  - deepseek-v4-flash  (default, fast)\n"
        "  - deepseek-v4-pro    (expert, higher quality)\n\n"
        f"Current backend: {backend.id} ({backend.display_name})\n"
        f"Active model: {active_model}\n"
        f"Authenticated: {backend.is_authenticated()}"
    )


async def mcp_deepseek_status() -> str:
    """MCP 工具：检查代理当前状态。"""
    backend = get_backend()
    account_config = accounts.get_active_account() or {}
    has_session = bool(account_config.get("session_id"))
    return (
        f"Status: ok\n"
        f"Authenticated: {backend.is_authenticated()}\n"
        f"Session active: {has_session}\n"
        f"Backend: {backend.id} ({backend.display_name})\n"
        f"Active model: {account_config.get('model', 'deepseek-v4-flash')}"
    )