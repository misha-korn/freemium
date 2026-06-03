# ---------------------------------------------------------------------------
# Rename the project folder feemium -> freemium.
#
# WHY THIS IS A SEPARATE SCRIPT:
# The folder can't be renamed while it is open in a live process that holds a
# recursive handle on it (the running Claude Code agent and/or PyCharm watching
# C:\projects). Windows refuses to rename a directory that is in use.
#
# HOW TO USE:
#   1. Close this Claude Code session AND any IDE (PyCharm/VS Code) that has
#      C:\projects or the project open.
#   2. Open a fresh PowerShell window.
#   3. Run:  powershell -ExecutionPolicy Bypass -File C:\projects\feemium\rename_to_freemium.ps1
# ---------------------------------------------------------------------------
$ErrorActionPreference = 'Stop'

$old = 'C:\projects\feemium'
$new = 'C:\projects\freemium'

# Move the process working dir out of the folder so it is not self-locked.
[System.IO.Directory]::SetCurrentDirectory('C:\projects')
Set-Location 'C:\projects'

if (-not (Test-Path $old)) { throw "Source not found: $old" }
if (Test-Path $new) { throw "Target already exists: $new" }

Rename-Item -LiteralPath $old -NewName 'freemium'
Write-Host "Renamed: $old -> $new" -ForegroundColor Green

# The virtualenv's console-script shims (pip.exe, celery.exe) bake in the old
# absolute path, so recreate the venv at the new location.
Write-Host "Recreating virtualenv at $new\.venv ..." -ForegroundColor Cyan
if (Test-Path "$new\.venv") { Remove-Item -Recurse -Force "$new\.venv" }
python -m venv "$new\.venv"
& "$new\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$new\.venv\Scripts\python.exe" -m pip install -r "$new\requirements\dev.txt"

Write-Host "Done. Project is now at $new" -ForegroundColor Green
