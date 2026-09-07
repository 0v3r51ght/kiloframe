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
