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
| `kiloframe localset default <name>` | Set active server |

`local select <model>` only selects a model that the active server has actually
reported as downloaded. It never claims that a remote model exists locally.

## Service Commands

| Command | Description |
|---------|-------------|
| `kiloframe start` | Start daemon |
| `kiloframe stop` | Stop daemon |
| `kiloframe restart` | Restart daemon |
| `kiloframe logs [-n LINES]` | Show service logs |

## Interactive slash commands

`/commands` is the complete in-app command list; `/help` adds short usage notes.
The full TUI also accepts direct forms:

```text
/local status
/local models
/local ps
/local pull <model>
/local select <model>
/local unload [model]
/localset list
/localset add <name> <http(s)://host:11434>
/localset remove <name>
/localset default <name>
/thinking off|on|low|medium|high
```

`/thinking` is enabled only when the active Ollama model advertises the `thinking`
capability. Models whose API advertises only generic thinking expose `on`/`off`; effort
levels are offered only for model families with a documented level control. Cloud
providers are not presented as supporting it without a verified provider-specific
control.

## CLI Help

```bash
kiloframe --help
kiloframe <command> --help
```
