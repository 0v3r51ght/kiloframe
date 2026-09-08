```text
██╗  ██╗██╗██╗      ██████╗ ███████╗██████╗  █████╗ ███╗   ███╗███████╗
██║ ██╔╝██║██║     ██╔═══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝
█████╔╝ ██║██║     ██║   ██║█████╗  ██████╔╝███████║██╔████╔██║█████╗
██╔═██╗ ██║██║     ██║   ██║██╔══╝  ██╔══██╗██╔══██║██║╚██╔╝██║██╔══╝
██║  ██╗██║███████╗╚██████╔╝██║     ██║  ██║██║  ██║██║ ╚═╝ ██║███████╗
╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝
  Developed by Citadel Research
```

KiloFrame is Kilobyte (“Kilo”): a full-screen terminal agent framework developed by
Citadel Research. It runs Kilo through the AI brain you select—an Ollama server on this
machine or another host, or an explicitly configured cloud provider. It is not tied to
one model or one provider, and it never silently switches a request to a different route.

The TUI preserves Kilo's existing visual design: a dedicated input line, bordered output
screen, live task/tool activity, sidebar, selectable slash-command workflows, and a
clickable output scrollbar. Kilo's runtime directive is enforced for local models, cloud
models, tools, continuation turns, and specialist-agent handoffs.

## What KiloFrame contains

| Area | Included capability |
|---|---|
| Model routes | Local or remote Ollama; explicit cloud route and model switching |
| Providers | OpenRouter, OpenAI, Anthropic, Gemini, Groq, Together, DeepInfra, DeepSeek, Moonshot/Kimi, NVIDIA NIM, Venice, Z.AI, Scaleway, Cohere, Mistral, Cerebras, Fireworks, SambaNova, Hugging Face, Nebius, Hyperbolic, and ModelScope |
| Agent runtime | Persistent conversations, bounded context compaction, specialist selection, multi-step tool loops, failure recovery, and completion checks |
| Tools | Permission-gated filesystem, shell, web, memory, and MCP tools with structured results |
| MCP | Serena and Context7 enabled by default; GitHub, Exa, and Firecrawl present but disabled until configured |
| Operations | Rootless daemon service account, normal `kiloframe` client, installer, status, doctor, logs, restart, and uninstall |

## Start here

After installation, run `kiloframe`—not `sudo kiloframe`. The installer starts the
rootless daemon on systemd and non-systemd hosts. Use `kiloframe status` to confirm the
same daemon/socket is visible to the normal client.

Inside KiloFrame, use `/localset` for a guided Ollama URL setup, `/mcp` to see every MCP
server and discovered tool, and `/commands` for the canonical command list. Commands
with choices use arrow-key selection and Enter; text is requested only for values such as
an endpoint, model name, or API key.

## Install

```bash
# Stable installer
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash

# Or install a checked-out tree
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
```

The one-line installer installs KiloFrame, starts or restarts its rootless daemon, and
prints the resulting live status; it does not download a model. On a normal systemd host
it enables the daemon. On a non-systemd host it starts the same service account daemon
directly. `sudo kiloframe start|stop|restart` remains available for service control, but
normal use is simply `kiloframe`; see [Installation](docs/INSTALLATION.md).

## First run

```text
$ kiloframe
❯ /localset add local http://127.0.0.1:11434
❯ /local models
❯ /local select <downloaded-model-name>
❯ Hello, Kilo.
```

For a remote Ollama server, replace the URL with that server’s URL. KiloFrame queries
the selected server for downloaded and loaded models; it never labels a model as local,
loaded, or ready without that server reporting it.

`/help` gives the short in-TUI guide and `/commands` gives the complete command list.
Command completion is available as you type. The principal model commands are
`/local`, `/localset`, `/switch`, and `/thinking`.

## Status and recovery

```bash
kiloframe status
kiloframe doctor
kiloframe local status
```

`kiloframe status` reports the daemon PID/uptime, Ollama reachability, selected model,
and the exact start/recovery command for the host. It does not infer that a selected
model is loaded. Use `kiloframe local ps` for the server’s current runtime state.

## Documentation

- [Installation and uninstallation](docs/INSTALLATION.md)
- [CLI and slash-command reference](docs/COMMANDS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Comprehensive Wiki](https://github.com/0v3r51ght/kiloframe/wiki) and its
  [version-controlled source](docs/WIKI.md)

## Verify an installer download

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh
sha256sum install-online.sh
# Compare with the SHA-256 published for the release you intend to install.
sudo bash install-online.sh
```

## License

MIT — see [LICENSE](LICENSE).
