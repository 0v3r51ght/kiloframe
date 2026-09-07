# Commands

## CLI

```text
kiloframe                         open the full TUI
kiloframe chat "message"          stream one answer
kiloframe status                  daemon, Ollama, model, runtime and recovery information
kiloframe doctor                  dependency and health checks
kiloframe local status|models|ps  inspect the active Ollama server
kiloframe local pull <model>      pull onto the active server
kiloframe local select <model>    select a model the active server reports downloaded
kiloframe local unload [model]    request unload on the active server
kiloframe localset list           list configured servers
kiloframe localset add <name> <url>
kiloframe localset default <name>
kiloframe localset remove <name>
```

`kiloframe status` distinguishes a stopped daemon, an unreachable server, no selected
model, and a selected-but-not-loaded model. It prints a systemd or non-systemd recovery
command appropriate for the host.

## Full TUI slash commands

```text
/help                 short in-app guide
/commands             full command reference
/local                 Ollama menu
/local status|models|ps|pull|select|unload
/localset list|add|remove|default
/switch               select Ollama or a configured cloud route
/thinking off|on|low|medium|high
/effort high|medium|low
/agent <name>|off
/private on|off|rotate
/cloud, /model
/chats, /kilochats, /chat, /delete
/cancel, /new, /clear, /quit
```

`/thinking` is capability-gated. A model with generic Ollama thinking gets `on`/`off`;
levels are only offered for model families with an advertised level control. KiloFrame
does not claim cloud thinking controls it cannot verify.
