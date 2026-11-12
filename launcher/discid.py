# SPDX-License-Identifier: GPL-3.0-or-later
"""Seriennummer und CRC aus PlayStation-Abbildern lesen, ohne Zusatzprogramme: ISO9660 aus .iso, .img, .bin und .cue.
Damit findet VoidStation die Spiel-Einstellungen von DuckStation und PCSX2. Beide bilden die Namen so:
  DuckStation (core/system.cpp):  BOOT aus SYSTEM.CNF  ->  SLUS_007.00  ->  SLUS-00700
  PCSX2 (CDVD/CDVD.cpp):          BOOT2 aus SYSTEM.CNF ->  dieselbe Umformung, dazu die CRC der ELF-Datei
                                  (Elfheader.cpp: XOR ueber alle 32-Bit-Woerter)
.chd geht ueber chdman (CHDMAN, vom Launcher gesetzt: launcher/bin/chdman, nur 64 Bit): Es holt nur die noetigen
Bytebereiche heraus (extractraw), nicht das ganze Abbild. Andere komprimierte Abbilder (.cso, .gz, .pbp) gehen nicht:
None, der Launcher nimmt dann seinen Rueckfall.
Geht auch fuer ein Laufwerk (/dev/sr0): identify() sagt, ob eine PlayStation-Disc darin liegt.
Wird nur bei Bedarf geladen, das spart dem Launcher Speicher."""
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SECTOR = 2048
LAYOUTS = ((2048, 0), (2352, 24), (2352, 16), (2336, 8))         # (Sektorgroesse, Versatz der Nutzdaten)
# .chd: CD-Abbilder fuehren je Sektor 2352 Byte + 96 Byte Subcode (cdrom.h CD_FRAME_SIZE), DVD-Abbilder 2048 Byte
CHD_LAYOUTS = ((2448, 24), (2448, 16), (2448, 0), (2048, 0))
CHDMAN = ""                                                      # Pfad zu chdman; leer = .chd nicht lesbar
MAX_DIR = 1 << 20
MAX_FILE = 64 << 20


def _image_of(path):
    """.cue -> Datei des ersten Tracks; alles andere bleibt, wie es ist."""
    path = Path(path)
    if path.suffix.lower() != ".cue":
        return path
    text = path.read_text(encoding="latin-1")
    m = re.search(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', text, re.M | re.I)
    if not m:
        raise ValueError("cue ohne FILE")
    name = (m.group(1) or m.group(2)).replace("\\", "/").rsplit("/", 1)[-1]
    target = path.parent / name
    if target.exists():
        return target
    hit = [f for f in path.parent.iterdir() if f.name.lower() == name.lower()]
    if not hit:
        raise ValueError("Datei aus cue fehlt")
    return hit[0]


class _Chd:
    """Bytebereiche aus einer .chd, bedient wie eine offene Datei (seek, read, close). Je Stueck ein Aufruf von
    chdman extractraw; die Stuecke sind so gross, dass Verzeichnis und SYSTEM.CNF meist mit dem ersten da sind."""
    CHUNK = 2448 * 2048                                  # rund 5 MB, Vielfaches beider Sektorgroessen

    def __init__(self, path):
        if not CHDMAN:
            raise ValueError("kein chdman")
        self.path, self.pos, self.cache = str(path), 0, {}
        self.tmp = tempfile.mkdtemp(prefix="vs-chd-")
        try:
            r = subprocess.run([CHDMAN, "info", "-i", self.path], capture_output=True, text=True, timeout=60)
            m = re.search(r"^Logical size:\s*([\d,.]+)\s*bytes", r.stdout, re.M)
            if r.returncode != 0 or not m:
                raise ValueError("chdman info")
            self.size = int(re.sub(r"\D", "", m.group(1)))
        except (OSError, subprocess.SubprocessError, ValueError):
            self.close()
            raise ValueError("chd nicht lesbar") from None

    def seek(self, pos):
        self.pos = pos

    def _chunk(self, base):
        if base not in self.cache:
            if len(self.cache) >= 3:
                self.cache.clear()                       # hoechstens rund 15 MB im Speicher
            out = os.path.join(self.tmp, "stueck")
            try:
                subprocess.run([CHDMAN, "extractraw", "-f", "-i", self.path, "-o", out, "-isb", str(base),
                                "-ib", str(min(self.CHUNK, self.size - base))],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=True)
                with open(out, "rb") as f:
                    self.cache[base] = f.read()
            except (OSError, subprocess.SubprocessError):
                raise ValueError("chd nicht lesbar") from None
        return self.cache[base]

    def read(self, n):
        parts = []
        while n > 0 and self.pos < self.size:
            base = self.pos // self.CHUNK * self.CHUNK
            part = self._chunk(base)[self.pos - base:self.pos - base + n]
            if not part:
                break
            parts.append(part)
            self.pos += len(part)
            n -= len(part)
        return b"".join(parts)

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Disc:
    def __init__(self, path):
        chd = Path(path).suffix.lower() == ".chd"
        self.f: Any = _Chd(path) if chd else open(_image_of(path), "rb")
        try:                                             # Audio-CD im Laufwerk: Lesefehler (OSError)
            self.size, self.off = next((s for s in (CHD_LAYOUTS if chd else LAYOUTS) if self._probe(*s)), (0, 0))
            if not self.size:
                raise ValueError("kein ISO9660")
            pvd = self.read(16, SECTOR)
        except (OSError, ValueError):
            self.close()
            raise
        self.root = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]
        self.label = pvd[40:72].decode("latin-1").strip()

    def _probe(self, size, off):
        self.f.seek(16 * size + off)
        return self.f.read(6) == b"\x01CD001"

    def close(self):
        self.f.close()

    def read(self, lba, length):
        if self.size == SECTOR:
            self.f.seek(lba * SECTOR)
            out = self.f.read(length)
        else:
            parts, left = [], length
            while left > 0:
                self.f.seek(lba * self.size + self.off)
                parts.append(self.f.read(min(left, SECTOR)))
                left -= SECTOR
                lba += 1
            out = b"".join(parts)
        if len(out) != length:
            raise ValueError("Abbild zu kurz")
        return out

    def _entries(self, lba, length):
        if length > MAX_DIR:
            raise ValueError("Verzeichnis zu gross")
        data, pos = self.read(lba, length), 0
        while pos < len(data):
            rec = data[pos]
            if rec == 0:                                 # Rest des Sektors ist leer
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            name = data[pos + 33:pos + 33 + data[pos + 32]]
            yield (name.split(b";")[0].rstrip(b".").decode("latin-1").upper(),
                   struct.unpack_from("<I", data, pos + 2)[0], struct.unpack_from("<I", data, pos + 10)[0],
                   bool(data[pos + 25] & 2))
            pos += rec

    def file(self, parts):
        """Datei unter dem Pfad `parts` (Gross-/Kleinschreibung und Version egal) -> Inhalt."""
        lba, length = self.root
        for i, part in enumerate(parts):
            want = part.split(";")[0].rstrip(".").upper()
            hit = next((e for e in self._entries(lba, length) if e[0] == want and e[3] == (i < len(parts) - 1)), None)
            if not hit:
                raise ValueError(f"nicht im Abbild: {part}")
            lba, length = hit[1], hit[2]
        if length > MAX_FILE:
            raise ValueError("Datei zu gross")
        return self.read(lba, length)


