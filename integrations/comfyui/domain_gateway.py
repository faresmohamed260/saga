from __future__ import annotations

import asyncio
import html
import json
import time
from pathlib import Path
from typing import Any

import httpx
import websockets
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

try:
    from integrations.comfyui.token_pool import (
        DEFAULT_STATE_PATH,
        DEFAULT_WARM_TTL_SECONDS,
        load_start_index,
        load_tokens,
        mark_render_success,
        rotate_prefer_warm,
        save_next_index,
        update_token_stat,
    )
    from integrations.comfyui.workspace_client import ModalUrls, app_list, ensure_urls, health_check, month_cost_usd
except ImportError:  # pragma: no cover
    from token_pool import (
        DEFAULT_STATE_PATH,
        DEFAULT_WARM_TTL_SECONDS,
        load_start_index,
        load_tokens,
        mark_render_success,
        rotate_prefer_warm,
        save_next_index,
        update_token_stat,
    )
    from workspace_client import ModalUrls, app_list, ensure_urls, health_check, month_cost_usd


MODULE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MODULE_DIR / "gateway_config.json"
STATE_PATH = DEFAULT_STATE_PATH
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

app = FastAPI(title="Modal ComfyUI Gateway")
_LOCK = asyncio.Lock()
BACKEND_COOKIE = "comfyui_backend"


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _set_active_backend(token_name: str, urls: ModalUrls) -> None:
    state = _load_state()
    state["active_token"] = token_name
    state["active_ui_url"] = urls.ui_url
    state["active_api_url"] = urls.api_url
    state["last_switched_at"] = int(time.time())
    token_stats = state.setdefault("token_stats", {})
    stats = token_stats.setdefault(token_name, {})
    stats["ui_url"] = urls.ui_url
    stats["api_url"] = urls.api_url
    stats["last_deployed_at"] = int(time.time())
    _save_state(state)


def _get_active_backend() -> tuple[str | None, str | None]:
    state = _load_state()
    return state.get("active_token"), state.get("active_ui_url")


def _get_selected_backend(request: Request) -> str | None:
    backend = (request.cookies.get(BACKEND_COOKIE) or "").strip().lower()
    return backend if backend in {"local", "cloud"} else None


def _default_backend() -> str | None:
    backend = str(CONFIG.get("default_backend") or "").strip().lower()
    return backend if backend in {"local", "cloud"} else None


def _effective_backend(request: Request) -> str | None:
    return _get_selected_backend(request) or _default_backend()


def _render_home_page(selected: str | None, active_token: str | None, active_ui_url: str | None) -> str:
    selected_label = selected or "not selected"
    return (
        "<html><head><title>Choose ComfyUI</title><style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f6efe4;color:#1f2937;}"
        ".wrap{max-width:860px;margin:0 auto;}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;}"
        ".card{background:#fff;border:1px solid #d6d3d1;border-radius:16px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.06);}"
        "a.button,button{display:inline-block;background:#111827;color:#fff;text-decoration:none;padding:10px 14px;border-radius:10px;border:none;cursor:pointer;}"
        "a.alt{background:#0f766e;} .muted{color:#6b7280;} ul{padding-left:18px;}"
        "</style></head><body><div class='wrap'>"
        "<h1>ComfyUI Gateway</h1>"
        f"<p class='muted'>Current selection: <strong>{html.escape(selected_label)}</strong></p>"
        "<div class='cards'>"
        "<div class='card'>"
        "<h2>Local Docker</h2>"
        "<p>Use the ComfyUI already running on this PC.</p>"
        "<form method='post' action='/select/local'><button type='submit'>Use Local</button></form>"
        "</div>"
        "<div class='card'>"
        "<h2>Modal Cloud</h2>"
        "<p>Use the rotating Modal-backed ComfyUI workspace with token-aware failover.</p>"
        f"<p class='muted'>Active cloud token: <strong>{html.escape(active_token or 'not resolved yet')}</strong></p>"
        f"<p class='muted'>Current Modal UI: <a href='{html.escape(active_ui_url or '#')}'>{html.escape(active_ui_url or 'not resolved yet')}</a></p>"
        "<form method='post' action='/select/cloud'><button class='alt' type='submit'>Use Cloud</button></form>"
        "</div>"
        "</div>"
        "<div class='card' style='margin-top:18px'>"
        "<h2>Shortcuts</h2>"
        "<ul>"
        "<li><a href='/app'>Open selected backend</a></li>"
        "<li><a href='/select/local'>Switch to local</a></li>"
        "<li><a href='/select/cloud'>Switch to cloud</a></li>"
        "<li><a href='/status'>Open status dashboard</a></li>"
        "</ul>"
        "</div></div></body></html>"
    )


