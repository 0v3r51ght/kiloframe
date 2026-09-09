# Integrations

KiloFrame distinguishes required preconfigured workflow integrations from optional
credential-bound services. The daemon only advertises tools that actually start and
complete discovery.

## Installed and preconfigured

| Integration | Installation | KiloFrame connection | Verification |
|---|---|---|---|
| Superpowers | official repository under `/opt/kiloframe/integrations/superpowers` | skill Markdown imported into bounded skill memory | `kiloframe status` skill count; inspect installer output |
| Serena | `serena-agent` installed through `uv` under integrations | enabled MCP command `serena start-mcp-server` | `command -v serena`; daemon log shows discovered tools |
| Context7 | global `@upstash/context7-mcp` package | enabled MCP command `context7-mcp` | `command -v context7-mcp`; daemon log shows discovered tools |
| Playwright CLI | global official CLI plus agent-neutral skill under `/opt/kiloframe/integrations/playwright` | official skill is imported into KiloFrame memory | `command -v playwright-cli`; inspect skill count/path |

These are installed by the normal installer, not left as manual post-install steps. A
failure to provision one causes installation to fail clearly.

### Superpowers

Superpowers supplies development workflow procedures. KiloFrame loads appropriate skill
content into its SQLite skill system so applicable procedures can be surfaced to the
agent without permanently inflating every prompt. The installed checkout can be updated
by rerunning the installer.

### Serena

Serena supplies semantic code navigation through MCP. The daemon starts it as a subprocess,
performs MCP initialization, discovers its tool schemas, and namespaces them. A startup
failure is logged; KiloFrame does not display nonexistent tools as ready.

### Context7

Context7 provides current library documentation for coding/research workflows. Its server
is enabled in `/etc/kiloframe/mcp.json`. Older generated configurations that invoked it
through `npx` on every startup are migrated to the installed command.

### Playwright CLI and agent skills

Playwright CLI is the primary browser workflow integration. The installer uses the
official `playwright-cli install --skills=agents` mode inside KiloFrame's integration
directory, verifies the resulting `SKILL.md`, and imports its real content into KiloFrame
memory at daemon startup. It does not use another agent's private skill directory. This
does not claim every browser/dependency is available on every distribution; validate the
concrete browser workflow on its target host.

## Optional integrations

| Integration | Default | Why |
|---|---|---|
| Exa MCP | disabled | external API key required |
| GitHub MCP | disabled | authentication required; not needed for local launch |
| Firecrawl MCP | disabled | external credentials/service required |
| Telegram | self-service after token setup | bot token required; each user activates their own chat with `/start` |
| Cloud providers | absent | provider API key required |

The default MCP registry contains disabled entries so operators can configure them without
rebuilding the app. Empty tokens are never evidence that a service is available.

KiloFrame also supports operator-defined OpenAI-compatible cloud endpoints through
`/cloud` → **Custom endpoint**. The setup requires HTTPS, a model name, and a key; it does
not make the endpoint active unless the operator selects it.

## MCP lifecycle and safeguards

- Servers are subprocesses connected over stdio JSON-RPC.
- Tool names are namespaced `mcp__<server>__<tool>`.
- Only object-schema tools are exposed.
- Requests time out instead of hanging the daemon indefinitely.
- Results use the same size/context compaction as built-in tools.
- Outward/non-safe actions still require policy approval.
- MCP tools are not exposed to remote Telegram callers.
- One failed optional server is skipped and logged; core startup continues.
- Built-in tool schemas remain available for every request.  Connected MCP schemas are
  selected by request relevance (code requests can include Serena and documentation/API
  requests can include Context7) so a large optional MCP catalog does not needlessly
  increase local-model prompt prefill time.

Use `/mcp` in the TUI for the live authoritative view. It lists every configured server
as connected, disabled, failed, or not connected and lets you select connected servers to
inspect their discovered tools. The wide-screen sidebar mirrors those live counts.

## Inspect and repair

```bash
kiloframe logs -n 200
command -v serena
command -v context7-mcp
command -v playwright-cli
sudo kiloframe restart
```

Look for successful MCP initialization and a nonzero discovered-tool count in the daemon
log. Rerun the installer to repair required packages. Configure credentials only in
protected runtime configuration—never in the repository or Wiki.

## Telegram self-service activation

After storing a real bot token with `/botkey` or `sudo kiloframe telegram set-token`, the
bridge starts even when no chat is yet allowed. A Telegram user activates their own chat by
sending `/start`; KiloFrame records that chat ID and immediately sends the normal introduction.
Messages from a chat that has not sent `/start` are ignored. Use
`sudo kiloframe telegram status` to review the resulting allow-list.

### Telegram route controls and directive

The bot exposes the same local/cloud route controls as the TUI. Use `/local` to select
Ollama, `/cloud` to select an explicitly configured provider, or `/switch` to toggle between
them. `/local_models`, `/local_ps`, `/local_load [MODEL]`, and `/local_unload [MODEL]` query
and control model residency on the active Ollama endpoint; `/model` selects the model for
the active route. These controls report live server state and do not imply that a model is
loaded until Ollama reports it.

Every natural-language Telegram reply passes through Kilo's Core Directive for both local
and cloud inference. The bridge also normalizes the final combined stream, which covers
providers or models that ignore the system prompt and guarantees the visible form
`Sir, ... , Sir.`. Progress, status, help, and approval cards are operational UI messages.
