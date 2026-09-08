# Troubleshooting

Run these first:

```bash
kiloframe status
kiloframe doctor
kiloframe local status
kiloframe logs -n 100
```

## Stopped daemon

Use the exact start command printed by `kiloframe status`. On systemd inspect
`journalctl -u kiloframe`; without systemd use `sudo kiloframe restart` and
`kiloframe logs`.

## Socket permission denied

Start a new login session after installation so membership in the `kiloframe` group takes
effect. Confirm with `id`. The runtime directory/socket should be service-owned and
group-restricted; do not make it world-writable.

## Ollama unreachable

Check `kiloframe localset list`, then test the active endpoint from the KiloFrame host.
For local Ollama, `curl http://127.0.0.1:11434/api/version` is a direct check. For remote
Ollama, inspect its bind address, route, firewall, proxy, and TLS. Restarting KiloFrame
does not repair a remote service.

## Model selection fails

Run `kiloframe local models` and use the exact returned name. A model listed on another
endpoint is not available on the active one. Pull it to the active endpoint or switch
endpoints.

## Selected but not loaded

That is valid before first inference or after unload. Send a prompt, then run
`kiloframe local ps`. If it remains unloaded, inspect the inference error rather than
assuming selection failed.

## CUDA out of memory

KiloFrame reports and makes one CPU retry for an Ollama CUDA OOM. Use a smaller model,
unload other models, or lower a customized context. CPU fallback is expected to be slower;
a failed retry remains visible.

## TUI layout or command confusion

- widen the terminal to at least 88 columns;
- press `F2` for sidebar visibility;
- use `KILOFRAME_SIMPLE_TUI=1 kiloframe` for the fallback;
- enter `/local status` inside the TUI, but `kiloframe local status` in a shell;
- use `/commands` for the registered in-app list.

## Output does not stay where I scrolled

The output pane has a visible right-side scrollbar. Click above/below its thumb to step,
click or drag the thumb to move through the transcript, use the mouse wheel, or use
PageUp/PageDown. New output follows only while you are at the bottom; when you scroll
back, KiloFrame preserves your reading position.

## I cannot see MCP servers

Run `/mcp` in the TUI. It asks the daemon for the actual registry and shows both enabled
and disabled entries. A connected entry lists its discovered tool count; a failed entry
shows failure rather than pretending it is available. If a required server is not
connected, inspect `kiloframe logs -n 200`, then run `sudo kiloframe restart`.

## `/switch` says no cloud provider after reopening KiloFrame

Update to the current release. `/switch` now asks the daemon for its persisted default
provider when no provider is selected in the new TUI session, activates it immediately,
and switches back to Ollama on the next invocation. If it still reports no configured
provider, run `/cloud`, choose the provider, and complete its key/model setup first.

## I want to load a downloaded Ollama model before asking a question

Use `/local`, select **Load a model now**, and select a downloaded model. This sends a
keep-alive preload request to the active Ollama server and waits up to three minutes for
slow remote/CPU-only model loads. Use `/local ps` to verify it is running; use `/local
unload` when finished. A timeout is the Ollama server failing to load the model in that
window, not a false success from KiloFrame.

## Required integration unavailable

```bash
command -v context7-mcp
command -v serena
command -v playwright-cli
kiloframe logs -n 200
```

Rerun the installer if a required command is missing. A server that fails discovery is
logged/skipped and should not appear ready.

## Optional integration unavailable

Exa, GitHub MCP, and Firecrawl are disabled by default until credentials are configured.
That is expected. No API key is required for core KiloFrame or the preconfigured
non-key-bound integrations.

## Safe configuration repair

Back up `/etc/kiloframe` first. Prefer KiloFrame commands to JSON edits. Move aside only
the damaged file, rerun the installer, and restore required operator values carefully.
Do not delete `/var/lib/kiloframe` unless losing conversations and memory is intended.
