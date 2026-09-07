# KiloFrame Troubleshooting

## Common Issues

### Daemon won't start

```bash
# On a systemd host
sudo journalctl -u kiloframe -n 50 --no-pager

# Verify Ollama is running
curl http://127.0.0.1:11434/api/version

# Test Ollama connection
kiloframe local status
```

### Permission denied errors

```bash
# Restore service ownership after inspecting an accidental change
sudo chown -R kiloframe:kiloframe /etc/kiloframe
sudo chown -R kiloframe:kiloframe /var/lib/kiloframe
sudo chown -R kiloframe:kiloframe /var/log/kiloframe

# Recreate the group-restricted runtime directory; do not make it world-writable
sudo install -d -m 0750 -o kiloframe -g kiloframe /run/kiloframe
```

### Model not found

```bash
# List available models
kiloframe local models

# Pull missing model
kiloframe local pull llama3.2

# Select model
kiloframe local select llama3.2
```

### Slow responses

- Check Ollama server resources
- Use smaller models (e.g., llama3.2:1b instead of 70b)
- Keep the default 2048-token context, or lower `KILOFRAME_OLLAMA_CONTEXT_TOKENS`
  in the daemon environment if the server reports GPU memory exhaustion
- Check network latency for remote servers

### TUI not displaying

```bash
# Force simple mode
KILOFRAME_SIMPLE_TUI=1 kiloframe

# Check terminal size
echo $COLUMNS $LINES
```

## Configuration Files

| File | Purpose |
|------|---------|
| `/etc/kiloframe/ollama.json` | Ollama server config |
| `/etc/kiloframe/providers.json` | Cloud providers |
| `/etc/kiloframe/policy.json` | Permission policy |
| `/etc/kiloframe/mcp.json` | MCP servers |

## Reset Configuration

```bash
# Backup current config
sudo cp -r /etc/kiloframe /etc/kiloframe.backup

# Reset only after taking the backup above
sudo rm -f /etc/kiloframe/ollama.json
sudo rm -f /etc/kiloframe/providers.json
# Run the installer again to recreate empty defaults
```

## Logs

```bash
# Service logs
sudo journalctl -u kiloframe -f

# In a non-systemd environment, inspect the supervisor or terminal that launched
# `python3 -m kiloframe.daemon`.
```