def _cnf(disc):
    """SYSTEM.CNF -> {SCHLUESSEL: Wert} (Schluessel wie geschrieben, Leerzeichen entfernt)."""
    out = {}
    for line in disc.file(["SYSTEM.CNF"]).decode("latin-1").replace("\r", "\n").split("\n"):
        key, sep, value = line.partition("=")
        if sep:
            out[re.sub(r"\s", "", key)] = re.sub(r"\s", "", value)
    return out


def _serial(boot):
    """cdrom:\\SLUS_007.00;1 -> SLUS-00700 oder None, wenn es nicht wie eine Seriennummer aussieht."""
    name = boot.rsplit("\\", 1)[-1] if "\\" in boot else boot.rsplit(":", 1)[-1]
    name = name.rsplit(";", 1)[0]
    if not re.fullmatch(r".{4}[_-].{3}\..{2,}", name):
        return None
    serial = name.replace(".", "").replace("_", "-").upper()
    return serial if re.fullmatch(r"[A-Z0-9-]+", serial) else None


def _ps2_crc(disc, boot):
    m = re.match(r"cdrom0?:[\\/]*(.+)", boot)
    if not m:
        return None
    elf = disc.file(re.split(r"[\\/]+", m.group(1).split(";")[0]))
    crc = 0
    for (word,) in struct.iter_unpack("<I", elf[:len(elf) & ~3]):
        crc ^= word
    return crc or None


def identify(path):
    """Was liegt im Laufwerk bzw. Abbild? -> {"kind": "ps1"|"ps2", "serial", "crc", "label"} oder None (kein PlayStation-Spiel)."""
    try:
        d = Disc(path)
    except (OSError, ValueError, struct.error, IndexError):
        return None
    try:
        cnf = _cnf(d)
        boot2 = cnf.get("BOOT2", "")
        if boot2:
            serial = _serial(boot2)
            try:
                crc = _ps2_crc(d, boot2) if serial else None
            except (OSError, ValueError, struct.error, IndexError):
                crc = None
            return {"kind": "ps2", "serial": serial, "crc": crc, "label": d.label}
        boot = next((v for k, v in cnf.items() if k.lower() == "boot"), "")
        return {"kind": "ps1", "serial": _serial(boot), "crc": None, "label": d.label} if boot else None
    except (OSError, ValueError, struct.error, IndexError):
        return None
    finally:
        d.close()


def psx_serial(path):
    """Seriennummer fuer DuckStation oder None."""
    try:
        d = Disc(path)
    except (OSError, ValueError, struct.error, IndexError):
        return None
    try:
        boot = next((v for k, v in _cnf(d).items() if k.lower() == "boot"), "")
        return _serial(boot) if boot else None
    except (OSError, ValueError, struct.error, IndexError):
        return None
    finally:
        d.close()


def ps2_id(path):
    """(Seriennummer, CRC) fuer PCSX2 oder None."""
    try:
        d = Disc(path)
    except (OSError, ValueError, struct.error, IndexError):
        return None
    try:
        boot = _cnf(d).get("BOOT2", "")
        serial = _serial(boot) if boot else None
        crc = _ps2_crc(d, boot) if serial else None
        return (serial, crc) if crc else None
    except (OSError, ValueError, struct.error, IndexError):
        return None
    finally:
        d.close()
