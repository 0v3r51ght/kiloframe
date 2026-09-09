# KiloFrame maintainer handover

KiloFrame's maintained operational documentation is the
[GitHub Wiki](https://github.com/0v3r51ght/kiloframe/wiki), with version-controlled source
under [`docs/wiki`](docs/wiki). This handover intentionally avoids duplicating volatile
test counts, private endpoints, model inventories, or completion claims.

## Current product invariants

- Local/private inference uses a user-configured local or remote Ollama endpoint.
- Endpoint reachability, downloaded models, and loaded models come from live Ollama APIs.
- Cloud providers are optional and explicitly selected; there is no silent cloud fallback.
- The full TUI keeps live Kilo activity and the answer in one Kilo response box, separate
  from Sir's input.
- Status and UI readiness labels must be evidence-based.
- Superpowers, Serena, Context7, and Playwright CLI are installed/preconfigured by the
  main installer.
- Exa, GitHub MCP, Firecrawl, Telegram, and cloud routes remain optional when credentials
  or external services are required.
- Conversation context compacts automatically while persistent sessions remain in SQLite.
- Telegram natural-language replies use the same Core Directive on local and cloud routes;
  the bridge enforces the final `Sir, ... , Sir.` form and exposes live local model controls.

## Before changing or releasing

Read:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/BUILDER_NOTES.md`](docs/BUILDER_NOTES.md)
- [`docs/INSTALLATION.md`](docs/INSTALLATION.md)
- [`docs/COMMANDS.md`](docs/COMMANDS.md)
- [`docs/wiki/Testing-and-Verification.md`](docs/wiki/Testing-and-Verification.md)

Run the full test suite, execute the published installer, inspect an actual PTY/TUI,
perform real inference against a test endpoint, restart and relaunch, and synchronize the
hosted Wiki. Never put a private endpoint, token, operator model inventory, or ephemeral
test result in tracked documentation.
