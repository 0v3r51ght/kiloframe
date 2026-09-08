# KiloFrame commands

## Shell commands

| Command | Effect |
|---|---|
| `kiloframe` | open the full TUI on a real terminal, or the streaming fallback otherwise |
| `kiloframe chat "message"` | send one prompt and stream its answer |
| `kiloframe status` | show truthful daemon, Ollama, model, uptime, memory, and recovery state |
| `kiloframe doctor` | check installation paths, socket, database, Ollama, model, and resources |
| `kiloframe resources` | print the current host/cgroup resource profile as JSON |
| `kiloframe model-info` | print active endpoint and selected-model metadata |
| `kiloframe version` | show KiloFrame and selected runtime information |
| `kiloframe logs [-n LINES]` | show systemd or detached-daemon logs |
| `kiloframe start` | start the daemon |
| `kiloframe stop` | stop the daemon |
| `kiloframe restart` | stop and start the daemon |
| `kiloframe benchmark [--prompt TEXT]` | time a real streamed inference |

## Ollama shell commands

| Command | Effect |
|---|---|
| `kiloframe local` / `local status` | query active endpoint, version, selected model, downloads, and running models |
| `kiloframe local models` | list models downloaded on the active Ollama server |
| `kiloframe local ps` | list models the active server reports loaded/running |
| `kiloframe local pull MODEL` | stream a model pull on the active server |
| `kiloframe local select MODEL` | select a model already reported downloaded |
| `kiloframe local unload [MODEL]` | request that Ollama unload the named or selected model |
| `kiloframe localset list` | list named endpoints and the active selection |
| `kiloframe localset add NAME URL` | add or update a local/remote endpoint |
| `kiloframe localset default NAME` | make a named endpoint active |
| `kiloframe localset remove NAME` | remove an endpoint from KiloFrame configuration |

Model selection is stored per endpoint. It does not download or load the model. Use
`models` to establish download state and `ps` to establish loaded state.

## Telegram shell commands

| Command | Effect |
|---|---|
| `kiloframe telegram status` | show enabled state, masked token state, and allowed chats |
| `kiloframe telegram set-token TOKEN` | store or replace the bot token |
| `kiloframe telegram allow CHAT_ID` | allow a numeric chat ID |
| `kiloframe telegram disallow CHAT_ID` | remove a chat ID |
| `kiloframe telegram disable` | clear the token and disable the bridge |

Telegram is optional. Do not place tokens in source files or documentation.

## Full-TUI slash commands

### Help and lifecycle

| Command | Effect |
|---|---|
| `/commands` | show every registered TUI command |
| `/help` | show the shorter usage guide |
| `/cancel` | cancel the active request and clear queued requests |
| `/new` | start a new conversation session |
| `/clear` | clear rendered conversation from the current screen |
| `/quit`, `/exit`, `/q` | exit the TUI without stopping the daemon |

Slash-command completion appears while typing. Commands that require a choice render a
numbered interactive menu where appropriate; invalid values display usage rather than
being sent to the model.

### Ollama and routing

| Command | Effect |
|---|---|
| `/local` | open the Ollama menu |
| `/local status` | show real endpoint, selected model, downloads, and loaded count |
| `/local models` | list and number downloaded models |
| `/local ps` | list loaded/running models |
| `/local pull MODEL` | pull with live progress |
| `/local select MODEL_OR_NUMBER` | select a downloaded model |
| `/local unload [MODEL]` | unload through Ollama's keep-alive mechanism |
| `/localset` / `/localset list` | list configured endpoints and open selection flow |
| `/localset add NAME URL` | add or update an endpoint |
| `/localset default NAME` | activate an endpoint |
| `/localset remove NAME` | remove an endpoint |
| `/switch` | switch between Ollama and the configured cloud route |

`/switch` never creates a cloud provider or silently falls back. If none is configured,
it tells the user to run `/cloud`.

### Model behavior

| Command | Effect |
|---|---|
| `/thinking off\|on\|low\|medium\|high` | control native model thinking when advertised |
| `/effort low\|medium\|high` | trade answer/tool budget for speed |
| `/agent NAME` | force an agent profile |
| `/agent off` | restore automatic profile selection |

Valid profiles include `orchestrator`, `research`, `coding`, `security`, `math`,
`engineering`, `systems`, `general`, `conversation`, and `private`. `/thinking` is
capability-gated: generic thinking models receive only on/off controls, level controls
are offered only where supported, and unverified cloud controls remain unavailable.

### Optional cloud and privacy

| Command | Effect |
|---|---|
| `/cloud` | open provider setup or show the active provider |
| `/cloud key` | add or replace provider configuration |
| `/cloud` → `Custom endpoint` | configure an OpenAI-compatible HTTPS URL, model, and key |
| `/cloud QUESTION` | use the configured provider for one request |
| `/model` | list the active provider's reported models |
| `/model NAME_OR_NUMBER` | change the configured cloud model |
| `/private on` | route web search/fetch through Tor |
| `/private status` | test the Tor route |
| `/private rotate` | request a new Tor circuit |
| `/private off` | return web requests to direct networking |

Private mode fails closed: if Tor is unavailable, a private web request is refused rather
than sent directly.

### Conversations

| Command | Effect |
|---|---|
| `/chats` | list recent terminal sessions |
| `/kilochats` | list sessions and arm number-to-open selection |
| `/chat N` | resume a listed session |
| `/delete` | open the deletion selector |
| `/delete N` or `/delete N,M` | delete selected listed sessions |
| `/delete all` | delete all sessions shown by the selector |

Conversation context compacts automatically when the model-input budget is exceeded.
The TUI reports compaction live; there is no manual `/compact` command because persistent
history remains available while only the model-facing context is bounded.

Use `kiloframe --help` and `kiloframe <command> --help` for parser-generated syntax.