def _render_cloud_home_page(active_token: str | None, active_ui_url: str | None) -> str:
    public_hostname = str(CONFIG.get("public_hostname") or "")
    local_public_hostname = str(CONFIG.get("local_public_hostname") or "")
    return (
        "<html><head><title>Cloud ComfyUI</title><style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f7f4ec;color:#1f2937;}"
        ".wrap{max-width:860px;margin:0 auto;}.card{background:#fff;border:1px solid #d6d3d1;border-radius:16px;padding:22px;box-shadow:0 10px 30px rgba(0,0,0,.06);}"
        "a.button{display:inline-block;background:#0f766e;color:#fff;text-decoration:none;padding:10px 14px;border-radius:10px;}"
        ".muted{color:#6b7280;} code{background:#f3f4f6;padding:2px 6px;border-radius:6px;}"
        "</style></head><body><div class='wrap'><div class='card'>"
        "<h1>Cloud ComfyUI</h1>"
        "<p>This hostname is dedicated to the Modal-backed ComfyUI workspace.</p>"
        f"<p class='muted'>Active token: <strong>{html.escape(active_token or 'not resolved yet')}</strong></p>"
        f"<p class='muted'>Current Modal UI: <a href='{html.escape(active_ui_url or '#')}'>{html.escape(active_ui_url or 'not resolved yet')}</a></p>"
        f"<p><a class='button' href='/app'>Open cloud ComfyUI</a></p>"
        "<p class='muted'>Status dashboard: <a href='/status'>/status</a></p>"
        f"<p class='muted'>Local Docker host: <a href='https://{html.escape(local_public_hostname)}'>https://{html.escape(local_public_hostname)}</a></p>"
        f"<p class='muted'>Cloud host: <code>{html.escape(public_hostname)}</code></p>"
        "</div></div></body></html>"
    )


async def ensure_active_backend(force_switch: bool = False) -> tuple[str, ModalUrls]:
    async with _LOCK:
        state = _load_state()
        tokens = load_tokens()
        active_name = None if force_switch else state.get("active_token")

        if active_name:
            for token in tokens:
                if token.name == active_name:
                    urls = ensure_urls(token, CONFIG["app_name"])
                    _set_active_backend(token.name, urls)
                    return token.name, urls

        start_index = load_start_index()
        for index, token in rotate_prefer_warm(tokens, start_index, state_path=STATE_PATH):
            ok, message = health_check(token)
            update_token_stat(token.name, state_path=STATE_PATH, health_ok=ok, last_error="" if ok else message)
            if not ok:
                continue
            urls = ensure_urls(token, CONFIG["app_name"])
            _set_active_backend(token.name, urls)
            mark_render_success(
                token.name,
                state_path=STATE_PATH,
                warm_ttl_seconds=int(CONFIG.get("warm_ttl_seconds", DEFAULT_WARM_TTL_SECONDS)),
            )
            save_next_index(index + 1, STATE_PATH)
            return token.name, urls

        raise RuntimeError("No healthy Modal token/workspace was available.")


def _build_status_rows(refresh: bool = False) -> list[dict[str, Any]]:
    tokens = load_tokens()
    state = _load_state()
    rows: list[dict[str, Any]] = []
    now = int(time.time())

    for token in tokens:
        stats = state.get("token_stats", {}).get(token.name, {})
        cost = stats.get("month_cost_usd")
        if refresh:
            try:
                cost = month_cost_usd(token)
                update_token_stat(token.name, state_path=STATE_PATH, health_ok=None, last_error=None)
                state = _load_state()
                state.setdefault("token_stats", {}).setdefault(token.name, {})["month_cost_usd"] = cost
                state["token_stats"][token.name]["month_cost_checked_at"] = now
                _save_state(state)
                stats = state.get("token_stats", {}).get(token.name, {})
            except Exception as exc:  # noqa: BLE001
                stats["month_cost_error"] = str(exc)

        cost_value = float(cost or 0.0)
        rows.append(
            {
                "name": token.name,
                "is_active": state.get("active_token") == token.name,
                "ui_url": stats.get("ui_url", ""),
                "last_health_ok": stats.get("last_health_ok"),
                "last_render_ok": stats.get("last_render_ok"),
                "warm_until": stats.get("warm_until", 0),
                "month_cost_usd": cost_value,
                "est_remaining_usd": max(float(CONFIG.get("monthly_credit_usd", 30.0)) - cost_value, 0.0),
                "month_cost_error": stats.get("month_cost_error", ""),
                "last_error": stats.get("last_error", ""),
            }
        )
    return rows


