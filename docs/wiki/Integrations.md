# Optional integrations

KiloFrame’s core TUI, Ollama route, and local tools do not require third-party account
credentials. Optional capabilities must be installed and configured before they are
available; their presence in documentation is not a connection claim.

| Capability | Intended role | Requirement |
|---|---|---|
| Superpowers | development workflow skills | installed skill source |
| Serena | code navigation through its server | Serena installed/configured for the project |
| Context7 | current library documentation | Context7 MCP command available |
| Playwright CLI | browser and agent-skill workflows | Playwright CLI and browser setup |
| GitHub MCP | authenticated repository operations | GitHub authentication and server configuration |
| Exa | enhanced research | Exa configuration/credentials |
| Firecrawl | crawling | Firecrawl configuration/credentials |

MCP configuration lives at `/etc/kiloframe/mcp.json`. Invalid or unavailable optional
servers are reported as unavailable and skipped; they do not prevent local KiloFrame
use. Never place tokens in a committed configuration file.
