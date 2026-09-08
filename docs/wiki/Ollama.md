# Ollama servers

KiloFrame does not manage GGUF files. Its local/private model route is an Ollama HTTP
server, configured locally or remotely.

```text
❯ /localset add workstation http://127.0.0.1:11434
❯ /localset add lab http://ollama.internal.example:11434
❯ /localset default lab
❯ /local status
❯ /local models
❯ /local select <downloaded model or displayed number>
❯ /local ps
```

`/local models` calls the active server’s model listing. `/local ps` calls its running
model listing. A remote model is not represented as downloaded on the KiloFrame host,
and selecting a model does not say it is loaded. `/local unload [model]` asks Ollama to
release the selected (or named) model using its supported keep-alive mechanism.

The default request context is 2048 tokens to reduce KV-cache GPU out-of-memory failures
on constrained servers. Raise `KILOFRAME_OLLAMA_CONTEXT_TOKENS` only after verifying
that the chosen server has enough memory, then restart the daemon.

If Ollama still returns a CUDA out-of-memory error during automatic placement, KiloFrame
reports the recovery in Kilo's live box and retries once with Ollama's documented
`num_gpu: 0` CPU setting. It never changes the configured server or model, loops retries,
or reports a second failure as success.