def _render_status_page(rows: list[dict[str, Any]]) -> str:
    active_token, active_ui_url = _get_active_backend()
    body = [
        "<html><head><title>ComfyUI Status</title><style>",
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f4ec;color:#1f2937;}",
        "table{border-collapse:collapse;width:100%;background:#fff;}th,td{border:1px solid #d1d5db;padding:8px;text-align:left;}",
        "th{background:#111827;color:#fff;}a{color:#0f766e;}button{padding:6px 10px;} .active{font-weight:700;color:#166534;}",
        "</style></head><body>",
        "<h1>ComfyUI Gateway Status</h1>",
        f"<p>Public host: <strong>{html.escape(CONFIG['public_hostname'])}</strong></p>",
        f"<p>Local UI: <a href=\"{html.escape(CONFIG['local_ui_url'])}\">{html.escape(CONFIG['local_ui_url'])}</a></p>",
        f"<p>Active token: <strong>{html.escape(active_token or 'none')}</strong></p>",
        f"<p>Active backend: <a href=\"{html.escape(active_ui_url or '#')}\">{html.escape(active_ui_url or 'not set')}</a></p>",
        "<p><a href=\"/\">Home</a> | <a href=\"/app\">Open selected backend</a> | <a href=\"/status?refresh=1\">Refresh billing + health</a></p>",
        "<p>Usage and remaining credit values come from cached state by default so this page stays fast. Use the refresh link when you want a live billing sweep across the token pool.</p>",
        "<table><thead><tr><th>Token</th><th>Active</th><th>Warm</th><th>Month Cost ($)</th><th>Est. Remaining ($)</th><th>Health</th><th>UI URL</th><th>Last Error</th><th>Action</th></tr></thead><tbody>",
    ]
    now = int(time.time())
    for row in rows:
        warm = bool(int(row["warm_until"] or 0) > now)
        body.append(
            "<tr>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td>{'yes' if row['is_active'] else ''}</td>"
            f"<td>{'warm' if warm else ''}</td>"
            f"<td>{row['month_cost_usd']:.4f}</td>"
            f"<td>{row['est_remaining_usd']:.4f}</td>"
            f"<td>{html.escape(str(row['last_health_ok']))}</td>"
            f"<td><a href=\"{html.escape(row['ui_url'] or '#')}\">{html.escape(row['ui_url'] or '')}</a></td>"
            f"<td>{html.escape(row['last_error'] or row['month_cost_error'] or '')}</td>"
            f"<td><form method=\"post\" action=\"/admin/switch\"><input type=\"hidden\" name=\"token\" value=\"{html.escape(row['name'])}\"><button type=\"submit\">Switch</button></form></td>"
            "</tr>"
        )
    body.append("</tbody></table></body></html>")
    return "".join(body)


async def _resolve_backend(request: Request, *, force_switch: bool = False) -> tuple[str, str | ModalUrls]:
    selected = _effective_backend(request)
    if selected == "local":
        return "local", CONFIG["local_ui_url"]
    _, urls = await ensure_active_backend(force_switch=force_switch)
    return "cloud", urls


async def _proxy_http(request: Request, path: str) -> Response:
    attempts = 0
    last_exc: Exception | None = None
    while attempts < 2:
        backend_kind, target_backend = await _resolve_backend(request, force_switch=attempts > 0)
        base_url = target_backend if backend_kind == "local" else target_backend.ui_url
        target = f"{base_url.rstrip('/')}/{path}" if path else base_url
        if request.url.query:
            target = f"{target}?{request.url.query}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
        body = await request.body()
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=300) as client:
                upstream = await client.request(request.method, target, headers=headers, content=body)
            if backend_kind == "cloud" and upstream.status_code >= 500:
                attempts += 1
                continue
            resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}}
            return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            attempts += 1
    raise HTTPException(status_code=502, detail=f"Gateway could not reach Modal backend: {last_exc}")


