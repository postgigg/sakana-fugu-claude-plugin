---
name: sakana-fugu
description: Use this skill when the user wants to run Claude Code against Sakana Fugu, configure the Sakana Fugu gateway, troubleshoot claude-fugu.ps1, or set SAKANA_API_KEY for Claude CLI.
---

# Sakana Fugu For Claude Code

Use the bundled launcher:

```powershell
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1
```

Requirements:

- `SAKANA_API_KEY` must be set in the shell before launching.
The launcher starts a local Anthropic-compatible adapter on `127.0.0.1:4010`, routes model IDs `fugu`, `fugu-ultra`, and `fugu-ultra-20260615` to `https://api.sakana.ai/v1`, and then starts Claude Code with `ANTHROPIC_BASE_URL` pointed at that adapter. The default model is `fugu-ultra`.

Use `-Model fugu-ultra` to launch the higher-capability model:

```powershell
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu-ultra
```
