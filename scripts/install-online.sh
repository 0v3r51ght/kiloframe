#!/usr/bin/env bash
set -euo pipefail

# One-line installer entry point:
# curl -fsSL https://raw.githubusercontent.com/0v3r51ght/kiloframe/main/scripts/install-online.sh | bash
REPO_URL="${KILOFRAME_REPO_URL:-https://github.com/0v3r51ght/kiloframe}"
BRANCH="${KILOFRAME_BRANCH:-main}"
# Must match install.sh: the service account, not the person running the installer.
# Using the login user here left the service running as one account with its data
# owned by another.
OWNER="${KILOFRAME_USER:-kiloframe}"
WORK="$(mktemp -d -t kiloframe-install.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v tar >/dev/null || { echo "tar is required" >&2; exit 1; }
curl --fail --location --retry 5 --output "$WORK/source.tar.gz" \
  "$REPO_URL/archive/refs/heads/$BRANCH.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
ROOT="$(find "$WORK" -mindepth 1 -maxdepth 1 -type d -name '*-'"$BRANCH" -print -quit)"
[[ -n "$ROOT" ]] || { echo "downloaded repository has no source directory" >&2; exit 1; }
sudo KILOFRAME_USER="$OWNER" "$ROOT/scripts/install.sh"
if command -v systemctl >/dev/null && systemctl show-environment >/dev/null 2>&1; then
  sudo systemctl restart kiloframe.service
else
  echo "systemd is not operational; start the daemon with the manual command printed by the installer."
fi
echo "KiloFrame installed. Run: kiloframe (then /local to add an Ollama server or /cloud for hosted models)"
