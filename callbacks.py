import asyncio
import socket
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Literal

import uvicorn
from mcp.server import MCPServer
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


class CallbackResult(BaseModel):
    outcome: Literal["success", "error", "cancel"]
    parameters: dict[str, str]


@dataclass
class CallbackState:
    base_url: str
    pending: dict[str, asyncio.Future[CallbackResult]] = field(default_factory=dict)


def create_callback_app(state: CallbackState) -> Starlette:
    async def receive(request: Request) -> PlainTextResponse:
        if request.method != "GET":
            return PlainTextResponse("Use GET for callbacks.", status_code=405)
        outcome = request.path_params["outcome"]
        if outcome not in {"success", "error", "cancel"}:
            return PlainTextResponse("Unknown callback outcome.", status_code=404)
        future = state.pending.get(request.path_params["request_id"])
        if future is None or future.done():
            return PlainTextResponse("This request is no longer waiting.", status_code=410)
        future.set_result(
            CallbackResult(outcome=outcome, parameters=dict(request.query_params))
        )
        return PlainTextResponse(
            "Result received. You can close this tab.",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    return Starlette(
        routes=[
            Route("/callbacks/{request_id}/{outcome}", receive, methods=["GET"])
        ]
    )


class CallbackServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # The MCP process owns shutdown signals; this listener must not intercept them.
        yield


@asynccontextmanager
async def callback_lifespan(_server: MCPServer) -> AsyncIterator[CallbackState]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        state = CallbackState(base_url=f"http://127.0.0.1:{port}")
        server = CallbackServer(
            uvicorn.Config(
                create_callback_app(state),
                log_level="warning",
                access_log=False,
                lifespan="off",
                timeout_graceful_shutdown=1,
            )
        )
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:
                if server_task.done():
                    await server_task
                    raise RuntimeError("The Things callback listener did not start.")
                await asyncio.sleep(0.01)
            yield state
        finally:
            for future in state.pending.values():
                future.cancel()
            state.pending.clear()
            server.should_exit = True
            await server_task
