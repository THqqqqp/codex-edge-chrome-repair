#!/usr/bin/env zsh
set -euo pipefail
setopt NULL_GLOB
export LC_ALL=C
export LANG=C

dry_run=0
skip_cache_sync=0
skip_edge_manifest=0
verbose=0
codex_home="${CODEX_HOME:-$HOME/.codex}"
source_plugin=""
cache_plugin=""

usage() {
  cat <<'EOF'
Usage: repair_codex_edge_chrome_macos.sh [options]

Repair Codex App's macOS Chrome plugin cache and Microsoft Edge native messaging setup.

Options:
  --dry-run              Print planned changes without writing files
  --codex-home PATH      Codex home directory, defaults to CODEX_HOME or ~/.codex
  --source-plugin PATH   Official bundled chrome plugin directory
  --cache-plugin PATH    Cached chrome plugin directory
  --skip-cache-sync      Do not repair the Codex plugin cache
  --skip-edge-manifest   Do not write the Edge native messaging manifest
  --verbose              Print extra diagnostics
  -h, --help             Show this help
EOF
}

info() { print -r -- "[INFO] $*"; }
ok() { print -r -- "[OK] $*"; }
warn() { print -r -- "[WARN] $*"; }
fail() { print -r -- "[ERROR] $*" >&2; exit 2; }
change() {
  if [[ "$dry_run" == "1" ]]; then
    print -r -- "[DRY-RUN] $*"
  else
    print -r -- "[CHANGE] $*"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --skip-cache-sync) skip_cache_sync=1 ;;
    --skip-edge-manifest) skip_edge_manifest=1 ;;
    --verbose) verbose=1 ;;
    --codex-home)
      [[ $# -ge 2 ]] || fail "--codex-home requires a path"
      codex_home="$2"
      shift
      ;;
    --source-plugin)
      [[ $# -ge 2 ]] || fail "--source-plugin requires a path"
      source_plugin="$2"
      shift
      ;;
    --cache-plugin)
      [[ $# -ge 2 ]] || fail "--cache-plugin requires a path"
      cache_plugin="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
  shift
done

[[ "$(uname -s)" == "Darwin" ]] || fail "This repair script is macOS-only."

realpath_portable() {
  local target="$1"
  if [[ -d "$target" ]]; then
    (cd "$target" && pwd -P)
  else
    local dir
    dir="$(dirname "$target")"
    local base
    base="$(basename "$target")"
    (cd "$dir" && print -r -- "$(pwd -P)/$base")
  fi
}

hash_file() {
  local file="$1"
  [[ -f "$file" ]] || {
    print -r -- "missing"
    return
  }
  shasum -a 256 "$file" | awk '{print $1}'
}

json_value() {
  local file="$1"
  local key="$2"
  sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$file" | head -n 1
}

defaults_value() {
  local plist="$1"
  local key="$2"
  defaults read "$plist" "$key" 2>/dev/null || true
}

require_path() {
  local path="$1"
  local label="$2"
  [[ -e "$path" ]] || fail "Missing $label: $path"
}

codex_home="$(realpath_portable "$codex_home")"

if [[ -z "$source_plugin" ]]; then
  source_plugin="$codex_home/.tmp/bundled-marketplaces/openai-bundled/plugins/chrome"
fi
source_plugin="$(realpath_portable "$source_plugin")"

if [[ -z "$cache_plugin" ]]; then
  cache_root="$codex_home/plugins/cache/openai-bundled/chrome"
  if [[ -e "$cache_root/latest" ]]; then
    cache_plugin="$(realpath_portable "$cache_root/latest")"
  else
    cache_plugin="$(find "$cache_root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1)"
    [[ -n "$cache_plugin" ]] || fail "Could not find chrome plugin cache under $cache_root"
    cache_plugin="$(realpath_portable "$cache_plugin")"
  fi
else
  cache_plugin="$(realpath_portable "$cache_plugin")"
  cache_root="$(dirname "$cache_plugin")"
fi

info "Codex home: $codex_home"
info "Bundled chrome plugin: $source_plugin"
info "Cached chrome plugin: $cache_plugin"

require_path "$source_plugin/.codex-plugin/plugin.json" "source plugin.json"
require_path "$source_plugin/assets" "source assets"
require_path "$source_plugin/scripts/browser-client.mjs" "source browser-client.mjs"
require_path "$source_plugin/scripts/extension-id.json" "source extension-id.json"
require_path "$source_plugin/skills/chrome/SKILL.md" "source chrome skill"

extension_id="$(json_value "$source_plugin/scripts/extension-id.json" extensionId)"
host_name="$(json_value "$source_plugin/scripts/extension-id.json" extensionHostName)"
[[ -n "$extension_id" ]] || fail "Could not read extensionId from $source_plugin/scripts/extension-id.json"
[[ -n "$host_name" ]] || host_name="com.openai.codexextension"

codex_app_version="$(defaults_value /Applications/Codex.app/Contents/Info CFBundleShortVersionString)"
edge_version="$(defaults_value "/Applications/Microsoft Edge.app/Contents/Info" CFBundleShortVersionString)"
codex_cli_version="$(/Applications/Codex.app/Contents/Resources/codex --version 2>/dev/null || true)"
plugin_version="$(json_value "$source_plugin/.codex-plugin/plugin.json" version)"
macos_version="$(sw_vers -productVersion 2>/dev/null || true)"

info "Environment versions:"
info "  macOS: ${macos_version:-unknown}"
info "  CPU: $(uname -m)"
info "  Codex App: ${codex_app_version:-unknown}"
info "  Codex CLI: ${codex_cli_version:-unknown}"
info "  Microsoft Edge: ${edge_version:-unknown}"
info "  Chrome plugin cache: chrome@openai-bundled ${plugin_version:-unknown}"
info "  Codex extension ID: ${extension_id:-unknown}"

if [[ "$skip_cache_sync" != "1" ]]; then
  source_hash="$(hash_file "$source_plugin/scripts/browser-client.mjs")"
  cache_hash="$(hash_file "$cache_plugin/scripts/browser-client.mjs")"
  info "Source browser-client hash: $source_hash"
  info "Cache browser-client hash: $cache_hash"

  needs_sync=0
  [[ "$source_hash" == "$cache_hash" ]] || needs_sync=1
  [[ -e "$cache_plugin/.codex-plugin/plugin.json" ]] || needs_sync=1
  [[ -e "$cache_plugin/assets" ]] || needs_sync=1
  [[ -e "$cache_plugin/docs" ]] || needs_sync=1
  [[ -e "$cache_plugin/extension-host" ]] || needs_sync=1
  [[ -e "$cache_plugin/scripts" ]] || needs_sync=1
  [[ -e "$cache_plugin/skills" ]] || needs_sync=1

  if [[ "$needs_sync" == "1" ]]; then
    backup="$cache_plugin.backup.$(date +%Y%m%d%H%M%S)"
    change "Back up $cache_plugin to $backup"
    change "Sync official bundled plugin into cache"
    if [[ "$dry_run" != "1" ]]; then
      cp -a "$cache_plugin" "$backup"
      rsync -a --delete "$source_plugin/" "$cache_plugin/"
    fi
  else
    ok "Cache browser-client and required directories already match bundled plugin."
  fi
else
  info "Skipped cache sync."
fi

if [[ "$skip_edge_manifest" != "1" ]]; then
  arch="$(uname -m)"
  case "$arch" in
    arm64) host_arch="arm64" ;;
    x86_64) host_arch="x64" ;;
    *) fail "Unsupported CPU architecture: $arch" ;;
  esac

  if [[ -e "$codex_home/plugins/cache/openai-bundled/chrome/latest" ]]; then
    host_root="$codex_home/plugins/cache/openai-bundled/chrome/latest"
  else
    host_root="$cache_plugin"
  fi

  host_binary="$host_root/extension-host/macos/$host_arch/extension-host"
  require_path "$host_binary" "extension host binary"

  manifest_dir="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
  manifest_path="$manifest_dir/$host_name.json"
  manifest_content='{"name":"'"$host_name"'","description":"Codex chrome native messaging host","type":"stdio","path":"'"$host_binary"'","allowed_origins":["chrome-extension://'"$extension_id"'/"]}'

  if [[ -f "$manifest_path" ]] && [[ "$(cat "$manifest_path")" == "$manifest_content" ]]; then
    ok "Native messaging manifest already correct: $manifest_path"
  else
    change "Write Edge native messaging manifest: $manifest_path"
    if [[ "$dry_run" != "1" ]]; then
      mkdir -p "$manifest_dir"
      print -r -- "$manifest_content" > "$manifest_path"
    fi
  fi
else
  info "Skipped Edge native messaging manifest repair."
fi

edge_user_data="$HOME/Library/Application Support/Microsoft Edge"
info "Edge user data directory: $edge_user_data"
found_extension=0
if [[ -d "$edge_user_data" ]]; then
  for profile in "$edge_user_data"/Default "$edge_user_data"/Profile\ *; do
    [[ -d "$profile" ]] || continue
    extension_dir="$profile/Extensions/$extension_id"
    if [[ -d "$extension_dir" ]]; then
      found_extension=1
      ok "Codex extension exists in Edge profile: $profile"
      if [[ "$verbose" == "1" ]]; then
        find "$extension_dir" -mindepth 1 -maxdepth 1 -type d -print
      fi
    fi
  done
fi

if [[ "$found_extension" != "1" ]]; then
  warn "Codex extension was not found in Edge profiles. Install it in Edge first."
fi

if [[ "$dry_run" == "1" ]]; then
  info "Dry run complete. Re-run without --dry-run to apply changes."
else
  ok "Repair complete. Restart Codex App and reload the Codex extension in Edge."
fi
