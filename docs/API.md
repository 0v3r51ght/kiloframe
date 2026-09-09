# KiloFrame RPC API

KiloFrame exposes a newline-delimited JSON protocol on the group-restricted Unix socket
`/run/kiloframe/kiloframe.sock`. The TUI, CLI, and Telegram bridge all use this daemon;
clients should read the returned state instead of maintaining a second model or route
state locally.

## Python client

```python
from pathlib import Path
from kiloframe.rpc import RPCClient

client = RPCClient(Path("/run/kiloframe/kiloframe.sock"))
status = await client.request("status")
```

`request()` waits for the first `result` event and raises `KiloFrameError` for a daemon
error. `stream()` yields every JSON event until the connection closes. Request fields are
the command name plus command-specific keyword arguments.

## Status and diagnostics

```python
status = await client.request("status")
healthy = status["healthy"]
model = status.get("model")          # selected Ollama model, or None
server = status.get("server")        # active Ollama URL, or None
processes = status.get("processes", [])

await client.request("doctor")
await client.request("resources")
await client.request("mcp_status")
```

Status is live runtime data. Ollama health, endpoint, selected model, downloaded and
running models, memory counts, MCP state, host resources, and background processes may
change between requests. A missing model or offline endpoint is reported explicitly.

## Chat stream

```python
async for event in client.stream("chat", text="Hello", cwd="/home/user"):
    kind = event.get("type")
    if kind == "token":
        print(event.get("text", ""), end="", flush=True)
    elif kind == "tool_start":
        print(f"\n[Tool: {event.get('name')}]")
    elif kind == "tool_end":
        print(" [complete]")
    elif kind in {"thinking", "warming", "runtime_status"}:
        print(f"\n[{kind}]")
    elif kind == "done":
        print("\n[Done]")
```

Chat events include `session`, `agent`, `capabilities`, `model`, `token`, `thinking`,
`warming`, `runtime_status`, `compaction`, `response_reset`, `tool_start`, `tool_end`,
`permission`, and `done`. A client must render `response_reset` by clearing the active
response buffer; it marks a new answer after a tool call or recovery retry. A
`permission` event requires a matching `permission_response` request on the same socket.

## Ollama and provider commands

```python
await client.request("ollama_status")
await client.request("ollama_servers")
models = await client.request("ollama_models")
running = await client.request("ollama_running")
await client.request("ollama_select_model", model="<downloaded-model>")
await client.request("ollama_load", model="<model>")
await client.request("ollama_unload", model="<model>")
await client.request("ollama_set_options", name="local", options={"context_tokens": 4096})

async for event in client.stream("ollama_pull", model="<model>"):
    print(event.get("status", ""))

await client.request("provider_models", name="<provider>", only_free=False)
await client.request("set_model", name="<provider>", model="<model>")
```

`ollama_select_model` only selects a model the active server reports as downloaded;
selection does not load it. Load and unload are Ollama-route operations and must never be
used as cloud controls. Server configuration commands are `ollama_add_server`,
`ollama_remove_server`, and `ollama_set_default`.

## Errors and compatibility

```python
from kiloframe.errors import KiloFrameError

try:
    await client.request("chat", text="hello")
except KiloFrameError as exc:
    print(f"KiloFrame error: {exc}")
```

Unknown commands and malformed requests return an error event. Keep clients tolerant of
additional event fields and event types so live UI improvements remain backward
compatible. The CLI command reference in [docs/COMMANDS.md](COMMANDS.md) is the user-facing
source for supported workflows.
