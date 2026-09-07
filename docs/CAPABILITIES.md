# KiloFrame capabilities

KiloFrame’s core features are the TUI/CLI, Ollama local or remote model route, tool
execution subject to policy, memory, and the daemon RPC service. They do not require a
cloud account or an Ollama server merely to install and launch.

## Optional development and research integrations

KiloFrame includes adapters or MCP configuration paths for the following projects. An
adapter is not an installation or an authenticated connection: the relevant command,
service, and credentials must exist on the host before KiloFrame can invoke it.

| Integration | Purpose | Configuration condition |
|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | structured development skills | skill source installed for the KiloFrame environment |
| [Serena](https://github.com/oraios/serena) | semantic code navigation | Serena installed and project server configured |
| [Context7](https://github.com/upstash/context7) | current technical documentation | Context7 MCP command available |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) | browser/agent-skill workflows | CLI and browser dependencies installed |
| [GitHub MCP](https://github.com/github/github-mcp-server) | repository operations | optional authenticated server configured |
| [Exa MCP](https://github.com/exa-labs/exa-mcp-server) | research | optional service configured |
| [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) | crawling | optional service and credentials configured |

MCP servers are configured in `/etc/kiloframe/mcp.json`. If an optional server is missing
or cannot start, KiloFrame reports and skips it rather than presenting it as available.
GitHub, Exa, and Firecrawl credentials are never required for ordinary local operation.
