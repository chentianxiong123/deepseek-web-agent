"""MCP Server 模块 — 将 DeepSeek Web 对话包装为 MCP tool。

模式参考 pplx-proxy/server.py 的 MCP 部分，但适配 fastmcp>=3.0 的新 API：
  - FastMCP('name') 创建实例
  - mcp.http_app(transport='streamable-http') 获取 HTTP 应用
  - mcp.http_app(transport='sse') 获取 SSE 应用
  - mcp.lifespan 是 lifespan 上下文管理器
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

log = logging.getLogger("deepseek-web-agent.mcp")

# ─── FastMCP 懒加载 ────────────────────────────────────────────────────────

_mcp_instance = None


def get_mcp_app():
    """获取或创建 MCP 应用（含 http_app / sse_app / api_key 配置）。"""
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = _build_mcp()
    return _mcp_instance


def _build_mcp():
    """构建 MCP FastMCP 实例，挂载工具，返回 http/sse 应用字典。"""
    try:
        from fastmcp import FastMCP
    except ImportError:
        log.warning("fastmcp package not installed, MCP endpoints disabled.")
        return None

    import config
    cfg = config.load_config()
    public_url = cfg.get("public_url", "http://127.0.0.1:48391")
    api_key = cfg.get("api_key", "")

    # ── 传输安全设置（参考 pplx-proxy 模式）─────────────────────────
    _pub_host = urlparse(public_url).hostname or ""
    _allowed_hosts = ["127.0.0.1", "localhost", "[::1]"]
    _allowed_origins = [
        "http://127.0.0.1:48391",
        "http://localhost:48391",
        f"http://{_pub_host}" if _pub_host else None,
        f"https://{_pub_host}" if _pub_host else None,
    ]
    _allowed_hosts = [h for h in _allowed_hosts + ([_pub_host] if _pub_host else []) if h]
    _allowed_origins = [o for o in _allowed_origins if o]

    mcp = FastMCP(
        "deepseek-web-agent",
        instructions="DeepSeek 网页端对话代理，支持多模型、思考模式和搜索。",
    )

    # ── 工具：ask_deepseek ─────────────────────────────────────────────

    @mcp.tool()
    async def ask_deepseek(
        query: str,
        model: str = "deepseek-v4-flash",
        thinking: bool = True,
        search: bool = False,
    ) -> str:
        """调用 DeepSeek 网页端对话，返回最终文本答案。

        Args:
            query: 用户输入的问题/提示词
            model: 模型，支持 deepseek-v4-flash / deepseek-v4-pro
            thinking: 是否启用思考过程（reasoning）
            search: 是否启用搜索
        Returns:
            DeepSeek 返回的最终文本答案
        """
        if not query or not query.strip():
            return "Error: query cannot be empty"
        from mcp_pipeline import mcp_ask_deepseek
        return await mcp_ask_deepseek(
            query,
            model=model,
            thinking=thinking,
            search=search,
        )

    # ── 工具：deepseek_models ───────────────────────────────────────────

    @mcp.tool()
    async def deepseek_models() -> str:
        """列出 DeepSeek 可用模型、当前 backend 及认证状态。"""
        from mcp_pipeline import mcp_deepseek_models
        return await mcp_deepseek_models()

    # ── 工具：deepseek_status ───────────────────────────────────────────

    @mcp.tool()
    async def deepseek_status() -> str:
        """检查 DeepSeek 代理当前状态（登录、会话、model）。"""
        from mcp_pipeline import mcp_deepseek_status
        return await mcp_deepseek_status()

    # ── 构建 Streamable HTTP + SSE 应用 ─────────────────────────────────

    # 获取 lifespan 上下文管理器（用于合并到 FastAPI）
    _mcp_lifespan = mcp.lifespan

    # 获取 HTTP 应用（Streamable HTTP）
    mcp_http_app = mcp.http_app(
        transport="streamable-http",
        allowed_hosts=_allowed_hosts if _allowed_hosts else None,
        allowed_origins=_allowed_origins if _allowed_origins else None,
    )

    # 获取 SSE 应用
    mcp_sse_app = mcp.http_app(
        transport="sse",
        allowed_hosts=_allowed_hosts if _allowed_hosts else None,
        allowed_origins=_allowed_origins if _allowed_origins else None,
    )

    return {
        "mcp": mcp,
        "http_lifespan": mcp_http_app.router.lifespan_context,
        "sse_lifespan": mcp_sse_app.router.lifespan_context,
        "http_app": mcp_http_app,
        "sse_app": mcp_sse_app,
        "has_auth": bool(api_key),
        "api_key": api_key,
    }
