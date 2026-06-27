---
name: codex-edge-chrome-repair
description: macOS-only repair workflow for Codex App Chrome plugin failures involving Microsoft Edge or corrupted openai-bundled chrome plugin cache. Use when Codex on macOS cannot connect to Edge through the Codex Chrome Extension, reports Chrome plugin disconnected, logs show missing or invalid plugin.json, browser-client is not trusted, native messaging host is missing, or Edge has the extension installed but @chrome cannot list tabs.
---

# Codex Edge Chrome Repair

Use this macOS-only skill to diagnose and repair the local Codex Chrome plugin bridge when the user wants to control Microsoft Edge through the `@chrome` / `chrome@openai-bundled` skill.

Do not present this as a Windows fix. Windows uses a different Edge native messaging registry path and should have a separate workflow.

## Workflow

1. Run the zsh script in dry-run mode first. Prefer this script because it does not require Python:

```bash
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --dry-run
```

2. Review the output for these common causes:

- `browser-client.mjs` cache hash differs from the bundled marketplace copy: the cache has been modified or partially refreshed, so Codex refuses to trust it.
- Edge extension is installed and enabled but Edge native host manifest is missing: Edge can load the extension but cannot connect it to Codex.
- `plugin.json`, `.codex-plugin`, `assets`, or `scripts/browser-client.mjs` missing under the cache: the cached plugin directory is incomplete.

3. If the dry run looks correct, run the repair:

```bash
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh
```

4. Ask the user to restart Codex App and reload the Codex extension in Edge if the UI still shows disconnected. The native bridge and trusted-cache checks are only reloaded reliably after a restart.

## Script Behavior

The script is intentionally conservative:

- It refuses to run on non-macOS platforms.
- It prints the local macOS, CPU, Codex App, Codex CLI, Edge, Chrome plugin cache, and extension ID versions before applying changes.
- It reads `$CODEX_HOME` or defaults to `~/.codex`.
- It locates the official bundled Chrome plugin at `.tmp/bundled-marketplaces/openai-bundled/plugins/chrome`.
- It locates the active cache at `plugins/cache/openai-bundled/chrome/latest`, or the highest versioned cache directory.
- It backs up the cache before syncing the official bundled plugin into the cache.
- It writes a Microsoft Edge native messaging manifest for `com.openai.codexextension`.
- It scans Edge profiles for the Codex extension ID from `scripts/extension-id.json`.

## Useful Options

```bash
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --help
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --dry-run
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --skip-cache-sync
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --skip-edge-manifest
<skill-dir>/scripts/repair_codex_edge_chrome_macos.sh --codex-home /path/to/.codex
```

Use `--skip-cache-sync` if the cache is already trusted and only Edge native messaging needs repair. Use `--skip-edge-manifest` if only the Codex plugin cache needs repair.

The Python script `repair_codex_edge_chrome.py` is optional. Use it only when `python3` is available. The zsh script is the default path for users who do not have Python installed.

## Known Tested Versions

This skill was created and validated on macOS 15.2 arm64 with Codex App 26.519.41501, Codex CLI `codex-cli 0.133.0-alpha.1`, `chrome@openai-bundled` 26.519.41501, Microsoft Edge 148.0.3967.83, and Codex Chrome Extension ID `hehggadaopoacecdllhhajmbjkdcmajg`.

It was revalidated on macOS 15.2 arm64 with Codex App 26.623.42026, Codex CLI `codex-cli 0.142.3`, `chrome@openai-bundled` 26.623.42026, Microsoft Edge 149.0.4022.96, and the same Codex Chrome Extension ID.

## Safety Notes

- Do not edit `scripts/browser-client.mjs` manually. Codex trusts it by SHA256 hash, so local modifications commonly break `@chrome`.
- Prefer syncing from the bundled marketplace copy instead of copying random plugin files from the internet.
- Do not hardcode user-specific paths in the skill. Use `$CODEX_HOME`, `--codex-home`, and the script's platform detection.
- If Edge still cannot connect after repair, confirm the Codex extension is enabled in Edge and reload it from `edge://extensions`.
