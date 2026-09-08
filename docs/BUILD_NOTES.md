# KiloFrame current build notes

These notes describe the current KiloFrame product. Git history is the source for older
implementation detail; obsolete runtime designs are intentionally not documented as
current behavior.

## Runtime

- Local/private inference uses a named local or remote Ollama HTTP endpoint.
- Downloaded, selected, and loaded models are separate states obtained from the active
  endpoint.
- Optional cloud inference is explicit and is never an automatic fallback.
- The daemon starts independently of Ollama availability so configuration and diagnostics
  remain usable while an endpoint is offline.
- Conversation and tool-result context compact automatically within bounded budgets and
  report compaction to the TUI.

## Interface

- The full TUI preserves separate Sir input and Kilo response presentation.
- Thinking, tools, results, errors, model recovery, and final text share Kilo's box.
- The sidebar displays grounded task, work, context, route/model, session, and loaded-model
  information.
- The wordmark reads KILOFRAME; its Citadel Research credit aligns with the wordmark's left
  edge.
- `/commands` and completion expose the registered slash-command surface.

## Integrations

- Superpowers, Serena, Context7, and Playwright CLI are provisioned by the installer.
- Serena and Context7 are enabled MCP servers on first install.
- Exa, GitHub MCP, and Firecrawl are credential-bound and disabled by default.
- Optional server failure is logged and skipped rather than presented as readiness.

## Installation contract

- The online installer downloads current `main` without accepting a stale cached branch
  archive, runs the full installer, starts/restarts the daemon, and prints status.
- Both operational-systemd and non-systemd hosts are supported.
- Reinstall preserves operator configuration and SQLite data.
- Uninstall stops the daemon before removing application, config, data, logs, wrapper, and
  the default service account.
- A retained service group does not prevent recreating the service account.

## Verification contract

Before release, run shell syntax checks, the complete unittest discovery, installer tests,
a public one-line install, doctor/status, integration discovery, a real TUI session with
slash commands and live inference, daemon restart/relaunch, and the branding/privacy/docs
audit. Exercise uninstall/reinstall whenever their code changes.

See [Testing and verification](wiki/Testing-and-Verification.md) for the acceptance
checklist and [Architecture](ARCHITECTURE.md) for the implementation map.
