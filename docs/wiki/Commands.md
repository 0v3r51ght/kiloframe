# Commands

## Command interaction

The TUI publishes one canonical slash-command list through `/commands`; compatibility
aliases are accepted but are not duplicated in the picker. Use Up/Down and Enter for
menus. `/localset`, `/cloud`, `/model`, `/agent`, `/effort`, `/thinking`, `/private`,
`/chats`, and `/mcp` use selection first and only ask for free text when an address,
credential, custom model, or other value is genuinely required.

When `/cloud` is open, select **Search provider catalog…**, type a fragment such as
`groq`, `nvidia`, or `kimi`, and press Enter to filter the catalog; direct typing in the
picker also filters it. Then use the normal arrow-key selection. `/switch` activates
the persisted configured cloud provider even after reopening KiloFrame; the next
`/switch` returns to Ollama.

## Shell CLI

| Command | Purpose |
|---|---|
| `kiloframe` | launch full TUI, or streaming fallback without a real terminal |
| `kiloframe chat "MESSAGE"` | stream one response |
| `kiloframe status` | daemon/model/endpoint/uptime/memory/recovery status |
| `kiloframe doctor` | installation and live health checks |
| `kiloframe resources` | JSON host/cgroup resource profile |
| `kiloframe model-info` | active Ollama endpoint and selected model |
| `kiloframe version` | application/runtime version information |
| `kiloframe logs -n 100` | recent systemd or detached-daemon log |
| `sudo kiloframe start`, `stop`, `restart` | daemon lifecycle; normal use is `kiloframe` |
| `kiloframe benchmark` | time a real short inference |

### Ollama CLI

```text
kiloframe local [status]
kiloframe local models
kiloframe local ps
kiloframe local pull MODEL
kiloframe local select MODEL
kiloframe local load [MODEL]
kiloframe local unload [MODEL]
kiloframe localset [list]
kiloframe localset add NAME URL
kiloframe localset default NAME
kiloframe localset remove NAME
```

### Optional Telegram CLI

```text
kiloframe telegram status
kiloframe telegram set-token TOKEN
kiloframe telegram allow CHAT_ID
kiloframe telegram disallow CHAT_ID
kiloframe telegram disable
```

## TUI slash commands

Slash-command completion appears while typing. Interactive commands show menus and accept
the displayed number where documented.

### Help and lifecycle

- `/commands` — complete in-app command list.
- `/help` — short usage guide.
- `/cancel` — cancel the active request and clear its queue.
- `/new` — start a fresh session.
- `/clear` — clear the current rendered screen.
- `/quit` — leave the TUI; the daemon remains active.
- `/mcp` — inspect live MCP state and select a connected server to view its discovered tools.

### Local/remote Ollama

- `/local` — interactive Ollama menu.
- `/local status` — endpoint, version, selected model, downloads, and loaded count.
- `/local models` — numbered list returned by the active server.
- `/local ps` — models reported loaded/running.
- `/local pull MODEL` — live pull progress.
- `/local select MODEL_OR_NUMBER` — select a downloaded model.
- `/local unload [MODEL]` — request unload.
- `/localset` or `/localset list` — configured endpoint menu.
- `/localset add NAME URL` — add/update an endpoint.
- `/localset default NAME` — activate a named endpoint.
- `/localset remove NAME` — remove an endpoint.
- `/switch` — toggle Ollama and an already configured cloud route.

### Response behavior

- `/thinking off|on|low|medium|high` — native thinking where the selected model advertises
  support. Unsupported levels are not pretended.
- `/effort low|medium|high` — response-token and agent-step budget.
- `/agent NAME` — force `orchestrator`, `research`, `coding`, `security`, `math`,
  `engineering`, `systems`, `general`, `conversation`, or `private`.
- `/agent off` — restore automatic selection.

### Cloud and privacy

- `/cloud` — configure or inspect a provider.
- `/cloud key` — add/change provider configuration.
- `/cloud` → `Custom endpoint` — configure a named OpenAI-compatible HTTPS URL, model,
  and API key without hand-editing JSON.
- `/cloud QUESTION` — one explicit cloud request.
- `/model` — fetch the selected provider's model catalogue.
- `/model NAME_OR_NUMBER` — select a provider model.
- `/private on|status|rotate|off` — control fail-closed Tor routing for web operations.

No cloud provider is required. `/switch` reports when none exists instead of implying a
connection. `/thinking` does not claim cloud support without a verified control.

### Sessions

- `/chats` — list recent sessions.
- `/kilochats` — list and arm number selection.
- `/chat N` — resume a listed session.
- `/delete`, `/delete N`, `/delete N,M`, `/delete all` — delete chosen history.

Conversation compaction is automatic and visible. Persistent history remains in SQLite;
only the bounded model-facing context is compacted, so no manual `/compact` command is
needed.

Use `kiloframe --help` or `kiloframe <command> --help` for generated argument syntax.
