# KiloFrame maintainer notes

This file records invariants that future changes must preserve. User-facing setup and
operation belong in the [Wiki](WIKI.md).

## Product contract

- Ollama is KiloFrame's local/private inference route. Do not restore a direct GGUF
  download or runtime subsystem.
- The active Ollama endpoint is configurable and may be local or remote. Always query
  that endpoint for its downloads and running models.
- Cloud inference is explicit per route or request. Never make it an automatic fallback.
- The TUI keeps Sir's input distinct from Kilo's bordered response. Tool activity,
  recovery, compaction, and failure events remain inside Kilo's response presentation.
- Status is evidence-based. Do not label an endpoint reachable, a model loaded, or the
  system ready without the corresponding RPC/Ollama evidence.
- Superpowers, Serena, Context7, and Playwright CLI are installer-provisioned. Exa,
  GitHub MCP, and Firecrawl remain disabled until their credentials are configured.
- Permission gates, path policy, remote allow-lists, and the tool audit trail are not
  optional UI conventions; they are security boundaries.

## Release workflow

1. Run `bash -n scripts/install.sh scripts/install-online.sh scripts/uninstall.sh`.
2. Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
3. Exercise the published one-line installer on the target environment.
4. Inspect `kiloframe status`, `kiloframe doctor`, and integration startup logs.
5. Use a real terminal to test `/commands`, `/local`, `/localset`, `/thinking`, session
   commands, cancellation, and a genuine model response.
6. Exercise uninstall and reinstall when installer behavior changes.
7. Audit public files for stale branding, private addresses, secrets, and documentation
   that no longer matches the implementation.
8. Synchronize `docs/wiki/` to the hosted GitHub Wiki.

Do not update a fixed test-count claim here; the suite is authoritative and changes as
coverage is added.
