# Installation

## Requirements

- Linux and Python 3.11 or newer
- `prompt_toolkit` and `pygments` for the full TUI (the installer attempts to install them)
- An Ollama server only if you want the Ollama route; it is not required to install or launch KiloFrame

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
```

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

On a host with operational systemd, the service is enabled. A container may have a
`systemctl` binary without systemd running; KiloFrame detects that case and does not
pretend a service was started. Start it under your process supervisor, or temporarily:

```bash
sudo -u kiloframe env PYTHONPATH=/opt/kiloframe/app/src python3 -m kiloframe.daemon
```

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
