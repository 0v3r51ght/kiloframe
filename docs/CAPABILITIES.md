# KiloFrame capabilities

KiloFrame’s core features are the TUI/CLI, Ollama local or remote model route, tool
execution subject to policy, memory, and the daemon RPC service. They do not require a
cloud account or an Ollama server merely to install and launch.

## Preconfigured development and research integrations

The installer provisions Superpowers, Serena, Context7, and Playwright CLI. Their
entries are present in KiloFrame's native skills/MCP configuration on first launch.

| Integration | Purpose | Configuration condition |
|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | structured development skills | official skill files are imported into KiloFrame's skill memory |
| [Serena](https://github.com/oraios/serena) | semantic code navigation | MCP server starts for KiloFrame and activates the current project |
| [Context7](https://github.com/upstash/context7) | current technical documentation | MCP server is enabled |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) | browser/agent-skill workflows | CLI and its skills are installed |
| [GitHub MCP](https://github.com/github/github-mcp-server) | repository operations | optional authenticated server configured |
| [Exa MCP](https://github.com/exa-labs/exa-mcp-server) | research | preconfigured but disabled until an API key is supplied |
| [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) | crawling | optional service and credentials configured |

MCP servers are configured in `/etc/kiloframe/mcp.json`. Exa, GitHub MCP, and Firecrawl
are disabled by default because they need credentials. GitHub and Firecrawl credentials
are never required for ordinary local operation.
