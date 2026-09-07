# Integrations

The installer provisions Superpowers, Serena, Context7, Playwright CLI, and Exa. They
are not documentation-only suggestions: Superpowers is loaded into KiloFrame's memory
skill system; Serena and Context7 are enabled MCP entries; and Playwright's agent skills
are installed with its CLI.

| Capability | Intended role | Requirement |
|---|---|---|
| Superpowers | development workflow skills | official skills loaded into KiloFrame memory |
| Serena | code navigation through its server | enabled MCP server |
| Context7 | current library documentation | enabled MCP server |
| Playwright CLI | browser and agent-skill workflows | installed CLI and skills |
| Exa | enhanced research | enabled MCP server; needs `EXA_API_KEY` for requests |
| GitHub MCP | authenticated repository operations | optional and disabled until authenticated |
| Firecrawl | crawling | optional and disabled until configured |

MCP configuration lives at `/etc/kiloframe/mcp.json`. Set Exa's API key in that
service-owned file before starting the daemon; never put a real token in the repository.
