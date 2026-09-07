# KiloFrame Wiki

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation Guide](#installation-guide)
3. [User Guide](#user-guide)
4. [Operator Guide](#operator-guide)
5. [Architecture](#architecture)
6. [Configuration Reference](#configuration-reference)
7. [Troubleshooting](#troubleshooting)
8. [API Reference](#api-reference)

---

## Quick Start

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/citadelconsortium/kiloframe/main/scripts/install-online.sh | sudo bash

# Start
kiloframe

# Add your Ollama server
/localset add local http://127.0.0.1:11434

# Pull a model
/local pull llama3.2

# Select the model
/local select llama3.2

# Chat
> Hello Kilo, who are you?
```

---

## Installation Guide

### System Requirements

- Linux (systemd required)
- Python 3.11+
- 4GB RAM minimum (8GB recommended for local models)
- Network access for model downloads

### One-Line Installer

```bash
curl -fsSL https://raw.githubusercontent.com/citadelconsortium/kiloframe/main/scripts/install-online.sh | sudo bash
```

### Manual Installation

```bash
git clone https://github.com/citadelconsortium/kiloframe
cd kiloframe
sudo ./scripts/install.sh
```

### Verify Installation

```bash
kiloframe status
kiloframe version
kiloframe doctor
```

---

## User Guide

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/local` | Ollama route: status, models, pick, pull, unload |
| `/localset` | Configure Ollama servers (add/remove/switch) |
| `/switch` | Flip between Ollama and cloud providers |
| `/thinking` | Set thinking depth: off, low, medium, high, max |
| `/private` | Toggle Tor routing for web operations |
| `/cloud` | Switch to cloud provider mode |
| `/model` | Show current model information |
| `/agent` | Force a specialist agent (research, coding, security, systems) |
| `/new` | Start a new conversation session |
| `/clear` | Clear the current screen |
| `/quit` | Exit KiloFrame |

### Ollama Integration

#### Adding a Server

```
/localset add myserver http://ollama.internal.example:11434
```

#### Listing Models

```
/local models
```

#### Pulling a Model

```
/local pull llama3.2
/local pull qwen2.5:14b
```

#### Selecting a Model

```
/local select llama3.2
```

#### Unloading a Model

```
/local unload llama3.2
```

### Cloud Providers

KiloFrame supports 25+ cloud providers:

- OpenRouter
- OpenAI
- Anthropic (Claude)
- Groq
- DeepSeek
- Together AI
- Mistral
- xAI (Grok)
- Google Gemini
- And more...

Switch to cloud with `/cloud` and select your provider.

---

## Operator Guide

### Service Management

```bash
# Start/stop/restart
sudo systemctl start kiloframe
sudo systemctl stop kiloframe
sudo systemctl restart kiloframe

# Check status
sudo systemctl status kiloframe
kiloframe status

# View logs
sudo journalctl -u kiloframe -f
kiloframe logs
```

### Configuration Files

| File | Purpose |
|------|---------|
| `/etc/kiloframe/ollama.json` | Ollama server configuration |
| `/etc/kiloframe/providers.json` | Cloud provider credentials |
| `/etc/kiloframe/policy.json` | Permission policy |
| `/etc/kiloframe/mcp.json` | MCP server configuration |

### Uninstallation

```bash
sudo ./scripts/uninstall.sh
```

---

## Architecture

### Module Map

```
src/kiloframe/
├── __init__.py        # Package init, version
├── agent.py           # Orchestrator + specialist agents
├── cli.py             # CLI entry point, command routing
├── config.py          # Settings, paths, Ollama config
├── context.py         # Context window management
├── daemon.py          # systemd service, RPC server
├── doctor.py          # Health checks
├── errors.py          # Custom exceptions
├── mcp.py             # MCP server integration
├── memory.py          # Cross-session memory
├── net.py             # Network utilities
├── ollama.py          # Ollama client and config
├── profiles.py        # Agent profiles
├── prompt.py          # System prompt, directives
├── providers.py       # Cloud provider integrations
├── reference.py       # Offline how-to bank
├── render.py          # Output rendering
├── resources.py       # Resource detection
├── rpc.py             # Daemon RPC protocol
├── runtime.py         # Runtime abstraction
├── security.py        # Security checks
├── telegram.py        # Telegram bot bridge
├── telegram_render.py # Telegram output rendering
├── theme.py           # Color themes
├── tools.py           # Tool definitions
├── tui.py             # Simple TUI
└── tui_full.py        # Full TUI with sidebar
```

### Agent Loop

1. User input received
2. Context assembled from memory
3. Orchestrator selects specialist agent
4. Agent executes tools (shell, files, web, MCP)
5. Results streamed back to user
6. Memory updated with facts and skills

---

## Configuration Reference

### Ollama Configuration (`/etc/kiloframe/ollama.json`)

```json
{
  "servers": {
    "local": {
      "url": "http://127.0.0.1:11434",
      "enabled": true,
      "model": "llama3.2"
    },
    "remote": {
      "url": "http://ollama.internal.example:11434",
      "enabled": false,
      "model": ""
    }
  },
  "default": "local"
}
```

### Cloud Provider Configuration (`/etc/kiloframe/providers.json`)

```json
{
  "default": "openrouter",
  "providers": {
    "openrouter": {
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-v1-...",
      "model": "anthropic/claude-sonnet-4.5",
      "timeout": 120,
      "enabled": true
    }
  }
}
```

### Policy Configuration (`/etc/kiloframe/policy.json`)

```json
{
  "permissions": {
    "filesystem.write": "ask",
    "terminal.execute": "ask",
    "service.restart": "deny",
    "package.install": "ask"
  }
}
```

---

## Troubleshooting

### Daemon won't start

```bash
# Check logs
sudo journalctl -u kiloframe -n 50

# Verify Ollama is running
curl http://127.0.0.1:11434/api/version

# Test connection
kiloframe local status
```

### Model not found

```bash
# List available models
kiloframe local models

# Pull missing model
kiloframe local pull llama3.2
```

### Permission denied

```bash
# Check service user
sudo systemctl status kiloframe

# Verify config permissions
ls -la /etc/kiloframe/
```

### TUI not displaying

```bash
# Force simple TUI
KILOFRAME_SIMPLE_TUI=1 kiloframe

# Check terminal size
echo $COLUMNS $LINES
```

---

## API Reference

### RPC Protocol

KiloFrame exposes an RPC socket at `/run/kiloframe/kiloframe.sock`.

#### Status Request

```json
{"type": "request", "command": "status"}
```

Response:

```json
{
  "type": "result",
  "data": {
    "running": true,
    "healthy": true,
    "pid": 1234,
    "uptime_seconds": 3600,
    "model": "llama3.2",
    "server": "http://127.0.0.1:11434",
    "memory": {"sessions": 5, "facts": 42, "skills": 8}
  }
}
```

#### Chat Request

```json
{
  "type": "request",
  "command": "chat",
  "data": {
    "text": "What is the gateway?",
    "cwd": "/home/user"
  }
}
```

Streaming events:

```json
{"type": "token", "text": "The"}
{"type": "token", "text": " gateway"}
{"type": "tool", "name": "terminal", "args": {"cmd": "ip route"}}
{"type": "done", "text": " complete"}
```

---

## Capabilities

### Superpowers Integration

KiloFrame integrates with [Superpowers](https://github.com/obra/superpowers) skills for advanced workflows:

- brainstorming
- systematic-debugging
- test-driven-development
- writing-plans
- executing-plans

### Serena Integration

First-class [Serena](https://github.com/oraios/serena) support for codebase navigation:

- Symbol searching
- Reference finding
- Code navigation
- Project management

### Context7 Integration

Automatic [Context7](https://github.com/upstash/context7) documentation lookup when working with libraries and frameworks.

### Playwright Integration

Browser automation via [Playwright CLI](https://github.com/microsoft/playwright-cli) for web testing and automation.

### GitHub MCP

Optional [GitHub MCP](https://github.com/github/github-mcp-server) for repository operations when authenticated.

### Exa Research

Powered research via [Exa MCP](https://github.com/exa-labs/exa-mcp-server) for deeper investigations.

### Firecrawl

Web scraping via [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) when configured.
