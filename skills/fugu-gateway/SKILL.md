---
name: fugu-gateway
description: Use this skill when configuring, launching, or troubleshooting Sakana Fugu in Claude Code via the local LiteLLM gateway, including SAKANA_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_CUSTOM_MODEL_OPTION, fugu, and fugu-ultra.
---

# Fugu Gateway

Claude Code cannot call Sakana's OpenAI-compatible API directly. It needs an Anthropic Messages-compatible gateway. This plugin uses a local Python adapter for that protocol bridge.

Launch with:

```powershell
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1
```

Common options:

```powershell
# Use Fugu Ultra
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model fugu-ultra

# Use a different gateway port
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Port 4011
```

If launch fails:

- Confirm `SAKANA_API_KEY` is set in the shell running the launcher.
- Confirm nothing else is using the selected port.
