# Sakana Fugu for Claude Code

<p align="center">
  <strong>A local Claude Code plugin that runs Sakana Fugu through an Anthropic-compatible adapter.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a>
  ·
  <a href="#models">Models</a>
  ·
  <a href="#how-it-works">How It Works</a>
  ·
  <a href="#security">Security</a>
</p>

---

## Overview

Sakana's Fugu API is OpenAI-compatible. Claude Code expects an Anthropic Messages-compatible API when using `ANTHROPIC_BASE_URL`.

This plugin bridges that gap with a small local Python adapter:

```text
Claude Code -> local Anthropic adapter -> Sakana /v1/chat/completions
```

It includes:

- Claude Code plugin manifest
- `/fugu` helper command
- `fugu-gateway` skill
- PowerShell launcher for Windows
- Local Python adapter for `/v1/messages`, `/v1/messages/count_tokens`, and `/v1/models`
- Tool-call validation and one-shot repair for malformed Fugu tool calls
- Anthropic-compatible streaming events, including `input_json_delta` for tool arguments

## Quick Start

Clone or copy this plugin into Claude's local skills directory:

```powershell
git clone https://github.com/postgigg/sakana-fugu-claude-plugin.git `
  $env:USERPROFILE\.claude\skills\sakana-fugu
```

Set your Sakana API key:

```powershell
[Environment]::SetEnvironmentVariable("SAKANA_API_KEY", "fish_...", "User")
$env:SAKANA_API_KEY = [Environment]::GetEnvironmentVariable("SAKANA_API_KEY", "User")
```

Launch Claude Code through Fugu Ultra:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1
```

## Models

Use the fast model:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu
```

Use Fugu Ultra, the default model:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu-ultra
```

Use the dated Ultra model:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu-ultra-20260615
```

## Verify

Check that the local adapter can start:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -CheckOnly
```

Run a one-shot Claude request:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 `
  -ClaudeArgs @("-p", "Say exactly ok", "--output-format", "json")
```

## How It Works

The launcher starts `scripts/fugu_anthropic_adapter.py` on `127.0.0.1:4010`, then starts Claude Code with:

```powershell
ANTHROPIC_BASE_URL=http://127.0.0.1:4010
ANTHROPIC_AUTH_TOKEN=sk-sakana-local
ANTHROPIC_MODEL=fugu
```

The adapter accepts Anthropic Messages requests from Claude Code and forwards them to Sakana's OpenAI-compatible chat completions endpoint.

For tool use, the adapter also acts as a guardrail:

- Converts Claude Code tools into OpenAI-compatible function schemas
- Removes malformed historical tool calls that are missing required fields
- Validates new model tool calls before Claude Code receives them
- Retries once when Fugu emits malformed tool arguments
- Streams tool arguments with Anthropic `input_json_delta` events so Claude Code can execute them correctly

## Security

The launcher reads `SAKANA_API_KEY` from your environment. It does not write your API key into plugin files.

Keep these out of commits:

- real API keys
- local debug logs
- temp gateway configs
- Claude session files

## Notes

The launcher defaults to Claude Code `--bare` mode. This keeps the startup context smaller and avoids unrelated plugin or MCP overhead. Use `-FullClaude` when you want your normal Claude Code customizations loaded.

For faster responses, use the fast model preset:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Fast
```

For Ultra with shorter responses:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -MaxTokens 2048
```

For Ultra with lower token usage while searching code:

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu-ultra -Lean
```

```powershell
$env:USERPROFILE\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -FullClaude
```

## License

MIT
