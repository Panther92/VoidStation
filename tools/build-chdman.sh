#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  chdman fuer VoidStation bauen (launcher/bin/chdman, nur x86_64).
#
#    tools/build-chdman.sh            baut nach launcher/bin/chdman
#    MAME_TAG=mame0290 tools/build-chdman.sh
#
#  chdman wandelt bin/cue-Abbilder in CHD um (Spieleliste: "In CHD
#  umwandeln", launcher.py ChdConvert). Void liefert es nur zusammen mit
#  ganz MAME (rund 400 MB installiert) – darum baut VoidStation es aus dem
#  offiziellen MAME-Quelltext selbst und liefert die eine Datei mit.
#
#  Was der Bau macht:
#   * holt nur die noetigen Ordner des Tags (sparse checkout, rund 80 MB)
#   * baut nur die Werkzeuge (TOOLS=1 EMULATOR=0), davon nur chdman, mit den
#     Bibliotheken aus dem MAME-Quelltext (zlib, zstd, FLAC, LZMA, utf8proc,
#     expat) und fest eingebundener libstdc++
#   * ersetzt SDL durch vier leere Platzhalter: chdman braeuchte SDL nur fuer
#     die Zwischenablage (osdlib_unix.cpp), die es nie benutzt
#  Ergebnis: haengt nur von glibc ab (libc, libm).
#
#  Braucht: git, make, g++, python3, SDL2-Header (Void: SDL2-devel,
#  Debian/Ubuntu: libsdl2-dev) – die Header nur zum Uebersetzen von ocore_sdl.
#  Dauer: einige Minuten. Lizenz von MAME: GPL-2.0-or-later (COPYING im Tag),
#  chdman selbst BSD-3-Clause – siehe launcher/bin/LIESMICH.txt.
# =====================================================================
set -euo pipefail
TAG="${MAME_TAG:-mame0289}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/launcher/bin/chdman"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

git clone -q --depth 1 --branch "$TAG" --filter=blob:none --no-checkout https://github.com/mamedev/mame "$WORK/mame"
cd "$WORK/mame"
git sparse-checkout init --no-cone
printf '%s\n' /makefile /scripts/ /regtests/regtests.mak /COPYING /src/version.cpp /src/lib/ /src/osd/ /src/tools/ /src/emu/ \
  /3rdparty/genie/ /3rdparty/flac/ /3rdparty/zlib/ /3rdparty/zstd/ /3rdparty/lzma/ /3rdparty/utf8proc/ /3rdparty/expat/ \
  /3rdparty/aes256cbc/ /3rdparty/minimp3/ /3rdparty/wdlfft/ /3rdparty/nanosvg/ /3rdparty/rapidjson/ /3rdparty/pugixml/ \
  /3rdparty/libjpeg/ /3rdparty/asio/ /3rdparty/compat/ > .git/info/sparse-checkout
git checkout -q "$TAG"

PROJ=build/projects/sdl/mame/gmake-linux
make TOOLS=1 EMULATOR=0 REGENIE=1 NOWERROR=1 SYMBOLS=0 PRECOMPILE=0 USE_QTDEBUG=0 \
  NO_X11=1 NO_OPENGL=1 NO_USE_XINPUT=1 NO_USE_MIDI=1 NO_USE_PORTAUDIO=1 NO_USE_PULSEAUDIO=1 NO_USE_PIPEWIRE=1 \
  USE_SYSTEM_LIB_ZLIB=0 USE_SYSTEM_LIB_ZSTD=0 USE_SYSTEM_LIB_FLAC=0 USE_SYSTEM_LIB_UTF8PROC=0 USE_SYSTEM_LIB_EXPAT=0 \
  LDOPTS='-Wl,--as-needed -static-libstdc++ -static-libgcc' \
  "$PROJ/Makefile" build/generated/version.cpp
make -C "$PROJ" config=release64 -j"$(nproc)" chdman

# Noch einmal binden, mit Platzhaltern statt -lSDL2
cat > "$WORK/sdl-stub.c" <<'STUB'
#include <stddef.h>
char *SDL_GetClipboardText(void) { return NULL; }
int SDL_HasClipboardText(void) { return 0; }
int SDL_SetClipboardText(const char *text) { (void)text; return -1; }
void SDL_free(void *mem) { (void)mem; }
STUB
gcc -O2 -c "$WORK/sdl-stub.c" -o "$WORK/sdl-stub.o"
rm -f chdman
make -C "$PROJ" config=release64 verbose=1 chdman | grep -E '^g\+\+ -o' > "$WORK/link.cmd"
grep -q -- ' -lSDL2 ' "$WORK/link.cmd" || { echo "Bindezeile ohne -lSDL2 – Bau pruefen" >&2; exit 1; }
sed -i "s| -lSDL2 | $WORK/sdl-stub.o |" "$WORK/link.cmd"
(cd "$PROJ" && bash "$WORK/link.cmd")

if readelf -d chdman | grep NEEDED | grep -vqE 'libc\.so|libm\.so|ld-linux'; then
  echo "chdman haengt von mehr als glibc ab:" >&2; readelf -d chdman | grep NEEDED >&2; exit 1
fi
mkdir -p "$(dirname "$OUT")"
strip -o "$OUT" chdman
chmod 755 "$OUT"
"$OUT" help 2>&1 | head -n1
echo "glibc mindestens: $(objdump -T "$OUT" | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -n1)"
sha256sum "$OUT"
