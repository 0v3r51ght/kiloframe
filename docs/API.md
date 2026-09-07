# KiloFrame RPC API

## Connection

Connect to the daemon via Unix socket:

```python
from kiloframe.rpc import RPCClient
from pathlib import Path

client = RPCClient(Path("/run/kiloframe/kiloframe.sock"))
```

## Status Request

```python
status = await client.request("status")
# Returns:
# {
#   "running": true,
#   "healthy": true,
#   "pid": 1234,
#   "uptime_seconds": 3600,
#   "model": "llama3.2",
#   "server": "http://127.0.0.1:11434",
#   "memory": {"sessions": 5, "facts": 42, "skills": 8}
# }
```

## Chat Stream

```python
async for event in client.stream("chat", text="Hello", cwd="/home/user"):
    if event["type"] == "token":
        print(event["text"], end="")
    elif event["type"] == "tool":
        print(f"\n[Tool: {event['name']}]")
    elif event["type"] == "done":
        print("\n[Done]")
```

## Ollama Commands

```python
# Server status
await client.request("ollama_status")

# List models
await client.request("ollama_models")

# List running models
await client.request("ollama_running")

# Pull model
async for event in client.stream("ollama_pull", model="llama3.2"):
    print(event.get("status", ""))

# Select model
await client.request("ollama_select_model", model="llama3.2")

# Unload model
await client.request("ollama_unload", model="llama3.2")

# Add server
await client.request("ollama_add_server", name="local", url="http://127.0.0.1:11434")

# Remove server
await client.request("ollama_remove_server", name="local")

# Set default
await client.request("ollama_set_default", name="local")

# List servers
await client.request("ollama_servers")
```

## Error Handling

```python
from kiloframe.errors import RPCError

try:
    result = await client.request("chat", text="hello")
except RPCError as e:
    print(f"Error: {e}")
```
