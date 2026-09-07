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
    pacman -Syu --needed --noconfirm python python-prompt_toolkit python-pygments curl sqlite ripgrep
elif command -v apt-get >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip curl sqlite3 ripgrep
elif command -v dnf >/dev/null; then
    dnf install -y python3 python3-pip curl sqlite ripgrep
elif command -v zypper >/dev/null; then
    zypper --non-interactive install python3 python3-pip curl sqlite3 ripgrep
elif command -v apk >/dev/null; then
    apk add python3 py3-pip curl sqlite ripgrep
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
            useradd --system --create-home --shell "$NOLOGIN" "$KILO_USER"
        elif command -v adduser >/dev/null; then
            adduser -S -D -h "/home/$KILO_USER" -s "$NOLOGIN" "$KILO_USER"
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
cp -a "$ROOT/src" "$ROOT/pyproject.toml" /opt/kiloframe/app/
chown -R root:root /opt/kiloframe/app
find /opt/kiloframe/app -type d -exec chmod 0755 {} +
find /opt/kiloframe/app -type f -exec chmod 0644 {} +
install -m 0755 "$ROOT/scripts/kiloframe-wrapper" /usr/local/bin/kiloframe
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
if has_systemd; then
    systemctl daemon-reload
    systemctl enable kiloframe.service
else
    # The daemon's socket path must be writable for an init-system-independent run.
    install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /run/kiloframe
    echo "systemd is not operational; installation is complete. Start the daemon with:"
    echo "  sudo -u $KILO_USER env PYTHONPATH=/opt/kiloframe/app/src $PYTHON_BIN -m kiloframe.daemon"
fi
echo "KiloFrame installed. Run: kiloframe (then /local to add an Ollama server or /cloud for hosted models)"
