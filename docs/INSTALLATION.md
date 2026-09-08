# KiloFrame Installation Guide

## System Requirements

- Linux (systemd recommended, but not required)
- Python 3.11+
- 4GB RAM minimum (8GB recommended for local models)
- Network access for model downloads

## Quick Install

```bash
# Method 1: One-line installer
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash

# Method 2: From source
git clone https://github.com/0v3r51ght/kiloframe
cd kiloframe
sudo ./scripts/install.sh
```

The one-line method downloads the current `main` archive, performs the real installation,
starts or restarts KiloFrame on systemd and non-systemd hosts, and prints live status
before returning. A failed download, installation, service action, or status check makes
the command return nonzero.

## Verify Installation

```bash
# Check version
kiloframe --version

# Check status
kiloframe status

# Run doctor
kiloframe doctor
```

## Configure Ollama

```bash
# Add your Ollama server
kiloframe localset add local http://127.0.0.1:11434

# Or remote server
kiloframe localset add remote http://ollama.internal.example:11434

# List servers
kiloframe localset list

# Set default
kiloframe localset default local
```

## Pull a Model

```bash
# List available models on server
kiloframe local models

# Pull a model
kiloframe local pull llama3.2

# Select model
kiloframe local select llama3.2
```

## Start KiloFrame

```bash
# Interactive TUI
kiloframe

# Or chat mode
kiloframe chat "Hello Kilo"
```

## Service Management (systemd)

```bash
# Start service
sudo systemctl start kiloframe

# Check status
sudo systemctl status kiloframe

# View logs
sudo journalctl -u kiloframe -f
```

### Containers and other non-systemd environments

The installer detects when `systemctl` exists but systemd is not actually running. It
still installs KiloFrame and creates the runtime directory, but cannot register a boot
service. Its CLI controls the detached daemon directly:

```bash
sudo kiloframe start
sudo kiloframe restart
sudo kiloframe stop
kiloframe logs
```

`kiloframe status` also prints an exact manual start command for use with another process
supervisor. Launch the TUI from an account permitted to use the KiloFrame socket. The
daemon remains usable without Ollama; configure a server later with
`kiloframe localset add <name> <url>`.

### Ollama memory tuning

KiloFrame sends a conservative 2048-token context limit to Ollama by default. This
avoids GPU out-of-memory failures on smaller local or remote servers where a model can
load but its default KV cache cannot. To raise it after confirming the server has enough
memory, set `KILOFRAME_OLLAMA_CONTEXT_TOKENS` in the daemon environment (for example
`4096`) and restart the daemon.

If Ollama's automatic GPU placement returns a CUDA out-of-memory error, KiloFrame makes
one bounded retry of the same selected model with Ollama's official `num_gpu: 0` request
option. The TUI reports that CPU recovery live; another failure is returned honestly.

## Uninstall

```bash
sudo ./scripts/uninstall.sh
```

## Troubleshooting

### Daemon won't start

```bash
# Check logs
sudo journalctl -u kiloframe -n 50

# Verify Ollama is running
curl http://127.0.0.1:11434/api/version

# Test connection
kiloframe local status
```

### Permission errors

```bash
# Fix permissions
sudo chown -R kiloframe:kiloframe /etc/kiloframe
sudo chown -R kiloframe:kiloframe /var/lib/kiloframe
sudo chown -R kiloframe:kiloframe /var/log/kiloframe
```
