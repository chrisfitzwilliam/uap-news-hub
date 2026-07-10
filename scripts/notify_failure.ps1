param(
  [Parameter(Mandatory=$true)][string]$Message,
  [string]$Title = 'UAP News Hub pipeline alert'
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'data\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
[pscustomobject]@{ at = (Get-Date).ToUniversalTime().ToString('o'); event = 'notification'; level = 'warning'; title = $Title; message = $Message } | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $logDir ("pipeline-{0}.jsonl" -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')))
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode($Title)) > $null
$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode($Message)) > $null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('UAP News Hub').Show([Windows.UI.Notifications.ToastNotification]::new($xml))
