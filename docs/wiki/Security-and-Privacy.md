# Security and privacy

KiloFrame treats the model as an untrusted planner, not a security boundary.

## Local route and cloud boundary

Ollama is the default model route. A cloud provider is used only after explicit setup and
selection or for an explicit `/cloud QUESTION`. An Ollama error never triggers cloud
fallback. Provider configuration is absent by default.

Remember that “remote Ollama” is still remote network inference: prompts travel to the
configured host. Use a trusted network or appropriate TLS termination.

## Telegram conversation boundary

Telegram uses the same explicit route boundary as the TUI: `/local` sends inference to the
configured Ollama endpoint and `/cloud` or `/switch` uses only an explicitly configured
cloud provider. There is no automatic cloud fallback. The Core Directive is included in
both routes and enforced again on the final Telegram message, so model output is rendered
as `Sir, ... , Sir.` even when the upstream model omits that address. Status, help, progress,
and approval messages are control-plane UI and are not conversational model answers.

## Command and path policy

- Commands execute as program plus argument vector, not through a shell.
- Shell operators and unsafe constructions are rejected.
- Paths are resolved before policy checks.
- Default writable/readable roots for agent tools are the service user's home and `/tmp`.
- Commands/actions are classified as safe, write, elevated, or destructive.
- Non-safe categories require their own session approval capability.
- Output, file size, execution time, and model-visible results are bounded.
- Every tool call is recorded in the SQLite audit table.

Do not make the daemon or socket world-writable to fix a login-group problem. Acquire the
installed group in a new session instead.

## MCP trust boundary

MCP processes are external code. KiloFrame namespaces discovered tools, requires usable
object schemas, imposes request timeouts, applies permission gates, compacts results, and
does not expose MCP tools to Telegram callers. Disable any server whose source/configuration
you do not trust.

## Private web mode

`/private on` routes supported web search/fetch through Tor. `/private status` tests it and
`/private rotate` requests a new circuit. If Tor is unavailable, private web requests fail
closed rather than silently using the direct network. `/private off` restores direct web
requests.

This controls KiloFrame's web operations; it does not claim to anonymize Ollama, cloud
provider, MCP, shell, or unrelated system traffic.

## Secrets

- provider keys live in `/etc/kiloframe/providers.json`;
- Telegram tokens live in `/etc/kiloframe/telegram.json`;
- optional MCP keys live in `/etc/kiloframe/mcp.json`;
- sensitive configuration should remain service-owned mode `0600`;
- keys should never appear in repository files, Wiki pages, screenshots, command history,
  or shared logs.

The Telegram bridge masks tokens in status, only accepts allow-listed numeric chat IDs,
and binds non-safe approvals to the originating chat with an expiry.

## Reporting a concern

Capture the KiloFrame version, exact operation, policy decision, and sanitized logs. Remove
tokens, private endpoints, usernames, and message content that is not necessary to
reproduce the issue before sharing it.