async def _proxy_websocket(client_ws: WebSocket, path: str) -> None:
    await client_ws.accept()
    attempts = 0
    while attempts < 2:
        backend_kind, target_backend = await _resolve_backend(client_ws, force_switch=attempts > 0)  # type: ignore[arg-type]
        base_url = target_backend if backend_kind == "local" else target_backend.ui_url
        base = base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
        target = f"{base}/{path}" if path else base
        if client_ws.url.query:
            target = f"{target}?{client_ws.url.query}"
        try:
            async with websockets.connect(target, open_timeout=60) as upstream:
                async def from_client() -> None:
                    while True:
                        message = await client_ws.receive()
                        if message["type"] == "websocket.disconnect":
                            await upstream.close()
                            return
                        if message.get("text") is not None:
                            await upstream.send(message["text"])
                        elif message.get("bytes") is not None:
                            await upstream.send(message["bytes"])

                async def from_upstream() -> None:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await client_ws.send_bytes(message)
                        else:
                            await client_ws.send_text(message)

                await asyncio.gather(from_client(), from_upstream())
                return
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001
            attempts += 1
            continue
    await client_ws.close(code=1011)


@app.get("/", include_in_schema=False)
async def root(request: Request, choose: int = 0) -> Response:
    default_backend = _default_backend()
    selected = _get_selected_backend(request)
    if default_backend == "cloud" and not choose:
        active_token, active_ui_url = _get_active_backend()
        return HTMLResponse(_render_cloud_home_page(active_token, active_ui_url))
    if choose or not selected:
        active_token, active_ui_url = _get_active_backend()
        return HTMLResponse(_render_home_page(selected, active_token, active_ui_url))
    return RedirectResponse(url="/app", status_code=307)


@app.get("/app", include_in_schema=False)
async def app_entry(request: Request) -> Response:
    if not _effective_backend(request):
        return RedirectResponse(url="/?choose=1", status_code=307)
    return await _proxy_http(request, "")


@app.post("/select/local")
@app.get("/select/local")
async def select_local() -> RedirectResponse:
    response = RedirectResponse(url="/app", status_code=303)
    response.set_cookie(BACKEND_COOKIE, "local", max_age=60 * 60 * 24 * 30, httponly=False, samesite="lax")
    return response


@app.post("/select/cloud")
@app.get("/select/cloud")
async def select_cloud() -> RedirectResponse:
    response = RedirectResponse(url="/app", status_code=303)
    response.set_cookie(BACKEND_COOKIE, "cloud", max_age=60 * 60 * 24 * 30, httponly=False, samesite="lax")
    return response


@app.get("/status", response_class=HTMLResponse)
async def status_page(refresh: int = 0) -> HTMLResponse:
    rows = _build_status_rows(refresh=bool(refresh))
    return HTMLResponse(_render_status_page(rows))


@app.get("/status.json")
async def status_json(refresh: int = 0) -> JSONResponse:
    rows = _build_status_rows(refresh=bool(refresh))
    return JSONResponse({"rows": rows, "active": _get_active_backend()[0]})


@app.post("/admin/switch")
async def admin_switch(request: Request) -> RedirectResponse:
    form = await request.form()
    target_name = str(form.get("token") or "").strip()
    tokens = {token.name: token for token in load_tokens()}
    token = tokens.get(target_name)
    if not token:
        raise HTTPException(status_code=404, detail="Unknown token")
    urls = ensure_urls(token, CONFIG["app_name"])
    _set_active_backend(token.name, urls)
    mark_render_success(
        token.name,
        state_path=STATE_PATH,
        warm_ttl_seconds=int(CONFIG.get("warm_ttl_seconds", DEFAULT_WARM_TTL_SECONDS)),
    )
    return RedirectResponse(url="/status", status_code=303)


@app.websocket("/ws")
async def websocket_root(ws: WebSocket) -> None:
    await _proxy_websocket(ws, "ws")


@app.websocket("/{path:path}")
async def websocket_all(ws: WebSocket, path: str) -> None:
    if path.startswith("status") or path.startswith("admin"):
        await ws.close(code=1008)
        return
    await _proxy_websocket(ws, path)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_all(request: Request, path: str) -> Response:
    if path.startswith("status") or path.startswith("admin") or path.startswith("select"):
        raise HTTPException(status_code=404, detail="Not found")
    if not _effective_backend(request):
        return RedirectResponse(url="/?choose=1", status_code=307)
    return await _proxy_http(request, path)
