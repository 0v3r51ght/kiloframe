# KiloFrame Commands Reference

## Main Commands

| Command | Description |
|---------|-------------|
| `kiloframe` | Start interactive TUI |
| `kiloframe chat "message"` | Send a message and stream response |
| `kiloframe status` | Show daemon and model status |
| `kiloframe version` | Show version information |
| `kiloframe doctor` | Run health checks |
| `kiloframe benchmark` | Test inference speed |

## Ollama Commands

| Command | Description |
|---------|-------------|
| `kiloframe local` | Show Ollama status |
| `kiloframe local status` | Server and model status |
| `kiloframe local models` | List downloaded models |
| `kiloframe local ps` | List running models |
| `kiloframe local pull <model>` | Download a model |
| `kiloframe local select <model>` | Set active model |
| `kiloframe local unload [model]` | Unload model from memory |

## Server Management

| Command | Description |
|---------|-------------|
| `kiloframe localset` | Show servers |
| `kiloframe localset add <name> <url>` | Add Ollama server |
| `kiloframe localset remove <name>` | Remove server |
| `kiloframe localset set-default <name>` | Set active server |
| `kiloframe localset set-model <server> <model>` | Set model per server |

## Service Commands

| Command | Description |
|---------|-------------|
| `kiloframe start` | Start daemon |
| `kiloframe stop` | Stop daemon |
| `kiloframe restart` | Restart daemon |
| `kiloframe logs [-n LINES]` | Show service logs |

## CLI Help

```bash
kiloframe --help
kiloframe <command> --help
```
