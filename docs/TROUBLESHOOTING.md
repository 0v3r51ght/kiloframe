# KiloFrame troubleshooting

Start with evidence from the installed system:

```bash
kiloframe status
kiloframe doctor
kiloframe local status
kiloframe logs -n 100
```

## Understand status states

| State | Meaning | Next action |
|---|---|---|
| `STOPPED` | no daemon answered the RPC socket | run the printed start command |
| `UNHEALTHY` | daemon runs but active Ollama endpoint is unreachable | check endpoint/network; restart only after correcting it |
| `MODEL REQUIRED` | endpoint is reachable but no model is selected | list and select a downloaded model |
| `MODEL SELECTED` | model is selected but not reported loaded | send a prompt or inspect `local ps` |
| `READY` | daemon, endpoint, selection, and loaded-state checks succeeded | normal operation |

The TUI footer and sidebar use the same live state. They must not display a provider as
connected merely because it is configured.

## Daemon does not start

On systemd:

```bash
sudo systemctl status kiloframe --no-pager
sudo journalctl -u kiloframe -n 100 --no-pager
sudo systemctl restart kiloframe
```

Without systemd:

```bash
sudo kiloframe restart
kiloframe logs -n 100
```

If the wrapper is unavailable, `kiloframe status` normally prints the manual supervisor
command. Verify `/opt/kiloframe/app/src/kiloframe` exists before using it.

## Permission denied on the RPC socket

A fresh install adds the sudo-invoking user to the `kiloframe` group, but the current
login does not acquire that membership retroactively. Start a new login session, then
check:

```bash
id
ls -ld /run/kiloframe
ls -l /run/kiloframe/kiloframe.sock
```

Expected runtime access is group-restricted, not world-writable. If ownership was changed
accidentally:

```bash
sudo chown -R kiloframe:kiloframe /etc/kiloframe /var/lib/kiloframe /var/log/kiloframe
sudo install -d -m 0750 -o kiloframe -g kiloframe /run/kiloframe
sudo kiloframe restart
```

## Ollama endpoint unreachable

```bash
kiloframe localset list
kiloframe local status
curl http://127.0.0.1:11434/api/version
```

For a remote endpoint, test its configured URL from the KiloFrame host. Check routing,
firewall, TLS termination, and Ollama binding on that host. Restarting KiloFrame cannot
make an unavailable remote service reachable.

## No model or model not found

```bash
kiloframe local models
kiloframe local pull <model-name>
kiloframe local select <exact-name-from-models>
kiloframe local ps
```

KiloFrame intentionally refuses to select a name the active endpoint does not report as
downloaded. Switching endpoints also switches to that endpoint's own saved selection.

## Selected but not loaded

This is normal before first inference or after unload/expiry. Send a prompt and then run
`kiloframe local ps`. If inference fails, read the actual Ollama error in Kilo's response
box and in `kiloframe logs`.

## CUDA out of memory or slow inference

KiloFrame requests a 2048-token context by default. When Ollama reports a CUDA
out-of-memory error during automatic placement, KiloFrame reports one CPU fallback retry
live. It does not loop or report a second failure as success.

- use a model sized for the Ollama server;
- inspect server memory and other loaded models;
- unload unused models;
- lower `KILOFRAME_OLLAMA_CONTEXT_TOKENS` in the daemon environment if customized;
- expect CPU fallback to be substantially slower.

## TUI layout or rendering

- Use a terminal at least 88 columns wide for the sidebar.
- Press `F2` to hide or show the sidebar.
- Increase terminal height if menus cover conversation history.
- Use `KILOFRAME_SIMPLE_TUI=1 kiloframe` to run the line-oriented fallback.
- Verify `prompt_toolkit` and `pygments` with `kiloframe doctor`.

Run slash commands in the real TUI, including the leading `/`. Shell forms such as
`kiloframe local status` belong in a normal shell, not the prompt box.

## Serena or Context7 missing

```bash
command -v serena
command -v context7-mcp
kiloframe logs -n 200
```

Successful daemon startup logs the MCP server and discovered tool count. A missing or
failed MCP process is skipped and logged; it is not shown as ready. Rerun the installer
to repair required preconfigured integrations.

## Playwright CLI missing

```bash
command -v playwright-cli
playwright-cli --help
```

The installer runs `playwright-cli install --skills`. Browser runtime requirements may
still depend on the host and the workflow being used.

## Optional integration appears unavailable

Exa, GitHub MCP, and Firecrawl are disabled in the default MCP file. This is intentional
until their external credentials and service details are configured. Their absence must
not be diagnosed as a failed core installation.

## Telegram bot does not answer

With a configured token and an empty allow-list, the bridge deliberately enters safe pairing
mode. Send `/start` to the bot from the intended account; it replies with that account's chat
ID and the `sudo kiloframe telegram allow CHAT_ID` command. No ordinary chat or tool action is
accepted before that explicit authorization. Check `kiloframe logs -n 200` for the pairing-mode
startup line and `sudo kiloframe telegram status` for authorized chat IDs.

## Configuration damaged or invalid

Back up before changing anything:

```bash
sudo cp -a /etc/kiloframe /etc/kiloframe.backup
```

Prefer `/localset`, `/cloud`, and Telegram management commands over hand-editing JSON.
If repair requires removing a configuration file, move only that file aside and rerun the
installer; do not delete the whole data directory or SQLite database.

## Reinstall without losing conversations

The installer preserves existing `/etc/kiloframe` files and `/var/lib/kiloframe`. Running
the one-line installer again updates the application and required integrations. The
uninstaller, by contrast, removes both paths—back them up first if they must survive.
