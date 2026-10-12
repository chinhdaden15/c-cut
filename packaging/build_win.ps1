# Build C-Cut cho Windows x64 → dist\C-Cut-Setup.exe  (cần: Python 3.11, MSVC Build Tools, Inno Setup 6)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PY = if ($env:PY) { $env:PY } else { "python" }
$ff = "build\ffmpeg"
if (-not (Test-Path "$ff\ffmpeg.exe")) {
  New-Item -ItemType Directory -Force $ff | Out-Null
  Invoke-WebRequest "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile "build\ff.zip"
  Expand-Archive "build\ff.zip" "build\ffx" -Force
  Get-ChildItem "build\ffx" -Recurse -Include ffmpeg.exe,ffprobe.exe | Copy-Item -Destination $ff
}
& $PY packaging\build_seed.py --ffmpeg-dir $ff; if ($LASTEXITCODE) { exit 1 }
Remove-Item -Recurse -Force build\nuitka -ErrorAction SilentlyContinue
& $PY -m nuitka --module thagent --include-package=thagent --output-dir=build\nuitka --remove-output --assume-yes-for-downloads --msvc=latest; if ($LASTEXITCODE) { exit 1 }
& $PY -m PyInstaller --noconfirm --clean --distpath build\pyi --workpath build\pyi-work packaging\ccut.spec; if ($LASTEXITCODE) { exit 1 }
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
& $iscc packaging\ccut.iss; if ($LASTEXITCODE) { exit 1 }
Write-Host "-> dist\C-Cut-Setup.exe"
