# Operations and recovery

```bash
kiloframe status
kiloframe local status
kiloframe local ps
kiloframe doctor
```

The status command reports the daemon PID and uptime, memory profile, selected server,
actual reachability, and selected model. It deliberately does not equate a selection
with a loaded runtime model: use `kiloframe local ps` for that.

On a normal systemd host:

```bash
sudo systemctl restart kiloframe
sudo journalctl -u kiloframe -n 100 --no-pager
```

On a non-systemd host, run the command printed by `kiloframe status` under a supervisor,
or use the manual command in [Installation](Installation). If the server is unreachable,
check the configured URL and the network path before restarting KiloFrame; restarting
the client cannot make a remote Ollama server available.

For TUI layout problems, make the terminal at least 88 columns wide to show the sidebar,
or use `F2` to toggle it. `KILOFRAME_SIMPLE_TUI=1 kiloframe` selects the line-oriented
fallback interface.
