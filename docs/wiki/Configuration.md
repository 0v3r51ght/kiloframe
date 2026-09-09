# Configuration

KiloFrame keeps system installation state under `/etc`, `/var/lib`, `/var/log`, and
`/run`. Prefer supported commands over hand-editing JSON because the daemon performs
validation and atomic updates.

## Files

| File | Purpose | Normal management |
|---|---|---|
| `/etc/kiloframe/ollama.json` | named endpoints, active endpoint, selected model per endpoint | `/localset`, `/local` |
| `/etc/kiloframe/mcp.json` | MCP commands, arguments, environments, enabled flags | installer; careful operator edit for optional services |
| `/etc/kiloframe/policy.json` | command/path permission policy | administrator review/edit |
| `/etc/kiloframe/providers.json` | optional cloud endpoints, models, credentials | `/cloud`, `/model` |
| `/etc/kiloframe/telegram.json` | token and allowed chat IDs | `/botkey` or `kiloframe telegram ...` |

Configuration is owned by the service account/group and sensitive files use mode `0600`.
Do not relax the runtime socket or credential files to world-readable/writable.

## Ollama configuration

Use:

```bash
kiloframe localset add NAME URL
kiloframe localset default NAME
kiloframe localset list
kiloframe local select MODEL
```

An endpoint entry contains its URL, enabled state, and model. The active endpoint name is
stored separately. Do not copy a selection across endpoints unless that endpoint itself
reports the same model downloaded.

## MCP configuration

On first install, Context7 and Serena are enabled. Exa, GitHub MCP, and Firecrawl exist as
disabled templates with empty secrets. Enabling an optional entry requires both the
external service setup and its credential. Restart KiloFrame after a manual MCP change,
then verify startup and discovered tools in logs.

## Cloud providers

Cloud configuration does not exist by default. `/cloud` guides provider selection and
key entry, while `/model` queries and changes its model where supported. Provider routing
is explicit. Removing or breaking the provider configuration must not make KiloFrame send
an Ollama prompt elsewhere.

The built-in catalog includes OpenRouter, OpenAI, Groq, Together, DeepInfra, DeepSeek,
Moonshot/Kimi, NVIDIA NIM, Venice, Z.AI, Scaleway, Cohere, Anthropic, Google Gemini,
Mistral, Cerebras, Fireworks, SambaNova, Hugging Face, Nebius, Hyperbolic, and
ModelScope. Entries use documented HTTPS endpoints; a provider still requires the
operator's key and a valid model. `/models` discovery is used where no safe default is
known. Anthropic uses its native Messages protocol; compatible providers use their
documented OpenAI-compatible chat/tool protocol.

The `/cloud` picker also offers **Custom endpoint**. It collects a short provider name,
an OpenAI-compatible `https://` base URL (normally ending in `/v1`), the served model
name, and an API key. The key is sent through the standard `Authorization: Bearer` header.
Plain HTTP and names reserved by built-in providers are rejected. Custom entries appear
in later provider pickers and use the same explicit `/switch` behavior.

## Environment overrides

| Variable | Default | Purpose |
|---|---|---|
| `KILOFRAME_OLLAMA_CONTEXT_TOKENS` | `8192` | context requested from Ollama |
| `KILOFRAME_DATA_DIR` | `/var/lib/kiloframe` | SQLite/data directory |
| `KILOFRAME_CONFIG_DIR` | `/etc/kiloframe` | configuration directory |
| `KILOFRAME_RUNTIME_DIR` | `/run/kiloframe` | PID/socket directory |
| `KILOFRAME_LOG_DIR` | `/var/log/kiloframe` | detached-daemon log directory |
| `KILOFRAME_INTEGRATIONS_DIR` | `/opt/kiloframe/integrations` | integration assets |
| `KILOFRAME_SIMPLE_TUI` | unset | use line-oriented TUI fallback when set |

Directory overrides are primarily useful for development/test isolation. A system install
expects its unit, wrapper, permissions, and directories to agree; changing only one path
can make the daemon and client use different sockets.

## Backup and restore

```bash
sudo cp -a /etc/kiloframe /etc/kiloframe.backup
sudo cp -a /var/lib/kiloframe /var/lib/kiloframe.backup
```

Stop the daemon before restoring a SQLite backup. Restore ownership to the service
account, then restart and run status/doctor. Never publish configuration backups: they may
contain provider or Telegram secrets.
