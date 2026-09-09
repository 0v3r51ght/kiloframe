```text
██╗  ██╗██╗██╗      ██████╗ ███████╗██████╗  █████╗ ███╗   ███╗███████╗
██║ ██╔╝██║██║     ██╔═══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝
█████╔╝ ██║██║     ██║   ██║█████╗  ██████╔╝███████║██╔████╔██║█████╗
██╔═██╗ ██║██║     ██║   ██║██╔══╝  ██╔══██╗██╔══██║██║╚██╔╝██║██╔══╝
██║  ██╗██║███████╗╚██████╔╝██║     ██║  ██║██║  ██║██║ ╚═╝ ██║███████╗
╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝
  Developed by Citadel Research
```

# KiloFrame

KiloFrame is a local-first terminal agent framework developed by Citadel Research. It
provides one Kilo runtime through a full-screen terminal interface, a scriptable CLI, and
an optional Telegram bridge. KiloFrame connects to an Ollama server on the local machine
or on another host, and can use an explicitly selected cloud provider when one is
configured. The active route is always visible and a failed route is never replaced
silently.

The daemon owns inference, conversations, tools, and integrations. Clients connect to it
over a group-restricted Unix socket, so the TUI, CLI, and Telegram bridge share the same
model selection, memory, permissions, and live status. The framework reports state from
the configured server: downloaded, selected, and loaded are separate model states.

## Capabilities

- Full-screen TUI with a bordered Kilo output pane, separate input area, live streaming,
  activity details, scrollbar, command completion, and a live sidebar.
- CLI for prompts, service control, status, health checks, resources, logs, and benchmarks.
- Local or remote Ollama endpoint management, model discovery, pull, selection, loading,
  unloading, context configuration, and CUDA out-of-memory recovery.
- Explicit cloud routing with provider and model selection. Supported catalog entries
  include OpenRouter, OpenAI, Anthropic, Gemini, Groq, Together, DeepInfra, DeepSeek,
  Moonshot/Kimi, NVIDIA NIM, Venice, Z.AI, Scaleway, Cohere, Mistral, Cerebras,
  Fireworks, SambaNova, Hugging Face, Nebius, Hyperbolic, ModelScope, Agnes AI, Ollama
  Cloud, LLM7, OpenCode Zen, and GLHF. Custom OpenAI-compatible HTTPS endpoints are also
  supported.
- Real filesystem, shell, system, web search, web fetch, memory, reference, and MCP
  tools. State-changing operations are approval-gated by the policy engine.
- Persistent SQLite conversations, bounded context compaction, facts, learned skills,
  audit records, specialist profiles, and cancellation with per-chat concurrency control.
- Optional Telegram bot with local/cloud controls, live progress, approval buttons,
  model selection, and the same Kilo directive used by the TUI and CLI.
- Installer and uninstaller for systemd and non-systemd hosts. The daemon runs under a
  dedicated service account and preserves configuration and data during upgrades.

## Requirements

The supported installer targets a Linux host with one of `apt`, `pacman`, `dnf`, `zypper`,
or `apk`, plus network access for the application and required integrations. Python 3.11
or newer, SQLite, curl, ripgrep, Git, Node.js, and npm are installed or verified by the
installer. An Ollama server is required for local inference but may run on another host.
Cloud credentials and Telegram credentials are optional.

## Install

