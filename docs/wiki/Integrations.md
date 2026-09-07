# Integrations

The installer provisions Superpowers, Serena, Context7, and Playwright CLI. They
are not documentation-only suggestions: Superpowers is loaded into KiloFrame's memory
skill system; Serena and Context7 are enabled MCP entries; and Playwright's agent skills
are installed with its CLI.

| Capability | Intended role | Requirement |
|---|---|---|
| Superpowers | development workflow skills | official skills loaded into KiloFrame memory |
| Serena | code navigation through its server | enabled MCP server |
| Context7 | current library documentation | enabled MCP server |
| Playwright CLI | browser and agent-skill workflows | installed CLI and skills |
| Exa | enhanced research | preconfigured but disabled until an API key is supplied |
| GitHub MCP | authenticated repository operations | optional and disabled until authenticated |
| Firecrawl | crawling | optional and disabled until configured |

MCP configuration lives at `/etc/kiloframe/mcp.json`. Exa, GitHub MCP, and Firecrawl
are disabled by default because they require credentials. Never put a real token in the
repository.
