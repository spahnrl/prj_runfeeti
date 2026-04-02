# Close Cursor/PyCharm first (folder must not be in use).
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File tools\rename_project_folder.ps1
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$parent = Split-Path $projectRoot -Parent
$newPath = Join-Path $parent "prj_RunFeeti"
$leaf = Split-Path $projectRoot -Leaf
if ($leaf -eq "prj_RunFeeti") { Write-Host "Already named prj_RunFeeti."; exit 0 }
if (Test-Path $newPath) { Write-Error "Target exists: $newPath"; exit 1 }
Rename-Item -LiteralPath $projectRoot -NewName "prj_RunFeeti"
Write-Host "Renamed to $newPath"
Write-Host "Recreate .venv: cd prj_RunFeeti && py -3.13 -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
