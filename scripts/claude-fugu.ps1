[CmdletBinding(PositionalBinding=$false)]
param(
  [ValidateSet("fugu", "fugu-ultra", "fugu-ultra-20260615")]
  [string]$Model = "fugu-ultra",

  [ValidateSet("high", "xhigh", "max")]
  [string]$Effort = "high",

  [int]$MaxTokens = 4096,

  [switch]$Fast,

  [int]$Port = 4010,

  [switch]$CheckOnly,

  [switch]$FullClaude,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ClaudeArgs
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:SAKANA_API_KEY)) {
  throw "SAKANA_API_KEY is not set. In PowerShell, run: `$env:SAKANA_API_KEY = 'sk-...'"
}

if ($Fast) {
  $Model = "fugu"
  $Effort = "high"
  $MaxTokens = [Math]::Min($MaxTokens, 2048)
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  throw "Claude CLI was not found on PATH."
}

$adapterPath = Join-Path $PSScriptRoot "fugu_anthropic_adapter.py"

function Test-Gateway {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 500) { return $false }
    return ($response.Content -like "*sakana-fugu-adapter*")
  } catch {
    return $false
  }
}

if (-not (Test-Gateway)) {
  $adapterArgs = @($adapterPath, "--host", "127.0.0.1", "--port", "$Port")
  Start-Process -FilePath "python" -ArgumentList $adapterArgs -WindowStyle Hidden | Out-Null

  $deadline = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if (Test-Gateway) { break }
  }
}

if (-not (Test-Gateway)) {
  throw "Sakana Fugu adapter did not become ready on http://127.0.0.1:$Port"
}

if ($CheckOnly) {
  Write-Host "Sakana Fugu adapter is ready on http://127.0.0.1:$Port"
  exit 0
}

$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:$Port"
$env:ANTHROPIC_AUTH_TOKEN = "sk-sakana-local"
$env:ANTHROPIC_MODEL = $Model
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = $Model
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = if ($Model -eq "fugu-ultra") { "Sakana Fugu Ultra" } else { "Sakana Fugu" }
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "Sakana $Model via local LiteLLM gateway"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
$env:CLAUDE_CODE_EFFORT_LEVEL = $Effort
$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"
$env:FUGU_MAX_TOKENS = "$MaxTokens"

$launchArgs = @("--model", $Model, "--effort", $Effort)
if (-not $FullClaude) {
  $launchArgs = @("--bare") + $launchArgs
}
$launchArgs += $ClaudeArgs

Write-Host "Starting Claude Code with $Model through $env:ANTHROPIC_BASE_URL (max tokens: $MaxTokens)"
& claude @launchArgs
exit $LASTEXITCODE
