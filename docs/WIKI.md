# KiloFrame Wiki source

The repository Wiki is generated from the Markdown pages in [`docs/wiki`](wiki). It is
kept deliberately factual: optional services are documented as optional, and runtime
state comes from the selected Ollama server rather than guesses made by the client.

| Wiki page | Purpose |
|---|---|
| [Home](wiki/Home.md) | Product overview and documentation map |
| [First run](wiki/First-Run.md) | Initial configuration and human TUI acceptance |
| [Installation](wiki/Installation.md) | Installer, upgrades, uninstall, paths, and integrity checks |
| [Commands](wiki/Commands.md) | Every CLI and full-TUI slash command |
| [Ollama](wiki/Ollama.md) | Local/remote endpoint and model lifecycle |
| [Conversations and memory](wiki/Conversations-and-Memory.md) | Sessions, persistence, compaction, facts, and skills |
| [Integrations](wiki/Integrations.md) | Required preconfiguration and optional services |
| [Configuration](wiki/Configuration.md) | Files, settings, ownership, environment, and backups |
| [Architecture](wiki/Architecture.md) | Clients, daemon, agent, tools, routes, and RPC |
| [RPC API](API.md) | Daemon socket, commands, streaming events, and client behavior |
| [Security and privacy](wiki/Security-and-Privacy.md) | Policy, approvals, secrets, MCP, and Tor |
| [Operations](wiki/Operations.md) | Status, daemon control, logs, upgrade, and backup |
| [Troubleshooting](wiki/Troubleshooting.md) | Symptom-based diagnosis and safe recovery |
| [Testing and verification](wiki/Testing-and-Verification.md) | Source, install, integration, Ollama, and real-TUI checks |

The detailed repository documentation remains the source of truth for code-level
architecture and troubleshooting: [Architecture](ARCHITECTURE.md),
[Capabilities](CAPABILITIES.md), and [Troubleshooting](TROUBLESHOOTING.md).
