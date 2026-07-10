[CmdletBinding()]
param(
  [ValidateSet('install','status','uninstall')]
  [string]$Action = 'install',
  [string]$TaskPrefix = 'UAPNewsHub',
  [string]$Python = 'python.exe',
  [System.Management.Automation.PSCredential]$Credential
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tasks = @{
  Hourly = @{ Script = Join-Path $PSScriptRoot 'run_hourly.ps1'; Minutes = 60 }
  Daily = @{ Script = Join-Path $PSScriptRoot 'run_daily.ps1'; Minutes = 1440 }
}

function Get-TaskName([string]$name) { "$TaskPrefix-$name" }
function Get-TaskAction([string]$script) {
  $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`""
  New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $root
}

switch ($Action) {
  'status' {
    foreach ($name in $tasks.Keys) {
      $task = Get-ScheduledTask -TaskName (Get-TaskName $name) -ErrorAction SilentlyContinue
      if ($null -eq $task) { Write-Output "$name: not installed"; continue }
      $info = Get-ScheduledTaskInfo -TaskName $task.TaskName
      Write-Output "$name: $($task.State); last=$($info.LastRunTime); result=$($info.LastTaskResult); next=$($info.NextRunTime)"
    }
  }
  'uninstall' {
    foreach ($name in $tasks.Keys) { Unregister-ScheduledTask -TaskName (Get-TaskName $name) -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Output 'UAP News Hub scheduled tasks removed.'
  }
  'install' {
    if ($null -eq $Credential) { $Credential = Get-Credential -Message 'Credential for unattended UAP News Hub tasks' }
    $password = $Credential.GetNetworkCredential().Password
    foreach ($name in $tasks.Keys) {
      $definition = $tasks[$name]
      $trigger = if ($name -eq 'Hourly') { New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(2)) -RepetitionInterval (New-TimeSpan -Minutes $definition.Minutes) -RepetitionDuration (New-TimeSpan -Days 3650) } else { New-ScheduledTaskTrigger -Daily -At '02:15' }
      $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8) -RestartCount 0
      Register-ScheduledTask -TaskName (Get-TaskName $name) -Action (Get-TaskAction $definition.Script) -Trigger $trigger -Settings $settings -User $Credential.UserName -Password $password -RunLevel Limited -Force | Out-Null
      Write-Output "Installed $(Get-TaskName $name) (overlap policy: IgnoreNew)."
    }
    Write-Output 'Use -Action status to inspect runs; runner logs are in data/logs and stale locks are recovered by the Python lock guard.'
  }
}
