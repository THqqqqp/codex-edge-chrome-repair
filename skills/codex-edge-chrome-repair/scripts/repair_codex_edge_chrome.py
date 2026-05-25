#!/usr/bin/env python3
"""Repair Codex Chrome plugin cache and Microsoft Edge native messaging setup."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


HOST_PLATFORM = {
    "Darwin": "macos",
    "Windows": "windows",
    "Linux": "linux",
}

EDGE_USER_DATA = {
    "Darwin": ("Library", "Application Support", "Microsoft Edge"),
    "Linux": (".config", "microsoft-edge"),
}

EXTENSION_ID_FILE = Path("scripts") / "extension-id.json"
HOST_NAME_DEFAULT = "com.openai.codexextension"
EDGE_REGISTRY_PREFIX = r"HKCU\Software\Microsoft\Edge\NativeMessagingHosts"


class RepairError(RuntimeError):
    pass


class Reporter:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.changed = False
        self.warnings: list[str] = []

    def info(self, message: str) -> None:
        print(f"[INFO] {message}")

    def ok(self, message: str) -> None:
        print(f"[OK] {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def change(self, message: str) -> None:
        self.changed = True
        prefix = "[DRY-RUN]" if self.dry_run else "[CHANGE]"
        print(f"{prefix} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair Codex Chrome plugin cache and Edge native messaging.",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
        help="Codex home directory. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--source-plugin",
        type=Path,
        help="Official bundled chrome plugin directory to sync from.",
    )
    parser.add_argument(
        "--cache-plugin",
        type=Path,
        help="Cached chrome plugin directory to repair.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report planned changes.",
    )
    parser.add_argument(
        "--skip-cache-sync",
        action="store_true",
        help="Do not repair the Codex plugin cache.",
    )
    parser.add_argument(
        "--skip-edge-manifest",
        action="store_true",
        help="Do not write Microsoft Edge native messaging host configuration.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra diagnostic details.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepairError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RepairError(f"Invalid JSON file: {path}: {exc}") from exc


def read_json_optional(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def command_output(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return None
    output = result.stdout.strip()
    return output or None


def defaults_value(plist_path: Path, key: str) -> str | None:
    return command_output(["defaults", "read", str(plist_path), key])


def sw_vers_value(key: str) -> str | None:
    return command_output(["sw_vers", f"-{key}"])


def report_environment_versions(cache_plugin: Path, reporter: Reporter) -> None:
    plugin_json = read_json_optional(cache_plugin / ".codex-plugin" / "plugin.json")
    extension_config = read_json_optional(cache_plugin / EXTENSION_ID_FILE)
    codex_app_version = defaults_value(
        Path("/Applications/Codex.app/Contents/Info"),
        "CFBundleShortVersionString",
    )
    edge_version = defaults_value(
        Path("/Applications/Microsoft Edge.app/Contents/Info"),
        "CFBundleShortVersionString",
    )
    codex_cli_version = command_output(
        ["/Applications/Codex.app/Contents/Resources/codex", "--version"],
    )

    reporter.info("Environment versions:")
    reporter.info(f"  macOS: {sw_vers_value('productVersion') or 'unknown'}")
    reporter.info(f"  CPU: {platform.machine() or 'unknown'}")
    reporter.info(f"  Codex App: {codex_app_version or 'unknown'}")
    reporter.info(f"  Codex CLI: {codex_cli_version or 'unknown'}")
    reporter.info(f"  Microsoft Edge: {edge_version or 'unknown'}")
    reporter.info(
        f"  Chrome plugin cache: chrome@openai-bundled {plugin_json.get('version') or 'unknown'}",
    )
    reporter.info(
        f"  Codex extension ID: {extension_config.get('extensionId') or 'unknown'}",
    )


def resolve_source_plugin(codex_home: Path, override: Path | None) -> Path:
    if override:
        return override.expanduser().resolve()
    return (
        codex_home
        / ".tmp"
        / "bundled-marketplaces"
        / "openai-bundled"
        / "plugins"
        / "chrome"
    ).resolve()


def resolve_cache_plugin(codex_home: Path, override: Path | None) -> Path:
    if override:
        return override.expanduser().resolve()

    chrome_cache = codex_home / "plugins" / "cache" / "openai-bundled" / "chrome"
    latest = chrome_cache / "latest"
    if latest.exists():
        return latest.resolve()

    versions = [
        entry
        for entry in chrome_cache.iterdir()
        if entry.is_dir() and re.match(r"^\d+\.\d+\.\d+$", entry.name)
    ] if chrome_cache.exists() else []
    if not versions:
        raise RepairError(f"Could not find chrome plugin cache under {chrome_cache}")

    return sorted(versions, key=lambda p: tuple(int(x) for x in p.name.split(".")))[-1].resolve()


def validate_plugin_dir(path: Path, label: str) -> None:
    required = [
        path / ".codex-plugin" / "plugin.json",
        path / "assets",
        path / "scripts" / "browser-client.mjs",
        path / EXTENSION_ID_FILE,
        path / "skills" / "chrome" / "SKILL.md",
    ]
    missing = [str(item) for item in required if not item.exists()]
    if missing:
        raise RepairError(f"{label} plugin directory is incomplete: {', '.join(missing)}")


def parse_trusted_hashes(codex_home: Path) -> list[str]:
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return []
    text = config_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S\s*=\s*"([^"]*)"', text)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def backup_path(cache_plugin: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return cache_plugin.with_name(f"{cache_plugin.name}.backup.{stamp}")


def copytree_replace(source: Path, target: Path, reporter: Reporter) -> Path:
    backup = backup_path(target)
    reporter.change(f"Back up {target} to {backup}")
    if not reporter.dry_run:
        if target.exists():
            shutil.copytree(target, backup, symlinks=True)
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=True)
    return backup


def needs_cache_sync(source_plugin: Path, cache_plugin: Path, reporter: Reporter, codex_home: Path) -> bool:
    source_client = source_plugin / "scripts" / "browser-client.mjs"
    cache_client = cache_plugin / "scripts" / "browser-client.mjs"
    source_hash = sha256(source_client)
    cache_hash = sha256(cache_client)
    trusted_hashes = parse_trusted_hashes(codex_home)

    reporter.info(f"Source browser-client hash: {source_hash or 'missing'}")
    reporter.info(f"Cache browser-client hash: {cache_hash or 'missing'}")
    if trusted_hashes:
        reporter.info(f"Trusted browser-client hashes from config: {', '.join(trusted_hashes)}")

    if source_hash and trusted_hashes and source_hash not in trusted_hashes:
        reporter.warn(
            "Bundled marketplace browser-client hash is not listed as trusted in config.toml. "
            "Codex App may need reinstall/update."
        )

    if source_hash != cache_hash:
        return True

    required_paths = [
        cache_plugin / ".codex-plugin" / "plugin.json",
        cache_plugin / "assets",
        cache_plugin / "docs",
        cache_plugin / "extension-host",
        cache_plugin / "scripts",
        cache_plugin / "skills",
    ]
    return any(not item.exists() for item in required_paths)


def repair_cache(source_plugin: Path, cache_plugin: Path, reporter: Reporter, codex_home: Path) -> None:
    validate_plugin_dir(source_plugin, "Source")
    if not cache_plugin.exists():
        reporter.change(f"Create cache plugin directory from {source_plugin}")
        if not reporter.dry_run:
            cache_plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_plugin, cache_plugin, symlinks=True)
        return

    if needs_cache_sync(source_plugin, cache_plugin, reporter, codex_home):
        backup = copytree_replace(source_plugin, cache_plugin, reporter)
        reporter.ok(f"Cache synced from official bundled plugin. Backup: {backup}")
    else:
        reporter.ok("Cache browser-client and required directories already match bundled plugin.")


def load_extension_config(plugin_dir: Path) -> tuple[str, str]:
    config = read_json(plugin_dir / EXTENSION_ID_FILE)
    extension_id = config.get("extensionId")
    host_name = config.get("extensionHostName") or HOST_NAME_DEFAULT
    if not isinstance(extension_id, str) or not extension_id:
        raise RepairError(f"Missing extensionId in {plugin_dir / EXTENSION_ID_FILE}")
    if not isinstance(host_name, str) or not host_name:
        raise RepairError(f"Invalid extensionHostName in {plugin_dir / EXTENSION_ID_FILE}")
    return extension_id, host_name


def host_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64", "x64"}:
        return "x64"
    raise RepairError(f"Unsupported CPU architecture for extension host: {platform.machine()}")


def host_binary_path(cache_plugin: Path) -> Path:
    system = platform.system()
    host_os = HOST_PLATFORM.get(system)
    if host_os is None:
        raise RepairError(f"Unsupported platform for native host: {system}")

    binary = "extension-host.exe" if host_os == "windows" else "extension-host"
    cache_root = cache_plugin.parent / "latest"
    root = cache_root if cache_root.exists() else cache_plugin
    return (root / "extension-host" / host_os / host_arch() / binary).resolve()


def edge_manifest_path(host_name: str) -> Path:
    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Microsoft Edge"
            / "NativeMessagingHosts"
            / f"{host_name}.json"
        )
    if system == "Linux":
        return Path.home() / ".config" / "microsoft-edge" / "NativeMessagingHosts" / f"{host_name}.json"
    if system == "Windows":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / "OpenAI" / "extension" / f"{host_name}.json"
    raise RepairError(f"Unsupported platform for Edge native host manifest: {system}")


def manifest_json(extension_id: str, host_name: str, host_path: Path) -> dict[str, Any]:
    return {
        "name": host_name,
        "description": "Codex chrome native messaging host",
        "type": "stdio",
        "path": str(host_path),
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }


def write_json_if_changed(path: Path, data: dict[str, Any], reporter: Reporter) -> None:
    content = json.dumps(data, separators=(",", ":"))
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        reporter.ok(f"Native messaging manifest already correct: {path}")
        return

    reporter.change(f"Write native messaging manifest: {path}")
    if not reporter.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def set_windows_edge_registry(host_name: str, manifest_path: Path, reporter: Reporter) -> None:
    if platform.system() != "Windows":
        return

    key = f"{EDGE_REGISTRY_PREFIX}\\{host_name}"
    reporter.change(f"Set Edge native host registry key {key} -> {manifest_path}")
    if reporter.dry_run:
        return
    subprocess.run(
        ["reg", "add", key, "/ve", "/t", "REG_SZ", "/d", str(manifest_path), "/f"],
        check=True,
    )


def repair_edge_manifest(cache_plugin: Path, reporter: Reporter) -> None:
    extension_id, host_name = load_extension_config(cache_plugin)
    host_path = host_binary_path(cache_plugin)
    if not host_path.exists():
        raise RepairError(f"Extension host binary does not exist: {host_path}")

    manifest_path = edge_manifest_path(host_name)
    write_json_if_changed(manifest_path, manifest_json(extension_id, host_name, host_path), reporter)
    set_windows_edge_registry(host_name, manifest_path, reporter)


def edge_user_data_dir() -> Path | None:
    system = platform.system()
    if system == "Windows":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / "Microsoft" / "Edge" / "User Data"
    parts = EDGE_USER_DATA.get(system)
    if parts is None:
        return None
    return Path.home().joinpath(*parts)


def read_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def profile_dirs(user_data: Path) -> list[Path]:
    if not user_data.exists():
        return []

    names: list[str] = []
    local_state = read_json_if_present(user_data / "Local State") or {}
    profile = local_state.get("profile")
    if isinstance(profile, dict):
        for key in ("last_used",):
            value = profile.get(key)
            if isinstance(value, str):
                names.append(value)
        active = profile.get("last_active_profiles")
        if isinstance(active, list):
            names.extend(item for item in active if isinstance(item, str))

    for entry in user_data.iterdir():
        if entry.is_dir() and (entry.name == "Default" or re.match(r"^Profile \d+$", entry.name)):
            names.append(entry.name)

    seen: set[str] = set()
    result = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        path = user_data / name
        if (path / "Preferences").exists() or (path / "Secure Preferences").exists():
            result.append(path)
    return result


def extension_status(profile: Path, extension_id: str) -> dict[str, Any]:
    settings = None
    preferences_path = None
    for filename in ("Secure Preferences", "Preferences"):
        path = profile / filename
        data = read_json_if_present(path)
        candidate = data
        for key in ("extensions", "settings", extension_id):
            if not isinstance(candidate, dict):
                candidate = None
                break
            candidate = candidate.get(key)
        if isinstance(candidate, dict):
            settings = candidate
            preferences_path = path
            break

    extension_path = profile / "Extensions" / extension_id
    versions = sorted([p.name for p in extension_path.iterdir() if p.is_dir()]) if extension_path.exists() else []
    registered = isinstance(settings, dict)
    state = settings.get("state") if isinstance(settings, dict) else None
    disable_reasons = settings.get("disable_reasons") if isinstance(settings, dict) else []
    if isinstance(disable_reasons, int):
        disable_reasons = [] if disable_reasons == 0 else [disable_reasons]
    if not isinstance(disable_reasons, list):
        disable_reasons = []
    installed = bool(versions)
    enabled = installed and registered and state != 0 and not disable_reasons

    return {
        "profile": str(profile),
        "preferences": str(preferences_path) if preferences_path else None,
        "registered": registered,
        "installed": installed,
        "enabled": enabled,
        "versions": versions,
        "state": state,
        "disable_reasons": disable_reasons,
    }


def report_edge_extension(cache_plugin: Path, reporter: Reporter, verbose: bool) -> None:
    extension_id, _host_name = load_extension_config(cache_plugin)
    user_data = edge_user_data_dir()
    if user_data is None:
        reporter.warn("Cannot scan Edge profiles on this platform.")
        return
    reporter.info(f"Edge user data directory: {user_data}")
    statuses = [extension_status(profile, extension_id) for profile in profile_dirs(user_data)]
    if not statuses:
        reporter.warn("No Edge profiles with Preferences were found.")
        return

    enabled = [status for status in statuses if status["enabled"]]
    installed = [status for status in statuses if status["installed"]]
    if enabled:
        reporter.ok(f"Codex extension is enabled in {len(enabled)} Edge profile(s).")
    elif installed:
        reporter.warn("Codex extension is installed in Edge but does not appear enabled.")
    else:
        reporter.warn(
            "Codex extension was not found in Edge profiles. Install it in Edge from the Chrome Web Store."
        )

    if verbose:
        print(json.dumps(statuses, indent=2, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    codex_home = args.codex_home.expanduser().resolve()
    reporter = Reporter(args.dry_run)

    try:
        if platform.system() != "Darwin":
            raise RepairError("This repair script is macOS-only.")

        source_plugin = resolve_source_plugin(codex_home, args.source_plugin)
        cache_plugin = resolve_cache_plugin(codex_home, args.cache_plugin)
        reporter.info(f"Codex home: {codex_home}")
        reporter.info(f"Bundled chrome plugin: {source_plugin}")
        reporter.info(f"Cached chrome plugin: {cache_plugin}")
        report_environment_versions(cache_plugin, reporter)

        if not args.skip_cache_sync:
            repair_cache(source_plugin, cache_plugin, reporter, codex_home)
        else:
            validate_plugin_dir(cache_plugin, "Cache")

        if not args.skip_edge_manifest:
            repair_edge_manifest(cache_plugin, reporter)
        else:
            reporter.info("Skipped Edge native messaging manifest repair.")

        report_edge_extension(cache_plugin, reporter, args.verbose)

        if reporter.dry_run:
            reporter.info("Dry run complete. Re-run without --dry-run to apply changes.")
        elif reporter.changed:
            reporter.ok("Repair complete. Restart Codex App and reload the Codex extension in Edge.")
        else:
            reporter.ok("No changes were required.")
        return 0
    except RepairError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Command failed: {' '.join(exc.cmd)}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
