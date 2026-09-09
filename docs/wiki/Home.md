# KiloFrame

KiloFrame is Kilobyte (“Kilo”): a full-screen terminal agent framework developed by
Citadel Research. Its daemon connects Kilo to the AI brain you choose—an Ollama server
on the same machine or elsewhere, or an explicitly configured cloud provider. The model
route is always explicit; KiloFrame never silently substitutes a provider or model.

The interface is evidence-based. The sidebar and footer distinguish configuration from
live state: an endpoint is not shown online unless it responds; a selected model is not
shown loaded unless Ollama reports it in `/api/ps`; and failures, tool activity, recovery,
and conversation compaction appear live inside Kilo's response box.

## Current release behavior

- Run `kiloframe` as the normal user. It connects to the same rootless daemon as the
  administrative command; sudo is only needed for service lifecycle operations.
- `/localset` is a guided, selectable setup flow for local or remote Ollama endpoints.
- `/switch` immediately activates the last configured cloud provider on a fresh TUI,
  then switches back to Ollama on the next use.
- `/cloud` includes a visible **Search provider catalog…** action and also accepts a
  provider-name fragment to filter the selectable catalog.
- `/local` can select, preload, unload, pull, and inspect models without leaving the TUI.
- `/mcp` shows the daemon's live MCP inventory, including connected, disabled, and failed
  servers plus their discovered tool counts.
- The output scrollbar responds to click, drag, wheel, PageUp/PageDown, and keeps the
  viewed position when new output arrives.
- Kilo's runtime directive applies consistently across model switches, tools, recovery,
  multi-step work, and specialist-agent execution.
- Telegram uses the same local/cloud controls and enforces the directive on every completed
  natural-language reply, including replies from models that omit the required address.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
kiloframe status
kiloframe doctor
kiloframe
```

Inside the TUI:

```text
❯ /localset add local http://127.0.0.1:11434
❯ /local models
❯ /local select <model-reported-by-the-server>
❯ /commands
❯ Hello, Kilo.
```

An Ollama endpoint is configurable, not an installation prerequisite. If the default
endpoint is offline, KiloFrame should launch and report that fact accurately.

## What is included

- full-screen terminal UI with separate Sir input and bordered Kilo output;
- streaming output with live thinking, tools, failures, CPU recovery, and compaction;
- live sidebar for task, work items, context, active route/model, sessions, and loaded
  models;
- local or remote Ollama endpoint management, pull, select, inference, and unload;
- automatic bounded conversation compaction with persistent SQLite sessions;
- explicit optional cloud providers without silent fallback;
- permission-gated built-in and MCP tools;
- preconfigured Superpowers, Serena, Context7, and Playwright CLI;
- optional credential-bound Exa, GitHub MCP, Firecrawl, and Telegram;
- systemd and non-systemd daemon controls;
- installer, uninstaller, doctor, status, logs, and real inference benchmark.

## Documentation map

- [Installation](Installation) — supported hosts, one-line install, layout, verification,
  upgrades, and uninstall
- [First run](First-Run) — first interactive setup and a human verification checklist
- [Commands](Commands) — every shell command and full-TUI slash command
- [Ollama](Ollama) — endpoint, model, thinking, load, unload, and failure behavior
- [Conversations and memory](Conversations-and-Memory) — sessions, history, compaction,
  facts, skills, and deletion
- [Integrations](Integrations) — what is preconfigured, optional, and how to verify it
- [Configuration](Configuration) — files, ownership, environment settings, and backups
- [Architecture](Architecture) — daemon, RPC, agent, tools, model routes, and event flow
- [Security and privacy](Security-and-Privacy) — policy, approvals, secrets, Tor, and MCP
- [Operations](Operations) — status, service lifecycle, logs, upgrades, and backups
- [Troubleshooting](Troubleshooting) — symptom-based diagnosis and recovery
- [Testing and verification](Testing-and-Verification) — source, installer, integration,
  and real-TUI acceptance checks

## Operating principles

KiloFrame never silently changes route when inference fails. It never treats a configured
provider as connected, and it never treats a downloaded model as loaded. Credential-bound
services remain optional. A command or source change is not considered verified until its
real user workflow has been exercised.
