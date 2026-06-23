---
description: Show how to launch Claude Code with Sakana Fugu
argument-hint: "[fugu|fugu-ultra]"
allowed-tools: []
---

Use the local launcher from a new PowerShell window:

```powershell
$env:SAKANA_API_KEY = "sk-..."
C:\Users\exont\.claude\skills\sakana-fugu\scripts\claude-fugu.ps1 -Model ${ARGUMENTS}
```

If no model is supplied, use `fugu-ultra`.