Install the current `main` branch with the online installer:

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
```

The installer downloads a cache-busted source archive, installs the application and
required integrations, creates the `kiloframe` service account, preserves existing
configuration and SQLite data, starts the daemon, and prints live status. It also
installs the self-contained `kiloframe uninstall` command. It does not download an
Ollama model.

On a host running systemd, the installer enables `kiloframe.service` for the
`multi-user.target`, so the daemon starts again after shutdown or reboot. The service
keeps its SQLite data and configuration outside `/run`; only the PID and RPC socket are
recreated at each boot. Use `sudo kiloframe start|stop|restart` for lifecycle control.

To install a checked-out tree:

```bash
git clone https://github.com/0v3r51ght/kiloframe.git
cd kiloframe
sudo ./scripts/install.sh
```

After installation, open a new login session if the installer added your account to the
`kiloframe` group. Run the client as the normal user; use `sudo` only for service lifecycle
commands when required.

## First local conversation

Check the installation before opening the TUI:

```bash
kiloframe status
kiloframe doctor
```

Configure a local Ollama endpoint and select a model reported by that endpoint:

```text
/localset add local http://127.0.0.1:11434
/localset default local
/local models
/local select <model-name>
```

For a remote Ollama host, replace the URL with the address reachable from the KiloFrame
host. The endpoint owns its own model storage and loaded state; a model downloaded on one
endpoint is not assumed to exist on another.

Start the interface and send a prompt:

```bash
kiloframe
```

Use `/commands` for the complete command list. The most frequently used commands are:

| Command | Purpose |
|---|---|
| `/local` | Open the Ollama route menu |
| `/localset` | Add, remove, select, or inspect Ollama endpoints |
| `/local models` | List downloaded models on the active endpoint |
| `/local select MODEL_OR_NUMBER` | Select a server-reported model |
| `/local load [MODEL]` | Load a downloaded model into Ollama memory |
| `/local unload [MODEL]` | Unload a model from Ollama memory |
| `/cloud` | Configure or select a cloud provider |
| `/model` | List or select a model on the active cloud route |
| `/switch` | Switch between the configured local and cloud routes |
| `/thinking` | Configure supported native model thinking |
| `/cancel` | Cancel active work and clear queued work |
| `/new` | Start a fresh conversation session |
| `/chats` | Browse or resume stored sessions |
| `/mcp` | Inspect live MCP servers and discovered tools |

## Telegram bot

Telegram is disabled until a bot token is configured. Configure it from the host:

```bash
kiloframe telegram set-token <BOT_TOKEN>
kiloframe telegram allow <CHAT_ID>
kiloframe telegram status
```

Each chat must send `/start` before ordinary messages are accepted. The bot uses the same
daemon and route boundary as the TUI. `/local`, `/cloud`, and `/switch` select the route;
`/models` lists models on the active route; and `/model MODEL_ID` selects a model. Cloud
model lists include inline selection buttons. Ollama load and unload controls are shown
only while the chat is on the local route. `/local_models`, `/local_ps`, `/local_load`, and
`/local_unload` never fall through to a cloud provider.

Telegram natural-language replies use the same Kilo directive as local conversations and
are normalized at delivery so a provider cannot identify Kilo as another assistant or
creator. Progress and machine work are sent as live status cards, and a slow inference
does not block commands or other chats.

## Cloud providers

Cloud inference is optional and explicit. Configure a provider in the TUI with `/cloud`
or use the provider configuration flow described in [Configuration](docs/wiki/Configuration.md).
KiloFrame validates HTTPS endpoints, keeps credentials in a mode `0600` file, queries live
model catalogs where supported, and never falls back to local or cloud inference without
the selected route. Cloud models receive the same tool schemas as local models. A provider
error is reported as an error; it is not presented as a completed answer.

## Tools, web research, and MCP

The built-in tools include file inspection and writing, bounded command execution, system
information, public web search and fetch, persistent memory, offline references, and
repeatable skills. Tool results are recorded and validated before Kilo reports an action
as successful. Web research uses search followed by source retrieval when the request
requires current information.

The installer provisions Superpowers, Serena, Context7, and Playwright CLI. Serena and
Context7 are enabled MCP services. Exa, GitHub MCP, Firecrawl, Telegram, and cloud
providers remain optional because they require credentials or an external service. Use
`/mcp` or `kiloframe logs -n 200` to inspect live integration state.

## Status and operations

```bash
kiloframe status
kiloframe doctor
kiloframe resources
kiloframe logs -n 100
kiloframe benchmark
sudo kiloframe restart
sudo kiloframe uninstall
```

`status` distinguishes daemon state, endpoint reachability, model selection, and loaded
state. `doctor` checks installation paths, the socket, database, Ollama API, model, and
resources. On a non-systemd host, the same wrapper controls the detached daemon.

If `sudo kiloframe start` is needed on a non-systemd host, it starts the daemon as the
dedicated `kiloframe` account with the installed Python runtime. On systemd hosts the
same command delegates to systemd. Non-systemd machines need an external boot supervisor
if the daemon must return after a reboot.

`sudo kiloframe uninstall` is the supported removal workflow. It works from any
directory and removes the service, application, managed configuration/data, and wrapper.
Back up `/etc/kiloframe` and `/var/lib/kiloframe` first if they must be retained.

Important paths are:

| Path | Contents |
|---|---|
| `/usr/local/bin/kiloframe` | Client and service wrapper |
| `/opt/kiloframe/app` | Installed application |
| `/opt/kiloframe/integrations` | Required integration assets |
| `/etc/kiloframe` | Ollama, provider, Telegram, MCP, and policy configuration |
| `/var/lib/kiloframe` | Persistent SQLite memory and sessions |
| `/var/log/kiloframe` | Detached daemon logs |
| `/run/kiloframe` | PID file and group-restricted RPC socket |

## Security model

Local and cloud routes are explicit. The daemon applies path and command policy before
executing tools, requests approval for state-changing or outward actions, keeps provider
and Telegram secrets out of source and logs, and exposes only the permitted built-in tool
set to Telegram. Private web mode fails closed when Tor is unavailable. MCP services run
as subprocesses and their tools are namespaced and validated before exposure.

## Documentation

- [Installation](docs/INSTALLATION.md): supported systems, upgrade, verification, and uninstall
- [Commands](docs/COMMANDS.md): complete CLI, TUI, and Telegram command reference
- [Troubleshooting](docs/TROUBLESHOOTING.md): diagnosis by symptom
- [Architecture](docs/ARCHITECTURE.md): daemon, RPC, agent, tools, and route boundaries
- [RPC API](docs/API.md): newline-delimited daemon protocol and live event types
- [Capabilities](docs/CAPABILITIES.md): installed and optional functionality
- [Wiki source](docs/WIKI.md): synchronized pages for setup, operations, integrations, and testing
- [Online wiki](https://github.com/0v3r51ght/kiloframe/wiki): rendered documentation

## Development and verification

Run the syntax checks and test suite from a checkout:

```bash
bash -n scripts/install.sh scripts/install-online.sh scripts/uninstall.sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
git diff --check
```

The release verification workflow also exercises the installer, a real Ollama endpoint,
the TUI in a real terminal, Telegram route controls, cloud model selection, MCP discovery,
and failure recovery. See [Testing and verification](docs/wiki/Testing-and-Verification.md).

## License

KiloFrame is released under the MIT License. See [LICENSE](LICENSE).
