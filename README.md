<p align="center"><img src="assets/kiloframe-mascot.svg" width="132" alt="Kilo, the KiloFrame mascot"></p>

```
██╗  ██╗██╗██╗      ██████╗ ███████╗██████╗  █████╗ ███╗   ███╗███████╗
██║ ██╔╝██║██║     ██╔═══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝
█████╔╝ ██║██║     ██║   ██║█████╗  ██████╔╝███████║██╔████╔██║█████╗
██╔═██╗ ██║██║     ██║   ██║██╔══╝  ██╔══██╗██╔══██║██║╚██╔╝██║██╔══╝
██║  ██╗██║███████╗╚██████╔╝██║     ██║  ██║██║  ██║██║ ╚═╝ ██║███████╗
╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝
Developed by Citadel Research
```

<p align="center"><b>A local-first terminal AI agent — Ollama or a cloud provider, never anything in between.</b></p>

<p align="center"><i>Orchestrator + specialist agents · real tools (shell, files, web, memory) · cross-session memory · a boxed, colored TUI · OpenCode-inspired slash commands · Kilo and Sir conversation boxes · and a left sidebar that tells you what Kilo is actually doing.</i></p>

---

## Why KiloFrame

- **It acts, it doesn't just talk.** Kilo is wired into the same real tools a human operator has (shell, files, web, memory, MCP). The model doesn't narrate; it runs the tool and reports what happened.
- **Local by default, with a hard public default.** KiloFrame's local/private route is a real Ollama server — local or remote. With no Ollama server it still runs through any of 25 OpenAI-compatible cloud providers you choose. Nothing about the box leaves the machine unless you say so.
- **Grounded.** The orchestrator commissions the right specialist per step (research, coding, security, systems, private), auto-recalls prior conversation, and refuses to record an announced action as a finished one.
- **OpenCode-style interactive surface, Kilo/Sir voice inside it.** The CLI mirrors OpenCode's command registry and layout, but Kilo still addresses you as **Sir** and shows every live tool call inside his own box. No two competing conversation styles.

## Install

```bash
# Production (stable)
sudo apt install -y curl
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
kiloframe

# From a working tree
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
kiloframe
```

The installer provisions Python, `prompt_toolkit`, `pygments`, the `kiloframe` system user, `/opt/kiloframe/app`, `/etc/kiloframe`, and the `kiloframe.service` systemd unit. It seeds an empty Ollama configuration so `/local` and `/localset` are immediately usable; it never downloads or bundles a model.

```text
# Optional: verify the installer
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh
sha256sum install-online.sh
# Compare against the SHA-256 advertised on the release page.
```

## First run

```text
kiloframe
> /localset add local http://127.0.0.1:11434
> /local pull llama3.2
> /local select llama3.2
> what is the gateway address on this host, Sir?
```

`/local`, `/localset`, `/switch`, `/thinking`, `/private`, `/cloud`, `/model`, `/agent`, `/help`, `/chats`, `/delete`, `/cancel`, `/new`, `/clear`, `/quit`.

## Documentation

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the module map and the agent loop, and the GitHub Wiki for the full user and operator guides.

## License

MIT — see [`LICENSE`](LICENSE).

— 0v3r51ght, Citadel Consortium

## Verify Installer Integrity

```bash
# Download installer
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh

# Check SHA-256
sha256sum install-online.sh
# Expected: <see release page for current hash>

# Run installer
sudo bash install-online.sh
```
