@echo off
echo ============================================
echo   OrcaCode - Terminal AI Agent Setup
echo ============================================
echo.
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
echo.
echo [2/4] Checking and installing ripgrep...
powershell -NoProfile -Command ^
    "$rg = Get-Command rg -ErrorAction SilentlyContinue; ^
     if (-not $rg -and -not (Test-Path 'rg.exe')) { ^
         Write-Host 'Ripgrep not found in PATH. Attempting winget install...'; ^
         winget install BurntSushi.ripgrep.MSVC --accept-package-agreements --accept-source-agreements; ^
         $rg = Get-Command rg -ErrorAction SilentlyContinue; ^
         if (-not $rg) { ^
             Write-Host 'winget failed or unavailable. Downloading standalone binary from GitHub...'; ^
             $url = 'https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/ripgrep-14.1.0-x86_64-pc-windows-msvc.zip'; ^
             $zip = Join-Path $env:TEMP 'ripgrep.zip'; ^
             $dest = Join-Path $env:TEMP 'ripgrep_extracted'; ^
             try { ^
                 Invoke-WebRequest -Uri $url -OutFile $zip; ^
                 Expand-Archive -Path $zip -DestinationPath $dest -Force; ^
                 Copy-Item (Join-Path $dest '*\rg.exe') -Destination '.' -Force; ^
                 Write-Host 'Successfully downloaded and bundled standalone rg.exe to current folder!'; ^
             } catch { ^
                 Write-Host 'Failed to download ripgrep binary. OrcaCode will use the pure-Python search fallback instead.' -ForegroundColor Yellow; ^
             } finally { ^
                 if (Test-Path $zip) { Remove-Item $zip -Force }; ^
                 if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }; ^
             } ^
         } ^
     } else { ^
         Write-Host 'Ripgrep is already available.' ^
     }"
echo.
echo [3/4] Creating .env file...
if not exist .env (
    copy .env.example .env
    echo    Created .env from .env.example
) else (
    echo    .env already exists, skipping
)
echo [4/4] Adding OrcaCode to User PATH...
powershell -Command "$p = [Environment]::GetEnvironmentVariable('Path', 'User'); $d = '%~dp0'.TrimEnd('\'); if (-not $p.Split(';').Contains($d)) { [Environment]::SetEnvironmentVariable('Path', $p + ';' + $d, 'User'); Write-Host '   Successfully added' $d 'to User PATH' } else { Write-Host '   ' $d 'is already in PATH' }"
echo.
echo Done!
echo ============================================
echo   To use OrcaCode:
echo     python orca.py setup       (setup wizard)
echo     python orca.py run "your request"
echo     python orca.py chat        (interactive)
echo     python orca.py version
echo.
echo   Edit .env file to set your API key.
echo ============================================
pause