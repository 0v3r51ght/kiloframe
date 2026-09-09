# First run

This walkthrough verifies the installed application from a normal user's terminal.

## 1. Confirm the daemon

```bash
kiloframe status
kiloframe doctor
```

`STOPPED` means use the start command printed by status. `UNHEALTHY` with an unreachable
Ollama endpoint is an accurate runtime state, not proof that installation failed.

## 2. Configure an Ollama endpoint

For Ollama on the KiloFrame host:

```bash
kiloframe localset add local http://127.0.0.1:11434
kiloframe localset default local
```

For a remote host, substitute your own address, such as
`http://ollama.internal.example:11434`. KiloFrame stores a selected model separately for
each named endpoint.

```bash
kiloframe localset list
kiloframe local status
```

## 3. Select a server-reported model

```bash
kiloframe local models
kiloframe local select <exact-model-name>
```

If the server has none, pull one appropriate for its resources:

```bash
kiloframe local pull <model-name>
```

Selection does not mean loaded. Before first inference, `kiloframe status` may say
`MODEL SELECTED` and `loaded NO — loads on first request`.

## 4. Exercise the real TUI

```bash
kiloframe
```

Check all of the following as a human user:

1. The KILOFRAME ASCII wordmark and left-aligned Citadel Research credit are intact.
2. The footer says whether Ollama is actually reachable.
3. `/commands` renders a complete in-app command list.
4. `/local status`, `/local models`, and `/local ps` show live server responses.
5. `/local select 1` works after the numbered model list is shown.
6. A normal prompt streams a response inside Kilo's box.
7. Thinking/tool/recovery activity remains in that same box when it occurs.
8. The sidebar reflects the route, model, context, sessions, and loaded models.
9. Resize the terminal, press `F2` to hide the sidebar, then press `F2` again: Sir and
   Kilo boxes should reflow with continuous side rails and no blank row between a request
   and its reply.
10. `/new`, `/chats`, and `/delete` behave as documented.
11. `/quit` exits without stopping the daemon.

## 5. Confirm loaded state and restart

```bash
kiloframe local ps
kiloframe status
sudo kiloframe restart
kiloframe status
kiloframe
```

On systemd hosts you may use `sudo systemctl restart kiloframe`. The second launch checks
that configuration and conversations persist across daemon and TUI restarts.
