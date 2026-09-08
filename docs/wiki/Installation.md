# Installation

## Requirements

- Linux and Python 3.11 or newer
- `prompt_toolkit` and `pygments` for the full TUI (the installer attempts to install them)
- An Ollama server only if you want the Ollama route; it is not required to install or launch KiloFrame

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
```

This downloads `main`, installs it, starts or restarts the daemon on systemd and
non-systemd hosts, and prints live status. Any failed stage returns a nonzero exit code.

Or install a checkout:

```bash
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
```

The installer creates the `kiloframe` service account, installs the application beneath
`/opt/kiloframe`, writes configuration in `/etc/kiloframe`, and installs the `kiloframe`
command. It adds the sudo-invoking user to the `kiloframe` group; start a new login
session before using the group-restricted daemon socket.

On a host with operational systemd, the service is enabled. The one-line installer also
starts the detached daemon on a non-systemd host. When running `scripts/install.sh`
directly in a container or another non-systemd environment, use the built-in controls:

```bash
sudo kiloframe start
sudo kiloframe restart
sudo kiloframe stop
```

`kiloframe status` prints the exact manual daemon command when an external supervisor is
preferred.

## Verify and uninstall

```bash
kiloframe status
kiloframe doctor
sudo ./scripts/uninstall.sh
```

Download verification is optional:

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh -o install-online.sh
sha256sum install-online.sh
# Compare with the SHA-256 published for the release.
sudo bash install-online.sh
```
