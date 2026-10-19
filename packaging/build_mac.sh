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
cp "packaging/guide/Huong dan su dung C-Cut.pdf" $STAGE/
mkdir -p dist; rm -f dist/C-Cut-mac-$TAG.dmg
# hdiutil trên máy build hay báo "Resource busy" ngẫu nhiên → thử lại tối đa 5 lần
for i in 1 2 3 4 5; do
  hdiutil create -volname "C-Cut" -srcfolder $STAGE -ov -format UDZO dist/C-Cut-mac-$TAG.dmg && break
  [ $i = 5 ] && exit 1
  echo "hdiutil lỗi, thử lại ($i)"; sleep 10
done
echo "→ dist/C-Cut-mac-$TAG.dmg"
