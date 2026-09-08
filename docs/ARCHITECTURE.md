# KiloFrame architecture

KiloFrame is a local-first terminal agent. A full-screen TUI, line-oriented CLI, and
optional Telegram bridge talk to one long-running daemon over a group-restricted Unix
socket. Local/private inference is provided by a configured Ollama HTTP server; optional
cloud inference is used only when the operator explicitly selects it.

```text
 full TUI       CLI chat       Telegram (optional)
    │              │                  │
    └──────────── Unix-socket RPC ─────┘
                         │
                  KiloFrame daemon
                         │
       ┌──────────┬──────┼──────┬────────────┐
       │          │      │      │            │
     agent      tools  memory  MCP       security
       │                 │      │
       │              SQLite   Serena / Context7
       │
       ├── configured Ollama server (local or remote)
       └── explicitly selected cloud provider (optional)
```

## Runtime boundaries

- The daemon owns sessions, tool execution, integrations, provider routing, and model
  requests. Closing the TUI does not stop it.
- Front ends connect to `/run/kiloframe/kiloframe.sock`; they do not infer daemon,
  provider, or model state locally.
- `/etc/kiloframe/ollama.json` stores named Ollama endpoints and a selected model per
  endpoint. The Ollama host owns downloads and loaded-model state.
- `/var/lib/kiloframe/memory.sqlite3` stores sessions, messages, learned facts, skills,
  and the tool audit trail.
- An optional provider is never an automatic fallback. A failed Ollama request is
  reported rather than silently sending private input elsewhere.

## Major modules

| Module | Responsibility |
|---|---|
| `cli.py` | command parsing, service controls, status, doctor, logs |
| `tui_full.py` | full-screen Kilo/Sir presentation, sidebar, menus, live events |
| `tui.py` | streaming line-oriented fallback |
| `daemon.py` | daemon lifecycle and integration startup |
| `rpc.py` | newline-delimited JSON RPC over the Unix socket |
| `agent.py` | prompt assembly, agent loop, compaction, tool dispatch |
| `ollama.py` | Ollama configuration and documented HTTP endpoints |
| `runtime.py` | selected Ollama model, streaming, thinking, CPU retry |
| `providers.py` | explicitly selected hosted inference routes |
| `tools.py` | built-in tool registry and implementations |
| `mcp.py` | MCP subprocess lifecycle, discovery, and invocation |
| `memory.py` | bounded SQLite persistence and session history |
| `context.py` | deterministic tool-result compaction |
| `security.py` | path and command policy plus action approvals |
| `resources.py` | host/cgroup resource reporting |
| `doctor.py` | installation and live-health checks |

## Request lifecycle

```text
Sir submits input
      │
      ├── slash command ──> TUI/RPC operation ──> visible result
      │
      └── normal prompt
             │
             ├── load recent session history
             ├── compact older history if it exceeds the budget
             ├── choose agent profile and applicable skills
             ├── announce the real model route
             └── stream model output
                      │
                      ├── text ────────────────> Kilo response box
                      └── tool request
                              ├── validate schema and policy
                              ├── request approval when required
                              ├── execute and audit
                              └── compact result and continue
```

The loop is bounded by effort level and `max_agent_steps`. Repeated identical tool calls
are blocked. Research profiles must successfully search and open a source before their
answer is accepted. Live model, thinking, tool, recovery, compaction, and failure events
are rendered inside Kilo's response presentation.

## Conversation compaction

KiloFrame stores full messages in SQLite but sends a bounded context to the model. Recent
turns are retained newest-first up to `max_history_tokens`; older turns become a compact,
role-labelled record. When this occurs the daemon emits a `compaction` event and the TUI
reports the number of earlier turns compacted. `/new` starts a separate session; `/chats`
and `/chats N` allow an existing one to be resumed.

Tool output is budgeted separately. Oversized structured or text results retain their
head, tail, exit status, and useful surrounding structure while explicitly saying what
was omitted. This prevents a single large command from displacing the conversation.

## Ollama route

KiloFrame uses Ollama's supported endpoints: `/api/version`, `/api/tags`, `/api/ps`,
`/api/show`, `/api/pull`, `/api/chat`, and `/api/generate` with `keep_alive: 0` for
unload. Selection, download, and loaded state are separate:

- `models` is whatever the active server reports downloaded.
- the selected model is stored for that named server only;
- `ps` is whatever that server reports currently running;
- a selection is not labelled loaded until `ps` confirms it.

Thinking controls are sent only when `/api/show` advertises a compatible capability.
On a CUDA out-of-memory response KiloFrame reports the recovery and makes one bounded
retry with Ollama's CPU setting; it never changes endpoint or model silently.

## Integrations and skills

The installer provisions Superpowers, Serena, Context7, and Playwright CLI. Superpowers
skills are imported into KiloFrame's skill memory. Serena and Context7 start as MCP
servers; discovered tools are namespaced and pass through the same permission and output
compaction path as built-ins. Playwright installs its agent skills for browser workflows.

Credential-bound Exa, GitHub MCP, and Firecrawl entries are present but disabled. A
failed optional MCP server is logged and skipped without fabricating an available tool or
taking down the core daemon.

## Security model

- The model is not the security boundary. Model output is untrusted input to policy code.
- Built-in command execution uses an explicit program and argument list, never a shell.
- Paths are resolved and restricted to the service account's home and `/tmp` by default.
- Actions are classified as safe, write, elevated, or destructive; non-safe actions use
  separate approval capabilities.
- Remote Telegram actions are accepted only for allow-listed chat IDs, and non-safe
  actions require a time-limited decision from the same chat.
- Private web mode routes through Tor and fails closed if Tor is unavailable.
- MCP tools are namespaced, schema-checked, permission-gated, and not exposed to remote
  callers.
- Provider secrets live in owner-readable configuration and are not printed in logs or
  command lines.

See [Configuration](wiki/Configuration.md), [Security and privacy](wiki/Security-and-Privacy.md),
and [RPC API](API.md) for operational details.
