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
    elif [[ -f /run/kiloframe/kiloframe.pid ]]; then
        echo "KiloFrame is running but its control command is missing; refusing unsafe removal." >&2
        exit 1
    fi
fi

echo "Removing KiloFrame user and groups..."
if [[ "$KILO_USER" == "kiloframe" ]] && id "$KILO_USER" &>/dev/null; then
    echo "Removing system user: $KILO_USER"
    if command -v userdel >/dev/null; then
        userdel -r "$KILO_USER" || true
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
