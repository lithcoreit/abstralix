import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from abstralix.config import ConfigManager
from abstralix.core.dag import DAGResolver
from abstralix.core.ir import IRBuilder, IRDocument
from abstralix.core.lexer import Lexer
from abstralix.core.parser import Parser
from abstralix.core.runtime import RuntimeEngine
from abstralix.core.sandbox import SandboxManager
from abstralix.plugins.registry import PluginRegistry

app = FastAPI(title="Abstralix 5.0 Daemon API", version="5.0.0")

active_websockets: List[WebSocket] = []
current_ir: Optional[IRDocument] = None
build_task: Optional[asyncio.Task] = None


class BuildRequest(BaseModel):
    entrypoint: str
    output_dir: str = "./build"
    clean: bool = False
    dev_mode: bool = True


def broadcast_event(event_name: str, data: Dict[str, Any]) -> None:
    payload = {"event": event_name, "data": data}
    for ws in list(active_websockets):
        asyncio.create_task(ws.send_json(payload))


@app.get("/api/v1/plugins")
async def list_plugins() -> Dict[str, Any]:
    reg = PluginRegistry()
    return reg.run_healthcheck()


@app.get("/api/v1/ir")
async def get_ir() -> Dict[str, Any]:
    sandbox = SandboxManager()
    if current_ir:
        return current_ir.model_dump()
    if sandbox.ir_path.exists():
        return IRDocument.load(sandbox.ir_path).model_dump()
    return {"status": "empty", "nodes": {}}


@app.post("/api/v1/build/start")
async def start_build(req: BuildRequest) -> Dict[str, Any]:
    global current_ir, build_task

    if build_task and not build_task.done():
        return {"status": "error", "message": "A build is already running"}

    abx_path = Path(req.entrypoint)
    if not abx_path.exists():
        return {"status": "error", "message": f"File not found: {req.entrypoint}"}

    config = ConfigManager()
    registry = PluginRegistry()
    sandbox = SandboxManager()
    sandbox.initialize(clean=req.clean)

    tokens = Lexer(abx_path.read_text(encoding="utf-8"), str(abx_path)).tokenize()
    ast = Parser(tokens, str(abx_path)).parse()
    ir = IRBuilder(config.defaults).build(ast)
    DAGResolver(ir, config.providers).resolve_all()
    current_ir = ir

    engine = RuntimeEngine(
        ir=ir,
        config=config,
        registry=registry,
        sandbox=sandbox,
        dev_mode=req.dev_mode,
        event_callback=broadcast_event,
    )

    async def _runner():
        await engine.run()
        sandbox.export_final_build(Path(req.output_dir), ir)
        broadcast_event("BUILD_FINISHED", {"output_dir": req.output_dir})

    build_task = asyncio.create_task(_runner())
    return {"status": "started", "total_nodes": len(ir.nodes)}


@app.post("/api/v1/build/stop")
async def stop_build() -> Dict[str, Any]:
    global build_task
    if build_task and not build_task.done():
        build_task.cancel()
        return {"status": "stopped"}
    return {"status": "idle"}


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)