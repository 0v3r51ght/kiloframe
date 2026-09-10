#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo: sudo ./scripts/uninstall.sh" >&2
    exit 1
fi

KILO_USER="${KILOFRAME_USER:-kiloframe}"
KILO_GROUP="$(id -gn "$KILO_USER" 2>/dev/null || echo "$KILO_USER")"

has_systemd() {
    command -v systemctl >/dev/null 2>&1 && systemctl show-environment >/dev/null 2>&1
}

wait_for_detached_daemon() {
    # `kiloframe stop` removes the socket promptly, but the process may still be
    # unwinding.  Do not remove its service account while it is alive: userdel then
    # fails silently and a reinstall can inherit a stale daemon.
    command -v pgrep >/dev/null 2>&1 || return 0
    for _ in $(seq 1 20); do
        if ! pgrep -u "$KILO_USER" -f "kiloframe.daemon" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.1
    done
    echo "Stopping remaining detached KiloFrame daemon..."
    pkill -TERM -u "$KILO_USER" -f "kiloframe.daemon" || true
    for _ in $(seq 1 20); do
        if ! pgrep -u "$KILO_USER" -f "kiloframe.daemon" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.1
    done
    echo "KiloFrame daemon did not stop; refusing unsafe removal." >&2
    return 1
}

echo "Stopping and disabling KiloFrame service..."
if has_systemd; then
    systemctl stop kiloframe.service || true
    systemctl disable kiloframe.service || true
    rm -f /etc/systemd/system/kiloframe.service
    systemctl daemon-reload
else
    if [[ -x /usr/local/bin/kiloframe ]]; then
        echo "Stopping the detached KiloFrame daemon..."
        /usr/local/bin/kiloframe stop
        wait_for_detached_daemon
    elif [[ -f /run/kiloframe/kiloframe.pid ]]; then
        echo "KiloFrame is running but its control command is missing; refusing unsafe removal." >&2
        exit 1
    fi
fi

echo "Removing KiloFrame user and groups..."
if [[ "$KILO_USER" == "kiloframe" ]] && id "$KILO_USER" &>/dev/null; then
    echo "Removing system user: $KILO_USER"
    if command -v userdel >/dev/null; then
        userdel -r "$KILO_USER"
    elif command -v deluser >/dev/null; then
        deluser --remove-home "$KILO_USER" || true
    fi
else
    echo "Skipping removal of user $KILO_USER (not the default service account or not found)."
fi

echo "Removing KiloFrame directories..."
rm -rf /opt/kiloframe
rm -rf /etc/kiloframe
rm -rf /var/lib/kiloframe
rm -rf /var/log/kiloframe

echo "Removing kiloframe command from PATH..."
rm -f /usr/local/bin/kiloframe
rm -f /usr/local/libexec/kiloframe-uninstall

echo "KiloFrame has been uninstalled."
