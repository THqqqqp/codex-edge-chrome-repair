# Codex Edge Chrome Repair Skill

Language: [English](#english) | [中文](#中文说明)

## English

[中文说明](#中文说明)

This is a **macOS-only** Codex skill for repairing the connection between Codex App's `chrome@openai-bundled` / `@chrome` skill and Microsoft Edge.

Use it when:

- The Codex Chrome Extension is installed in Edge, but Codex App still shows it as disconnected.
- `@chrome` cannot list Edge tabs.
- Codex logs include `browser-client is not trusted`.
- The Codex plugin cache is missing `.codex-plugin`, `assets`, `plugin.json`, or `browser-client.mjs`.
- Edge is missing the Codex Native Messaging Host manifest.

Not supported:

- Windows. Edge native messaging registration and cache behavior are different on Windows, and this repository intentionally targets macOS only.
- Linux. Linux paths differ and are not tested.

### Tested Environment

The original repair and validation were done on:

- macOS: `15.2`, Apple Silicon `arm64`
- Codex App: `26.519.41501`
- Codex CLI: `codex-cli 0.133.0-alpha.1`
- Codex Chrome plugin cache: `chrome@openai-bundled 26.519.41501`
- Microsoft Edge: `148.0.3967.83`
- Codex Chrome Extension ID: `hehggadaopoacecdllhhajmbjkdcmajg`

It was also revalidated with the newer plugin layout and native host name on:

- macOS: `15.2`, Apple Silicon `arm64`
- Codex App: `26.623.42026`
- Codex CLI: `codex-cli 0.142.3`
- Codex Chrome plugin cache: `chrome@openai-bundled 26.623.42026`
- Microsoft Edge: `149.0.4022.96`
- Codex Chrome Extension ID: `hehggadaopoacecdllhhajmbjkdcmajg`

The script prints the current machine's versions when it runs. Other versions may work, but run `--dry-run` first and compare the output.

### What if Python is not installed?

Use the zsh script first. It does not require Python:

```bash
./skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome_macos.sh --dry-run
./skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome_macos.sh
```

The zsh script only relies on built-in macOS tools: `zsh`, `rsync`, `shasum`, `sed`, `find`, `mkdir`, and `cp`.

The Python script is optional:

```bash
python3 skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome.py --dry-run
python3 skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome.py
```

### Install

```bash
mkdir -p ~/.codex/skills
cp -R skills/codex-edge-chrome-repair ~/.codex/skills/
```

Restart Codex App after copying the skill.

Or run:

```bash
./scripts/install-local.sh
```

### Use in Codex

Ask Codex:

```text
Use codex-edge-chrome-repair to fix my Edge @chrome connection.
```

### What It Changes

The script:

- Finds the official bundled Chrome plugin under `~/.codex/.tmp/bundled-marketplaces/openai-bundled/plugins/chrome`.
- Finds the active cache under `~/.codex/plugins/cache/openai-bundled/chrome`.
- Compares the SHA256 hash of `scripts/browser-client.mjs`.
- Backs up the cache before syncing the official bundled plugin into the cache.
- Writes the Edge Native Messaging Host manifest:
  `~/Library/Application Support/Microsoft Edge/NativeMessagingHosts/com.openai.codexextension.json`
- Checks whether the Codex extension exists in Edge profiles.

After repair, restart Codex App and reload the Codex extension from `edge://extensions`.

## 中文说明

[English](#english)

这是一个 **macOS 专用** 的 Codex skill，用来修复 Codex App 的 `chrome@openai-bundled` / `@chrome` 无法连接 Microsoft Edge 的问题。

适用场景：

- Edge 已安装 Codex Chrome Extension，但 Codex App 仍显示未连接。
- `@chrome` 无法列出 Edge 标签页。
- Codex 日志出现 `browser-client is not trusted`。
- Codex 插件缓存缺失 `.codex-plugin`、`assets`、`plugin.json` 或 `browser-client.mjs`。
- Edge 缺少 Codex Native Messaging Host manifest。

不适用场景：

- Windows。Windows 的 Edge 原生消息注册表路径和插件缓存行为不同，本仓库没有把 Windows 作为支持目标。
- Linux。Linux 路径也不同，未测试。

### 已测试环境

本仓库最初修复和验证的环境：

- macOS：`15.2`，Apple Silicon `arm64`
- Codex App：`26.519.41501`
- Codex CLI：`codex-cli 0.133.0-alpha.1`
- Codex Chrome plugin cache：`chrome@openai-bundled 26.519.41501`
- Microsoft Edge：`148.0.3967.83`
- Codex Chrome Extension ID：`hehggadaopoacecdllhhajmbjkdcmajg`

后来也在新版插件目录结构和新版 native host 文件名下重新验证：

- macOS：`15.2`，Apple Silicon `arm64`
- Codex App：`26.623.42026`
- Codex CLI：`codex-cli 0.142.3`
- Codex Chrome plugin cache：`chrome@openai-bundled 26.623.42026`
- Microsoft Edge：`149.0.4022.96`
- Codex Chrome Extension ID：`hehggadaopoacecdllhhajmbjkdcmajg`

脚本会在运行时打印当前机器的版本信息。不同版本也可能可用，但请先跑 `--dry-run` 对照输出。

### 没有 Python 怎么办？

优先使用 zsh 脚本，不需要安装 Python：

```bash
./skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome_macos.sh --dry-run
./skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome_macos.sh
```

这个脚本只依赖 macOS 自带工具：`zsh`、`rsync`、`shasum`、`sed`、`find`、`mkdir`、`cp`。

Python 脚本是可选版本，适合已经有 `python3` 的机器：

```bash
python3 skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome.py --dry-run
python3 skills/codex-edge-chrome-repair/scripts/repair_codex_edge_chrome.py
```

### 安装 Skill

```bash
mkdir -p ~/.codex/skills
cp -R skills/codex-edge-chrome-repair ~/.codex/skills/
```

然后重启 Codex App。

也可以直接运行：

```bash
./scripts/install-local.sh
```

### 在 Codex 里使用

对 Codex 说：

```text
使用 codex-edge-chrome-repair 修复我的 Edge @chrome 连接。
```

### 修复内容

脚本会：

- 查找官方 bundled 插件：`~/.codex/.tmp/bundled-marketplaces/openai-bundled/plugins/chrome`
- 查找当前缓存插件：`~/.codex/plugins/cache/openai-bundled/chrome`
- 对比 `scripts/browser-client.mjs` 的 SHA256
- 如果缓存被改坏，先备份，再从官方 bundled 插件同步回缓存
- 写入 Edge 的 Native Messaging Host manifest：
  `~/Library/Application Support/Microsoft Edge/NativeMessagingHosts/com.openai.codexextension.json`
- 检查 Edge profile 里是否存在 Codex 扩展

修复后建议重启 Codex App，并在 `edge://extensions` 里重新加载 Codex 扩展。
