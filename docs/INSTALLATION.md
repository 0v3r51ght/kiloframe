# KiloFrame installation

## Requirements

- Linux with Python 3.11 or newer
- root access for the system installation
- network access during installation for operating-system packages and the required
  preconfigured integrations
- an Ollama endpoint only when using the Ollama route; installation and launch do not
  require Ollama to be reachable

The installer supports `pacman`, `apt-get`, `dnf`, `zypper`, and `apk`. Operational
systemd is used when available; containers and other non-systemd hosts use KiloFrame's
detached-daemon controls.

## One-line installation

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
```

This is a complete installer, not a launcher stub. It downloads a cache-busted archive
of current `main`, validates the archive structure, invokes the main installer, starts or
restarts the daemon, and prints live `kiloframe status`. A failed download, dependency,
integration, install, daemon-control, or status stage returns a nonzero exit code.

## Installation from a checkout

```bash
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
sudo kiloframe restart
kiloframe status
```

The installer is repeatable and preserves existing operator configuration. It:

1. installs required operating-system packages;
2. creates or reuses the `kiloframe` service account and group;
3. installs application code under `/opt/kiloframe/app`;
4. creates protected configuration, data, log, and runtime paths;
5. installs `/usr/local/bin/kiloframe`;
6. installs and enables the systemd unit when systemd is operational;
7. provisions Superpowers, Serena, Context7, and Playwright CLI;
8. writes the preconfigured MCP registry on a first install.

Exa is installed and its MCP entry is disabled until configured. GitHub MCP and
Firecrawl are optional disabled entries. Their credentials are not required for core
installation or operation.

## Installed layout

| Path | Purpose |
|---|---|
| `/usr/local/bin/kiloframe` | user command wrapper |
| `/opt/kiloframe/app` | installed Python application |
| `/opt/kiloframe/integrations` | Superpowers and Serena assets |
| `/etc/kiloframe` | Ollama, MCP, policy, provider, and Telegram configuration |
| `/var/lib/kiloframe` | SQLite conversations, facts, skills, and audit data |
| `/var/log/kiloframe` | detached-daemon log on non-systemd hosts |
| `/run/kiloframe` | PID file and group-restricted RPC socket |
| `/etc/systemd/system/kiloframe.service` | systemd unit |

The invoking sudo user is added to the KiloFrame group. Open a new login session after a
fresh installation so the shell receives that group before launching the TUI.

## First configuration

```bash
kiloframe localset add local http://127.0.0.1:11434
kiloframe localset list
kiloframe local status
kiloframe local models
kiloframe local select <name-from-models>
kiloframe
```

For a remote endpoint, use your own URL, for example
`http://ollama.internal.example:11434`. KiloFrame does not require a particular server
address and never embeds an operator's private endpoint in public documentation.

## Verify the installation

```bash
kiloframe --version
kiloframe status
kiloframe doctor
kiloframe local status
command -v context7-mcp
command -v playwright-cli
command -v serena
```

Then open a real terminal with `kiloframe`, run `/commands`, inspect `/local status`, and
send a normal prompt. A source-only unit test is not a substitute for this interactive
check.

`kiloframe status` may accurately report `UNHEALTHY` when the configured Ollama endpoint
is offline, or `MODEL REQUIRED` when no model is selected. Those states do not mean the
files failed to install.

## Service operation

On systemd:

```bash
sudo systemctl start kiloframe
sudo systemctl restart kiloframe
sudo systemctl stop kiloframe
sudo journalctl -u kiloframe -n 100 --no-pager
```

On a host without operational systemd:

```bash
sudo kiloframe start
sudo kiloframe restart
sudo kiloframe stop
kiloframe logs -n 100
```

`kiloframe status` detects the environment and prints an executable start or recovery
command. The one-line installer starts the detached daemon automatically on non-systemd
hosts.

## Optional SHA-256 verification

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh
sha256sum install-online.sh
# Compare the digest with the SHA-256 published for the intended release.
sudo bash install-online.sh
```

For stronger reproducibility, download a named release asset and its published checksum
instead of a moving branch before executing it.

## Uninstall

The uninstaller is provided by a checkout:

```bash
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/uninstall.sh
```

It stops KiloFrame, removes the service unit, application, configuration, runtime data,
logs, command wrapper, and the default service account. It does not remove system-wide
packages installed through the host package manager or global integration packages that
may be shared with other applications.

Back up `/etc/kiloframe` and `/var/lib/kiloframe` before uninstalling if configuration or
conversation history must be retained.

## Context and memory tuning

Ollama requests default to a conservative 2048-token context. Set
`KILOFRAME_OLLAMA_CONTEXT_TOKENS` in the daemon environment only after confirming the
server has enough memory, then restart KiloFrame. Conversation history and tool results
are independently compacted within their configured budgets; see
[Conversations and memory](wiki/Conversations-and-Memory.md).
