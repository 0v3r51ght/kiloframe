# KiloFrame Troubleshooting

## Common Issues

### Daemon won't start

```bash
# Check logs
sudo journalctl -u kiloframe -n 50
# or
tail -f /var/log/kiloframe/kiloframe.log

# Verify Ollama is running
curl http://127.0.0.1:11434/api/version

# Test Ollama connection
kiloframe local status
```

### Permission denied errors

```bash
# Fix ownership
sudo chown -R kiloframe:kiloframe /etc/kiloframe
sudo chown -R kiloframe:kiloframe /var/lib/kiloframe
sudo chown -R kiloframe:kiloframe /var/log/kiloframe

# Fix runtime directory
sudo chmod 777 /run/kiloframe
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
- Reduce context size in config
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

# Reset to defaults
sudo rm /etc/kiloframe/ollama.json
sudo rm /etc/kiloframe/providers.json
# Run installer again to recreate
```

## Logs

```bash
# Service logs
sudo journalctl -u kiloframe -f

# Application logs
tail -f /var/log/kiloframe/kiloframe.log

# Daemon output
cat /tmp/kiloframe-daemon.log
```
