#!/bin/zsh
# Build C-Cut cho macOS (theo kiến trúc của máy đang chạy: x86_64 = Intel, arm64 = chip M) → dist/C-Cut-mac-<arch>.dmg
set -e
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
ARCH=$(uname -m); [ "$ARCH" = "x86_64" ] && TAG=intel || TAG=arm64
if [ -n "$FFMPEG_DIR" ]; then $PY packaging/build_seed.py --ffmpeg-dir "$FFMPEG_DIR"; else $PY packaging/build_seed.py; fi
rm -rf build/nuitka
$PY -m nuitka --module thagent --include-package=thagent --output-dir=build/nuitka --remove-output --assume-yes-for-downloads
$PY -m PyInstaller --noconfirm --clean --distpath build/pyi --workpath build/pyi-work packaging/ccut.spec
APP=build/pyi/C-Cut.app
codesign --force --deep --sign - "$APP"          # ký ad-hoc (chưa có Apple Developer ID)
STAGE=build/dmg; rm -rf $STAGE; mkdir -p $STAGE
cp -R "$APP" $STAGE/; ln -s /Applications $STAGE/Applications
[ -f "dist/Huong dan su dung C-Cut.pdf" ] && cp "dist/Huong dan su dung C-Cut.pdf" $STAGE/
mkdir -p dist; rm -f dist/C-Cut-mac-$TAG.dmg
hdiutil create -volname "C-Cut" -srcfolder $STAGE -ov -format UDZO dist/C-Cut-mac-$TAG.dmg
echo "→ dist/C-Cut-mac-$TAG.dmg"
