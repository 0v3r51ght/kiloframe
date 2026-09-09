#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo: sudo ./scripts/install.sh" >&2
    exit 1
fi

# Self-bootstrap: when run via  curl ... | sudo bash  there is no checkout on disk,
# so clone the repo to /opt and re-exec this script from there. A normal ./scripts/
# run already has the tree and skips this.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd || true)"
if [[ -z "$ROOT" || ! -f "$ROOT/src/kiloframe/__init__.py" ]]; then
    if ! command -v git >/dev/null; then
        if command -v pacman >/dev/null; then
            pacman -Syu --needed --noconfirm git
        elif command -v apt-get >/dev/null; then
            apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y git
        elif command -v dnf >/dev/null; then
            dnf install -y git
        elif command -v zypper >/dev/null; then
            zypper --non-interactive install git
        elif command -v apk >/dev/null; then
            apk add git
        else
            echo "Git is required to bootstrap KiloFrame." >&2
            exit 1
        fi
    fi
    DEST="/opt/kiloframe"
    rm -rf "$DEST"
    git clone --depth 1 https://github.com/0v3r51ght/kiloframe "$DEST"
    exec bash "$DEST/scripts/install.sh" "$@"
fi

KILO_USER="${KILOFRAME_USER:-kiloframe}"
KILO_GROUP="$(id -gn "$KILO_USER" 2>/dev/null || echo "$KILO_USER")"

# A container can have a systemctl binary without systemd as PID 1.  Invoking it
# there makes a successful file installation look like a failed KiloFrame install.
has_systemd() {
    command -v systemctl >/dev/null 2>&1 && systemctl show-environment >/dev/null 2>&1
}

if command -v pacman >/dev/null; then
    pacman -Syu --needed --noconfirm python python-prompt_toolkit python-pygments curl sqlite ripgrep git nodejs npm
elif command -v apt-get >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip curl sqlite3 ripgrep git nodejs npm
elif command -v dnf >/dev/null; then
    dnf install -y python3 python3-pip curl sqlite ripgrep git nodejs npm
elif command -v zypper >/dev/null; then
    zypper --non-interactive install python3 python3-pip curl sqlite3 ripgrep git nodejs npm
elif command -v apk >/dev/null; then
    apk add python3 py3-pip curl sqlite ripgrep git nodejs npm
else
    echo "No supported package manager found; checking preinstalled dependencies." >&2
fi
PYTHON_BIN="$(command -v python3 || command -v python || true)"
[[ -n "$PYTHON_BIN" ]] || { echo "Python 3.11+ is required." >&2; exit 1; }
if ! "$PYTHON_BIN" -c "import prompt_toolkit, pygments" 2>/dev/null; then
    "$PYTHON_BIN" -m pip install --break-system-packages prompt_toolkit pygments 2>/dev/null \
        || "$PYTHON_BIN" -m pip install prompt_toolkit pygments \
        || echo "warning: prompt_toolkit/Pygments missing; code output will use the simple fallback UI" >&2
fi

if ! id "$KILO_USER" >/dev/null 2>&1; then
    if [[ "$KILO_USER" == "kiloframe" ]]; then
        echo "Creating service user: $KILO_USER"
        NOLOGIN="$(command -v nologin || echo /sbin/nologin)"
        if command -v useradd >/dev/null; then
            if getent group "$KILO_GROUP" >/dev/null 2>&1; then
                useradd --system --create-home --shell "$NOLOGIN" --gid "$KILO_GROUP" "$KILO_USER"
            else
                useradd --system --create-home --shell "$NOLOGIN" "$KILO_USER"
            fi
        elif command -v adduser >/dev/null; then
            if getent group "$KILO_GROUP" >/dev/null 2>&1; then
                adduser -S -D -h "/home/$KILO_USER" -s "$NOLOGIN" -G "$KILO_GROUP" "$KILO_USER"
            else
                adduser -S -D -h "/home/$KILO_USER" -s "$NOLOGIN" "$KILO_USER"
            fi
        else
            echo "No supported system-user creation tool found." >&2
            exit 1
        fi
    else
        echo "User does not exist: $KILO_USER" >&2
        exit 1
    fi
