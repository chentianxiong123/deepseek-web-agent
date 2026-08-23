from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

import config
import session as sess

router = APIRouter(tags=["admin"])


@router.get("/admin")
async def admin():
    cfg = config.load_config()
    usage = sess.get_usage_status() if cfg.get("session_id") else {}
    from admin_page import render_overview
    return HTMLResponse(render_overview(cfg, usage))


@router.get("/admin/accounts")
async def admin_accounts():
    from admin_page import render_accounts
    return HTMLResponse(render_accounts())


@router.get("/admin/sessions")
async def admin_sessions():
    from admin_page import render_sessions
    return HTMLResponse(render_sessions())


@router.get("/admin/rules")
async def admin_rules():
    from admin_page import render_rules
    return HTMLResponse(render_rules())


@router.get("/admin/parser-flow")
async def admin_parser_flow():
    from admin_page import render_parser_flow
    return HTMLResponse(render_parser_flow())


@router.get("/admin/debug")
async def admin_debug():
    from admin_page import render_debug
    return HTMLResponse(render_debug())


@router.get("/admin/prompts")
async def admin_prompts():
    from admin_page import render_prompts
    return HTMLResponse(render_prompts())


@router.get("/admin/mcp")
async def admin_mcp():
    from admin_page import render_mcp
    return HTMLResponse(await render_mcp())


@router.post("/api/mcp/call")
async def api_mcp_call(request: Request):
    """调用 MCP 工具（供管理页面测试用）"""
    from mcp_server import get_mcp_app
    import asyncio
    body = await request.json()
    tool_name = body.get("name", "")
    arguments = body.get("arguments", {})

    if not tool_name:
        return JSONResponse({"ok": False, "error": "name is required"})

    mcp = get_mcp_app()
    if not mcp:
        return JSONResponse({"ok": False, "error": "MCP not available (fastmcp not installed)"})

    try:
        tool = await mcp["mcp"].get_tool(tool_name)
        if not tool:
            return JSONResponse({"ok": False, "error": f"Tool '{tool_name}' not found"})
        result = await mcp["mcp"].call_tool(tool_name, arguments)
        # FastMCP call_tool 返回 ToolResult，取 text
        text = ""
        if hasattr(result, "content"):
            for block in result.content:
                if hasattr(block, "text"):
                    text += block.text
                elif isinstance(block, dict) and "text" in block:
                    text += block["text"]
        else:
            text = str(result) if result else ""
        return JSONResponse({"ok": True, "result": text.strip()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/prompts")
async def api_get_prompts():
    from prompts import manager
    return JSONResponse(content=manager.get_all_prompts())


@router.put("/api/prompts/{name}")
async def api_set_prompt(name: str, request: Request):
    from prompts import manager
    body = await request.json()
    content = body.get("content", "")
    manager.set_prompt(name, content)
    return JSONResponse(content={"ok": True, "name": name})
