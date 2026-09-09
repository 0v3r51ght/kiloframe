# KiloFrame

KiloFrame is a local-first terminal agent framework developed by Citadel Research. It
runs one Kilo runtime behind three clients: the full-screen TUI, the command-line client,
and an optional Telegram bridge. All clients use the same daemon, conversation store,
permission policy, tools, integrations, and route selection.

The local route is Ollama. Ollama may run on the KiloFrame host or on a separate trusted
host reachable over HTTP or HTTPS. Cloud inference is optional and explicit. KiloFrame
never changes route because a request is slow or because another provider is available.

## Current behavior

- The daemon is the only process that owns inference and model state. Clients connect over
  a group-restricted Unix socket.
- The active Ollama endpoint, selected model, and loaded model state are reported from live
  server APIs. Downloaded, selected, and loaded are separate states.
- The TUI displays streaming output, tool activity, failures, recovery, compaction, and
  loaded models in the output pane and sidebar. The sidebar changes between local and cloud
  views and lists actual background processes reported by the daemon.
- `/localset` manages named Ollama endpoints. `/local` opens the local model menu.
  `/cloud` selects or configures a provider. `/model` lists or selects a model on the
  active route. `/switch` changes between the configured routes.
- Telegram has the same route controls. Cloud model lists provide inline selection buttons;
  local load and unload controls are visible only on the local route.
- Built-in tools and connected MCP tools are real, permission-aware operations. Tool
  failures remain visible and cannot be reported as successful work.
- The Kilo directive is applied to local and cloud requests, continuation turns, specialist
  agents, streaming output, and Telegram delivery. Provider identity text cannot replace
  Kilo or Citadel Research at the client boundary.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
kiloframe status
kiloframe doctor
kiloframe
```

Configure Ollama inside the TUI:

```text
/localset add local http://127.0.0.1:11434
/localset default local
/local models
/local select <model-reported-by-the-server>
```

For a remote Ollama server, use its reachable URL. KiloFrame does not copy models between
endpoints and does not infer that a model is loaded before `/api/ps` confirms it.

## Documentation map

- [First run](First-Run) covers installation checks, endpoint setup, model selection, and
  real-terminal acceptance.
- [Installation](Installation) documents supported systems, upgrades, paths, verification,
  and uninstall.
- [Commands](Commands) is the canonical CLI, TUI, and Telegram command reference.
- [Ollama](Ollama) explains endpoint configuration, model lifecycle, thinking controls,
  context limits, and recovery.
- [Conversations and memory](Conversations-and-Memory) covers sessions, compaction, facts,
  skills, and audits.
- [Integrations](Integrations) identifies installed services and credential-bound optional
  services.
- [Configuration](Configuration) documents protected files, environment settings, and
  backups.
- [Architecture](Architecture) describes client, daemon, agent, tool, MCP, and provider
  boundaries.
- [RPC API](../API.md) documents the daemon socket, commands, and streaming event types.
- [Security and privacy](Security-and-Privacy) describes policy, approvals, secrets, Tor,
  and remote Telegram limits.
- [Operations](Operations) covers health checks, service control, logs, upgrades, and
  backups.
- [Troubleshooting](Troubleshooting) provides symptom-based recovery instructions.
- [Testing and verification](Testing-and-Verification) defines source, installer,
  integration, Ollama, Telegram, and real-TUI acceptance checks.

The version-controlled files under `docs/wiki` are the source for the hosted repository
Wiki. Code-level details remain in [Architecture](../ARCHITECTURE.md),
[Capabilities](../CAPABILITIES.md), and [Troubleshooting](../TROUBLESHOOTING.md).
