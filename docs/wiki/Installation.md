# Installation

## Supported environment

KiloFrame targets Linux with Python 3.11 or newer and root access for system installation.
The installer recognizes `pacman`, `apt-get`, `dnf`, `zypper`, and `apk`. systemd is used
when operational; its mere presence in a container is not treated as a working init system.

Ollama is required only to use the Ollama model route. KiloFrame can be installed,
launched, inspected, and configured while an endpoint is offline.

## One-line installer

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
```

The script downloads a no-cache archive of current `main`, validates its structure, runs
the full installer, starts or restarts KiloFrame, and prints live status. Any failed stage
returns nonzero.

## Install from source

```bash
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
kiloframe status
```

The installer provisions the service account, command wrapper, application, config/data
paths, daemon unit/runtime directory, installed uninstaller, and required integrations. Existing configuration
and SQLite data are preserved on reinstall. It starts the rootless `kiloframe` daemon on
both systemd and non-systemd hosts. Open a new login session after installation if the
installer added your account to the `kiloframe` group; ordinary operation is then simply
`kiloframe`, without sudo.

## Installed paths

| Path | Contents |
|---|---|
| `/usr/local/bin/kiloframe` | command wrapper |
| `/opt/kiloframe/app` | installed Python package |
| `/opt/kiloframe/integrations` | Superpowers, Serena, Context7, and Playwright assets |
| `/etc/kiloframe` | protected configuration |
| `/var/lib/kiloframe` | persistent SQLite memory |
| `/var/log/kiloframe` | detached-daemon log |
| `/run/kiloframe` | PID file and RPC socket |

The invoking sudo user is added to the service group. Start a new login session after a
fresh installation before using the group-restricted socket.

## Installation verification

```bash
kiloframe --version
kiloframe status
kiloframe doctor
command -v context7-mcp
command -v playwright-cli
command -v serena
test -f /opt/kiloframe/integrations/playwright/.agents/skills/playwright-cli/SKILL.md
```

Then complete the real-terminal checks in [First run](First-Run). Unit tests alone do not
prove that layout, keyboard interaction, streaming, or selection workflows are usable.

## Upgrade or repair

Run the same one-line installer again. It replaces application code, updates required
integrations, migrates the known legacy Context7 invocation, restarts the daemon, and
retains operator config/data.

Before a significant upgrade, back up:

```bash
sudo cp -a /etc/kiloframe /etc/kiloframe.backup
sudo cp -a /var/lib/kiloframe /var/lib/kiloframe.backup
```

## Optional SHA verification

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh
sha256sum install-online.sh
# Compare with the checksum for the release you intend to install.
sudo bash install-online.sh
```

A named release and its published digest are more reproducible than a moving branch.

## Uninstall

Use the installed command from any directory:

```bash
sudo kiloframe uninstall
```

The script stops the daemon first, removes the unit, application, configuration, runtime
data, logs, wrapper, installed uninstaller, and default service account. It refuses an unsafe non-systemd removal
if a running PID is present but the control wrapper is missing.

The repository script `scripts/uninstall.sh` remains available for maintainer recovery when
the installed wrapper is unavailable.

Uninstall is destructive to `/etc/kiloframe` and `/var/lib/kiloframe`. Back them up first
if endpoints, keys, sessions, learned facts, skills, or audits must survive. Shared
operating-system/global packages are not removed.
