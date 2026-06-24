param(
    [string[]]$BotArgs = @()
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $scriptDir 'start.bat'

$argumentList = @('/c', ('"{0}"' -f $batPath))
if ($BotArgs.Count -gt 0) {
    $argumentList += $BotArgs
}

Start-Process -FilePath 'cmd.exe' -ArgumentList $argumentList -WorkingDirectory $scriptDir -Verb RunAs