fi
KILO_GROUP="$(id -gn "$KILO_USER")"

# The daemon socket is intentionally group-restricted rather than world-writable.
# Let the administrator who invoked sudo use the installed CLI after a fresh login.
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]] && id "$SUDO_USER" >/dev/null 2>&1; then
    usermod -aG "$KILO_GROUP" "$SUDO_USER"
    echo "Added $SUDO_USER to group $KILO_GROUP (open a new login session after installation)."
fi

echo "Installing KiloFrame application..."
install -d -m 0755 /opt/kiloframe/app
# Ollama and provider configuration is changed by the daemon, which runs as the
# service account.  The directory (not just existing files) must therefore be
# writable for atomic replace() updates.
install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /etc/kiloframe
install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /var/lib/kiloframe /var/log/kiloframe
# Preserve existing runtime data when moving to the operator's non-root account.
if [[ -x /usr/local/bin/kiloframe ]]; then
    /usr/local/bin/kiloframe stop
fi
chown -R "$KILO_USER:$KILO_GROUP" /etc/kiloframe /var/lib/kiloframe /var/log/kiloframe
install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /run/kiloframe
cp -a "$ROOT/src" "$ROOT/pyproject.toml" /opt/kiloframe/app/
chown -R root:root /opt/kiloframe/app
find /opt/kiloframe/app -type d -exec chmod 0755 {} +
find /opt/kiloframe/app -type f -exec chmod 0644 {} +
install -m 0755 "$ROOT/scripts/kiloframe-wrapper" /usr/local/bin/kiloframe
install -d -m 0755 /usr/local/libexec
install -m 0755 "$ROOT/scripts/uninstall.sh" /usr/local/libexec/kiloframe-uninstall
sed -e "s/^User=.*/User=$KILO_USER/" -e "s/^Group=.*/Group=$KILO_GROUP/" \
    -e "s|^ExecStart=.*|ExecStart=$PYTHON_BIN -m kiloframe.daemon|" \
    "$ROOT/systemd/kiloframe.service" > /etc/systemd/system/kiloframe.service
chmod 0644 /etc/systemd/system/kiloframe.service
if [[ ! -f /etc/kiloframe/policy.json ]]; then
    install -m 0600 -o "$KILO_USER" -g "$KILO_GROUP" "$ROOT/config/policy.json" /etc/kiloframe/policy.json
fi
if [[ ! -f /etc/kiloframe/ollama.json ]]; then
    install -m 0600 -o "$KILO_USER" -g "$KILO_GROUP" /dev/null /etc/kiloframe/ollama.json
    printf '{"servers":{"local":{"url":"http://127.0.0.1:11434","enabled":true,"model":""}},"default":"local"}' > /etc/kiloframe/ollama.json
    chmod 0600 /etc/kiloframe/ollama.json
    chown "$KILO_USER":"$KILO_GROUP" /etc/kiloframe/ollama.json
fi
if [[ ! -f /etc/kiloframe/mcp.json ]]; then
    install -m 0600 -o "$KILO_USER" -g "$KILO_GROUP" "$ROOT/config/mcp.preconfigured.json" /etc/kiloframe/mcp.json
fi

# Older generated configs invoked Context7 through npx on every daemon start. The
# package is installed globally below, so migrate only that exact old default while
# preserving every operator-defined server and setting.
"$PYTHON_BIN" - /etc/kiloframe/mcp.json <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
context7 = (data.get("servers") or {}).get("context7") or {}
if context7.get("command") == "npx" and context7.get("args") == ["-y", "@upstash/context7-mcp@latest"]:
    context7["command"] = "context7-mcp"
    context7["args"] = []
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
PY
chmod 0600 /etc/kiloframe/mcp.json
chown "$KILO_USER":"$KILO_GROUP" /etc/kiloframe/mcp.json

