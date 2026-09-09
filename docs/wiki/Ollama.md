# Ollama local and remote servers

Ollama is KiloFrame's local/private model route. KiloFrame is an HTTP client; it does not
download raw GGUF files or start a separate model runner. The configured Ollama host owns
its model storage, GPU/CPU resources, loaded state, and lifetime.

## Endpoint management

```text
$ /localset add workstation http://127.0.0.1:11434
$ /localset add lab http://ollama.internal.example:11434
$ /localset list
$ /localset default lab
```

Names are local labels. URLs must use HTTP or HTTPS. Each named endpoint keeps its own
selected model because a model available on one server may not exist on another.

Equivalent shell commands are `kiloframe localset add`, `list`, `default`, and `remove`.

## Model lifecycle

```text
$ /local status
$ /local models
$ /local pull <model-name>
$ /local select <model-name-or-displayed-number>
$ Hello, Kilo.
$ /local ps
$ /local unload [model-name]
```

These are deliberately separate states:

1. **Downloaded** — `/api/tags` on the active server reports the model.
2. **Selected** — KiloFrame records that model for the named endpoint.
3. **Loaded** — `/api/ps` reports that Ollama currently has it in memory.

KiloFrame refuses selection when the active server does not report the requested name.
Selection does not force a load; the first inference normally does. Unload uses Ollama's
generate request with `keep_alive: 0` and then refreshes running state.

## API behavior

KiloFrame uses Ollama's version, tags, running-process, model-show, pull, chat, and generate
endpoints. It does not infer remote filesystem state. If the endpoint stops responding,
status becomes unreachable and the TUI reports it rather than displaying cached readiness.

## Thinking controls

`/thinking` first inspects the selected model. If the model advertises generic thinking,
KiloFrame offers on/off. Named effort levels are exposed only for a compatible model
family. The selected value is passed on Ollama chat requests; unsupported cloud thinking
is not advertised.

`/effort` is separate: it adjusts KiloFrame's response and tool-step budget regardless of
whether a model has a native thinking channel.

## Context and memory pressure

The default request context is 8192 tokens. Operators may set
`KILOFRAME_OLLAMA_CONTEXT_TOKENS` in the daemon environment and restart, but should verify
capacity first. KiloFrame passes the configured context and validated Ollama options per
request; it does not assume a fixed GPU layer count for a particular host.

If automatic placement returns an out-of-memory error, KiloFrame reports that in Kilo's live
box and retries the same endpoint/model once with a smaller batch, then once with CPU-only
placement when needed. It never loops, changes model, changes endpoint, or calls a cloud
provider. CPU inference may be much slower; a second failure remains a visible failure.

## Remote-server checklist

- The KiloFrame host can reach the URL and port.
- Ollama is bound to an interface reachable from that host.
- Any firewall or reverse proxy allows the documented API calls and streams.
- The model appears in `/local models` on the active endpoint.
- `/local ps` is used for loaded state; host-local process inspection is irrelevant.
- HTTP exposes prompts on the intervening network; use a trusted network or TLS proxy as
  appropriate for the deployment.

KiloFrame does not require any permanent endpoint. Add, remove, or switch named servers
as the environment changes.
