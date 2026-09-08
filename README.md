```text
██╗  ██╗██╗██╗      ██████╗ ███████╗██████╗  █████╗ ███╗   ███╗███████╗
██║ ██╔╝██║██║     ██╔═══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝
█████╔╝ ██║██║     ██║   ██║█████╗  ██████╔╝███████║██╔████╔██║█████╗
██╔═██╗ ██║██║     ██║   ██║██╔══╝  ██╔══██╗██╔══██║██║╚██╔╝██║██╔══╝
██║  ██╗██║███████╗╚██████╔╝██║     ██║  ██║██║  ██║██║ ╚═╝ ██║███████╗
╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝
  Developed by Citadel Research
```

KiloFrame is Kilo's terminal agent framework. It uses an Ollama server you configure
(on the same machine or a remote host) and can use separately configured cloud
providers. The full TUI keeps Kilo’s streamed work, tool activity, and answer in one
response box, with a sidebar for real route, model, task, context, and process state.
The `/cloud` picker supports built-in services and custom OpenAI-compatible HTTPS
endpoints; cloud routing remains explicit and requires the operator's credentials.

## Install

```bash
# Stable installer
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash

# Or install a checked-out tree
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
```

The one-line installer installs KiloFrame, starts or restarts its daemon, and prints the
resulting live status; it does not download a model. On a normal systemd host it enables
the daemon. In a container or another non-systemd environment,
`sudo kiloframe start|stop|restart` controls the detached daemon and status prints the
exact supervisor command; see [Installation](docs/INSTALLATION.md).

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