# Preconfigure the requested first-party workflow integrations. Their source/command
# is installed here rather than being left as a documentation-only suggestion. A
# credentials-bound server remains disabled in mcp.json until its owner supplies a key.
install -d -m 0755 /opt/kiloframe/integrations
if [[ ! -d /opt/kiloframe/integrations/superpowers/.git ]]; then
    if ! git clone --depth 1 https://github.com/obra/superpowers.git /opt/kiloframe/integrations/superpowers; then
        echo "Superpowers is required but could not be downloaded; check GitHub connectivity and rerun the installer." >&2
        exit 1
    fi
fi
if command -v npm >/dev/null 2>&1; then
    if ! npm install -g @upstash/context7-mcp@latest @playwright/cli@latest exa-mcp-server; then
        echo "Context7, Playwright CLI, and Exa are required but could not be installed." >&2
        exit 1
    elif command -v playwright-cli >/dev/null 2>&1; then
        PLAYWRIGHT_WORKSPACE="/opt/kiloframe/integrations/playwright"
        install -d -m 0755 "$PLAYWRIGHT_WORKSPACE"
        (
            cd "$PLAYWRIGHT_WORKSPACE"
            # Playwright defaults plain --skills to a vendor-specific .claude path.
            # KiloFrame uses the official agent-neutral layout and imports it below.
            playwright-cli install --skills=agents
        ) || { echo "Playwright agent skills installation failed." >&2; exit 1; }
        PLAYWRIGHT_SKILL="$PLAYWRIGHT_WORKSPACE/.agents/skills/playwright-cli/SKILL.md"
        [[ -f "$PLAYWRIGHT_SKILL" ]] || {
            echo "Playwright reported success but KiloFrame's agent skill was not found: $PLAYWRIGHT_SKILL" >&2
            exit 1
        }
        chmod -R a+rX "$PLAYWRIGHT_WORKSPACE/.agents"
    fi
else
    echo "npm is required for Context7, Playwright CLI, and Exa." >&2
    exit 1
fi
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
    "$PYTHON_BIN" -m pip install --break-system-packages uv 2>/dev/null \
        || "$PYTHON_BIN" -m pip install uv
    UV_BIN="$(command -v uv || true)"
fi
if [[ -z "$UV_BIN" ]]; then
    echo "uv is required to install Serena but could not be installed." >&2
    exit 1
fi
install -d -m 0755 /opt/kiloframe/integrations/uv-tools /opt/kiloframe/integrations/bin
if ! UV_TOOL_DIR=/opt/kiloframe/integrations/uv-tools \
    UV_TOOL_BIN_DIR=/opt/kiloframe/integrations/bin \
    "$UV_BIN" tool install --python "$PYTHON_BIN" serena-agent; then
    echo "Serena is required but could not be installed." >&2
    exit 1
fi
SERENA_BIN="/opt/kiloframe/integrations/bin/serena"
if [[ ! -x "$SERENA_BIN" ]]; then
    echo "Serena installed but its launcher was not found: $SERENA_BIN" >&2
    exit 1
fi
ln -sf "$SERENA_BIN" /usr/local/bin/serena
if has_systemd; then
    systemctl daemon-reload
    systemctl enable kiloframe.service
    systemctl restart kiloframe.service
else
    # The daemon's socket path must be writable for an init-system-independent run.
    install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /run/kiloframe
    if command -v runuser >/dev/null 2>&1; then
        echo "systemd is not operational; starting the daemon as $KILO_USER."
        runuser -u "$KILO_USER" -- env PYTHONPATH=/opt/kiloframe/app/src \
            nohup "$PYTHON_BIN" -m kiloframe.daemon >>/var/log/kiloframe/daemon.log 2>&1 &
        sleep 1
    else
        echo "systemd is not operational; start the daemon with:"
        echo "  sudo -u $KILO_USER env PYTHONPATH=/opt/kiloframe/app/src $PYTHON_BIN -m kiloframe.daemon"
    fi
fi
# Installation is complete only when the daemon accepts connections.
"$PYTHON_BIN" - <<'PYREADY'
import socket
import time
for attempt in range(60):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(1)
            client.connect("/run/kiloframe/kiloframe.sock")
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("KiloFrame daemon did not start; inspect /var/log/kiloframe/daemon.log and kiloframe logs")
PYREADY
echo "KiloFrame installed. Run: kiloframe (then /local to add an Ollama server or /cloud for hosted models)"
