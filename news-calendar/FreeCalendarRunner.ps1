param([switch]$Install, [switch]$SetKey, [switch]$CheckOnly, [string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:USERPROFILE 'Documents\HY-News-Updater'
$destination = Join-Path $env:USERPROFILE 'Documents\NinjaTrader 8\templates\HY'
$keyPath = Join-Path $root 'fred-key.dpapi'
$taskName = 'HY Free News Calendar'
New-Item -ItemType Directory -Force -Path $root | Out-Null
if (-not $SourceRoot) { $SourceRoot = $root }
$packageFiles = @('FreeCalendar.cs','HYNewsCalendarV5.cs','FreeCalendarRunner.ps1','FreeCalendar-Setup.cmd','package-hashes.json')
if ($Install -and ([IO.Path]::GetFullPath($SourceRoot) -ne [IO.Path]::GetFullPath($root))) {
    foreach ($name in $packageFiles) { Copy-Item -LiteralPath (Join-Path $SourceRoot $name) -Destination (Join-Path $root $name) -Force }
}
$statusPath = Join-Path $root 'status.json'
$lock = $null
$secret = $null
$plain = $null
try {
    $lock = [IO.File]::Open((Join-Path $root 'refresh.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    if ($SetKey) {
        # The operator enters this locally. DPAPI binds it to this Windows user.
        $secret = Read-Host 'FRED API key (hidden; stored for this Windows user only)' -AsSecureString
        $encrypted = ConvertFrom-SecureString $secret
        [IO.File]::WriteAllText($keyPath,$encrypted,[Text.Encoding]::UTF8)
    }
    if (-not (Test-Path -LiteralPath $keyPath)) { throw 'FRED key is missing. Run the approved setup with -SetKey.' }
    $secret = ConvertTo-SecureString ([IO.File]::ReadAllText($keyPath))
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $core = Join-Path $root 'FreeCalendar.cs'
    $native = Join-Path $root 'HYNewsCalendarV5.cs'
    $checks = Get-Content -Raw -LiteralPath (Join-Path $root 'package-hashes.json') | ConvertFrom-Json
    foreach ($file in @('FreeCalendar.cs','HYNewsCalendarV5.cs')) {
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $file)).Hash.ToLowerInvariant()
        if ($actual -ne $checks.$file) { throw ('Package hash changed: '+$file) }
    }
    Add-Type -Path @($core,$native) -ReferencedAssemblies @('System.dll','System.Core.dll','System.Xml.dll')
    $current = Join-Path $destination 'HYNewsCalendarV5.xml'
    if ($CheckOnly) {
        Write-Host 'Package and personal FRED key loaded. Calendar was not modified.'
        return
    }
    $final = [HY.News.FreeCalendar]::Refresh($current,$destination,$plain,(Join-Path $root 'source-history'),[DateTime]::UtcNow)
    [xml]$manifest = [IO.File]::ReadAllText($final)
    $status = [pscustomobject]@{
        schema='HY-FRED-FED-1';state='renewed';checked_at_utc=[DateTime]::UtcNow.ToString('o');
        manifest_sha256=(Get-FileHash -Algorithm SHA256 $final).Hash.ToLowerInvariant();
        verified_at_utc=$manifest.HYNewsCalendar.verifiedAtUtc;expires_at_utc=$manifest.HYNewsCalendar.expiresAtUtc;
        covered_through=$manifest.HYNewsCalendar.coveredThrough;orders_sent=$false;trading_logic_changed=$false
    }
    [IO.File]::WriteAllText($statusPath,($status | ConvertTo-Json),[Text.Encoding]::UTF8)
    if ($Install) {
        # Same user, least privilege, runs while logged in. No stored password,
        # no elevation, no execution-policy or security-setting changes.
        $script = Join-Path $root 'FreeCalendarRunner.ps1'
        $command = '& { . ([scriptblock]::Create([IO.File]::ReadAllText('''+$script.Replace("'","''")+'''))) }'
        $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -Command "'+$command+'"')
        $repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Hours 4)
        $login = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($repeat,$login) -Settings $settings -Principal $principal -Force | Out-Null
        Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State | Format-List
    }
    $status | ConvertTo-Json
}
catch {
    # Never include exception URLs/stack traces; API URLs may contain a key.
    $safe = $_.Exception.Message -replace '[a-z0-9]{32}','[REDACTED]'
    $status = [pscustomobject]@{schema='HY-FRED-FED-1';state='failed_last_calendar_retained';checked_at_utc=[DateTime]::UtcNow.ToString('o');error=$safe;orders_sent=$false;freshness_extended=$false}
    [IO.File]::WriteAllText($statusPath,($status | ConvertTo-Json),[Text.Encoding]::UTF8)
    Write-Host ($status | ConvertTo-Json)
    exit 1
}
finally {
    $plain=$null
    if($secret){$secret.Dispose()}
    if($lock){$lock.Dispose()}
}
