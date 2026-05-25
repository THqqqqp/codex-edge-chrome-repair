#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-"$HOME/.codex"}"
target="$codex_home/skills/codex-edge-chrome-repair"

mkdir -p "$codex_home/skills"
rm -rf "$target"
cp -R "$repo_root/skills/codex-edge-chrome-repair" "$target"

echo "Installed skill to $target"
echo "Restart Codex App to load the skill."
