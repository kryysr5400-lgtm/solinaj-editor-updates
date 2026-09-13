param(
    [Parameter(Mandatory=$true)][string]$StageDir,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [string]$Launcher = "",
    [string]$PythonExe = "",
    [string]$TargetVersion = ""
)

$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "SolinajEditor_Update.log"

function Log([string]$m) {
    Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) -Encoding UTF8
}

Start-Sleep -Seconds 2
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $InstallDir ("_update_backup_files\" + $stamp)

try {
    Log "Dosya tabanli guncelleme basladi: $TargetVersion"
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

    $files = Get-ChildItem -Path $StageDir -Recurse -File
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($StageDir.Length).TrimStart('\','/')
        $dest = Join-Path $InstallDir $rel
        $bak = Join-Path $backupRoot $rel

        if (Test-Path $dest) {
            $bakDir = Split-Path -Parent $bak
            if ($bakDir) { New-Item -ItemType Directory -Force -Path $bakDir | Out-Null }
            Copy-Item -Force $dest $bak
        }

        $destDir = Split-Path -Parent $dest
        if ($destDir) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
        Copy-Item -Force $f.FullName $dest
    }

    Remove-Item -Recurse -Force $StageDir -ErrorAction SilentlyContinue

    $marker = @{
        version = $TargetVersion
        installed_at = (Get-Date).ToString("o")
        success = $true
    } | ConvertTo-Json

    [System.IO.File]::WriteAllText(
        (Join-Path $InstallDir "update_success.json"),
        $marker,
        (New-Object System.Text.UTF8Encoding($false))
    )

    Log "Guncelleme tamamlandi. Uygulama yeniden baslatiliyor."

    $started = $false
    $shortsLauncher = Join-Path $InstallDir "SolinajShorts_Launcher.vbs"
    if (Test-Path $shortsLauncher) {
        try {
            Start-Process -FilePath "wscript.exe" -ArgumentList @("`"$shortsLauncher`"") -WorkingDirectory $InstallDir
            Log "SolinajShorts_Launcher.vbs ile yeniden baslatildi."
            $started = $true
        } catch { Log ("Shorts launcher baslatma hatasi: " + $_.Exception.Message) }
    }

    if (-not $started -and $PythonExe -and (Test-Path $PythonExe)) {
        try {
            Start-Process -FilePath $PythonExe -ArgumentList @((Join-Path $InstallDir "app.py")) -WorkingDirectory $InstallDir
            Log "PythonExe ile yeniden baslatildi."
            $started = $true
        } catch { Log ("PythonExe baslatma hatasi: " + $_.Exception.Message) }
    }

    if (-not $started) {
        foreach ($cmd in @("pythonw.exe","python.exe","pyw.exe","py.exe")) {
            $found = Get-Command $cmd -ErrorAction SilentlyContinue
            if ($found) {
                try {
                    Start-Process -FilePath $found.Source -ArgumentList @((Join-Path $InstallDir "app.py")) -WorkingDirectory $InstallDir
                    Log "$cmd ile yeniden baslatildi."
                    $started = $true
                    break
                } catch { }
            }
        }
    }

    if (-not $started) {
        Log "UYARI: Guncelleme tamamlandi fakat uygulama otomatik acilamadi."
    }
}
catch {
    Log ("HATA: " + $_.Exception.Message)
    try {
        if (Test-Path $backupRoot) {
            $backupFiles = Get-ChildItem -Path $backupRoot -Recurse -File
            foreach ($b in $backupFiles) {
                $rel = $b.FullName.Substring($backupRoot.Length).TrimStart('\','/')
                $dest = Join-Path $InstallDir $rel
                $destDir = Split-Path -Parent $dest
                if ($destDir) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
                Copy-Item -Force $b.FullName $dest
            }
        }
    } catch {}
    throw
}
