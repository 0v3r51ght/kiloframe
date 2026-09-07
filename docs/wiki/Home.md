# KiloFrame

KiloFrame is a local-first terminal AI agent with a full-screen terminal interface and
a streaming CLI. Its local model route is a configurable [Ollama](Ollama) server. That
server may be on the same host or another machine; its downloads and loaded-model state
belong to that server.

The full TUI presents Sir’s input separately from Kilo’s response. Kilo’s progress,
tool calls, failures, and final response stay inside the same Kilo box. The sidebar is
grounded in live state: active route and model, queued task, work items, current context,
and models reported as running by Ollama.

## First run

```text
$ kiloframe
❯ /localset add local http://127.0.0.1:11434
❯ /local models
❯ /local select <model reported by /local models>
❯ Hello, Kilo.
```

Use `/help` for the short guide and `/commands` for the full command list. Input
completion appears while typing slash commands.

## Start here

- [Installation](Installation)
- [Commands](Commands)
- [Ollama local and remote servers](Ollama)
- [Operations and recovery](Operations)
- [Optional integrations](Integrations)
