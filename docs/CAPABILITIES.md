# KiloFrame capabilities

KiloFrame’s core features are the TUI/CLI, Ollama local or remote model route, tool
execution subject to policy, memory, and the daemon RPC service. They do not require a
cloud account or an Ollama server merely to install and launch.

## Assistant identity and address contract

The complete Kilo Core Directive is the first system instruction on local Ollama and
every cloud-provider request. Visible TUI and Telegram replies are also normalised at
the framework boundary: the assistant identifies as Kilo, attributes development to
Citadel Research, starts with `Sir, `, and ends with `, Sir.`. Identity enforcement is
applied to the guarded combined stream, so provider names cannot escape merely because
the provider split a phrase such as `I am Claude` across multiple response chunks.

Ordinary factual discussion of model and provider names is preserved; the normaliser
only rewrites self-identification and self-creator claims.

## Preconfigured development and research integrations

The installer provisions Superpowers, Serena, Context7, and Playwright CLI. Their
entries are present in KiloFrame's native skills/MCP configuration on first launch.

| Integration | Purpose | Configuration condition |
|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | structured development skills | official skill files are imported into KiloFrame's skill memory |
| [Serena](https://github.com/oraios/serena) | semantic code navigation | MCP server starts for KiloFrame and activates the current project |
| [Context7](https://github.com/upstash/context7) | current technical documentation | MCP server is enabled |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) | browser/agent-skill workflows | CLI plus agent-neutral official skill imported into KiloFrame memory |
| [GitHub MCP](https://github.com/github/github-mcp-server) | repository operations | optional authenticated server configured |
| [Exa MCP](https://github.com/exa-labs/exa-mcp-server) | research | preconfigured but disabled until an API key is supplied |
| [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) | crawling | optional service and credentials configured |

MCP servers are configured in `/etc/kiloframe/mcp.json`. Exa, GitHub MCP, and Firecrawl
are disabled by default because they need credentials. GitHub and Firecrawl credentials
are never required for ordinary local operation.
