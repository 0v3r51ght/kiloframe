# KiloFrame Wiki source

The repository Wiki is generated from the Markdown pages in [`docs/wiki`](wiki). It is
kept deliberately factual: optional services are documented as optional, and runtime
state comes from the selected Ollama server rather than guesses made by the client.

| Wiki page | Purpose |
|---|---|
| [Home](wiki/Home.md) | Product overview and first run |
| [Installation](wiki/Installation.md) | Installer, non-systemd operation, uninstall, integrity checks |
| [Commands](wiki/Commands.md) | CLI and full-TUI slash commands |
| [Ollama](wiki/Ollama.md) | Local/remote server configuration and lifecycle |
| [Operations](wiki/Operations.md) | Status, recovery, logs, and troubleshooting |
| [Integrations](wiki/Integrations.md) | Optional skills and MCP integrations |

The detailed repository documentation remains the source of truth for code-level
architecture and troubleshooting: [Architecture](ARCHITECTURE.md),
[Capabilities](CAPABILITIES.md), and [Troubleshooting](TROUBLESHOOTING.md).
