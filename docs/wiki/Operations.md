# Operations

## Daily health check

```bash
kiloframe status
kiloframe doctor
kiloframe local status
kiloframe local ps
```

Status includes daemon state/PID/uptime, real Ollama reachability, endpoint, selected
model, actual loaded state where available, host memory, stored facts/skills/sessions, and
the appropriate control/recovery command.

| State | Interpretation |
|---|---|
| `STOPPED` | daemon socket did not answer |
| `UNHEALTHY` | daemon active, Ollama endpoint unreachable |
| `MODEL REQUIRED` | endpoint reachable, no selected model |
| `MODEL SELECTED` | selection exists but model is not reported loaded |
| `READY` | daemon/endpoint/selection/load checks are satisfied |

## systemd hosts

```bash
sudo systemctl start kiloframe
sudo systemctl stop kiloframe
sudo systemctl restart kiloframe
sudo systemctl status kiloframe --no-pager
sudo journalctl -u kiloframe -n 100 --no-pager
sudo journalctl -u kiloframe -f
```

## Non-systemd hosts

```bash
sudo kiloframe start
sudo kiloframe stop
sudo kiloframe restart
kiloframe logs -n 100
```

The control command validates a stored PID against the process command line before
signalling it. The manual daemon command printed by status can be used with an external
supervisor.

## Upgrade

Back up configuration/data, run the public installer again, then verify:

```bash
curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | sudo bash
kiloframe status
kiloframe doctor
```

Open the real TUI and send a prompt after an upgrade. Existing configuration and SQLite
data are preserved. The installer refreshes application code and required integrations.

## Backup and restore

```bash
sudo cp -a /etc/kiloframe /etc/kiloframe.backup
sudo cp -a /var/lib/kiloframe /var/lib/kiloframe.backup
```

Stop the daemon before restoring SQLite. Restore the service account's ownership, restart,
and run doctor/status. Treat both backup paths as sensitive because they can contain
prompts, learned data, tokens, and provider keys.

## Logs and integration health

Daemon logs show MCP startup/discovery, Ollama failures, CPU recovery, and unexpected
exceptions. Context7/Serena should log successful startup and tool counts. Optional
credential-bound integrations may remain disabled without making core health fail.

## TUI operation

- Use at least 88 columns for the sidebar.
- Press `F2` to toggle the sidebar.
- `/cancel` stops the active request and clears queued work.
- `/quit` closes the client only.
- Model work can continue in Ollama according to its own lifecycle/keep-alive.
- Use `/local unload` when the selected model should be released.

See [Troubleshooting](Troubleshooting) for symptom-based recovery.
