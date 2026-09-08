# Architecture

KiloFrame separates terminal presentation from long-running execution.

```text
TUI / CLI / optional Telegram
             │
      group-restricted Unix RPC socket
             │
       KiloFrame daemon
       ├── agent and profiles
       ├── built-in tools + policy
       ├── MCP integrations
       ├── SQLite memory/audit
       ├── Ollama runtime client
       └── explicit cloud-provider client
```

## Client layer

`kiloframe` launches the full `prompt_toolkit` UI when attached to a suitable terminal.
Without one, or with `KILOFRAME_SIMPLE_TUI=1`, it uses the streaming line UI. Both consume
the same RPC event stream and therefore receive real model, thinking, tool, result,
recovery, compaction, token, and error events.

The full TUI owns only presentation and interactive state such as the selected cloud
route, current effort, forced profile, command menus, and sidebar visibility. Daemon/model
health comes from RPC and Ollama, not optimistic UI defaults.

## Daemon and RPC

The daemon listens on `/run/kiloframe/kiloframe.sock`. It initializes memory, Ollama
configuration, provider registry, tools, and enabled MCP servers. Front ends can request
status, resources, sessions, model lifecycle operations, configuration changes, and a
streamed chat.

The Unix socket is restricted to the KiloFrame service group. One daemon supports multiple
client launches without starting duplicate local model processes because Ollama owns the
model runtime separately.

## Agent loop

For each prompt the agent:

1. creates or resumes a session;
2. selects or honors an agent profile;
3. adds relevant facts and skills;
4. retains recent history and compacts older history to budget;
5. announces the actual local or explicitly selected cloud model;
6. streams a model request with allowed tool schemas;
7. validates, authorizes, executes, audits, and compacts tool results;
8. continues until an answer, bounded error, cancellation, or step limit.

Repeated identical calls are rejected. Research/private profiles require successful
source search and fetch before accepting an answer. The framework ensures Kilo's normal
response is addressed to Sir without relying on a weak model to follow formatting.

## Model routes

The Ollama client queries the configured endpoint using supported HTTP APIs. Downloads,
selection, and loaded state are intentionally distinct. Optional cloud providers use an
OpenAI-compatible chat shape and are selected explicitly per route/request. KiloFrame has
no automatic cloud fallback.

## Tools, MCP, and security

Built-in tools publish JSON schemas. MCP servers are initialized over stdio and their
schema-valid tools are namespaced. All tool requests are treated as untrusted model output
and pass through argument validation, path/command policy, approval where required, output
bounds, and SQLite audit. See [Security and privacy](Security-and-Privacy).

The repository's [architecture document](https://github.com/0v3r51ght/kiloframe/blob/main/docs/ARCHITECTURE.md)
contains the module-by-module reference.
