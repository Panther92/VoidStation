# SPDX-License-Identifier: GPL-3.0-or-later
"""Seriennummer und CRC aus PlayStation-Abbildern lesen, ohne Zusatzprogramme: ISO9660 aus .iso, .img, .bin und .cue.
Damit findet VoidStation die Spiel-Einstellungen von DuckStation und PCSX2. Beide bilden die Namen so:
  DuckStation (core/system.cpp):  BOOT aus SYSTEM.CNF  ->  SLUS_007.00  ->  SLUS-00700
  PCSX2 (CDVD/CDVD.cpp):          BOOT2 aus SYSTEM.CNF ->  dieselbe Umformung, dazu die CRC der ELF-Datei
                                  (Elfheader.cpp: XOR ueber alle 32-Bit-Woerter)
Komprimierte Abbilder (.chd, .cso, .gz, .pbp) gehen hier nicht: None, der Launcher nimmt dann seinen Rueckfall.
Wird nur bei Bedarf geladen, das spart dem Launcher Speicher."""
import re
import struct
from pathlib import Path

SECTOR = 2048
LAYOUTS = ((2048, 0), (2352, 24), (2352, 16), (2336, 8))         # (Sektorgroesse, Versatz der Nutzdaten)
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


class Disc:
    def __init__(self, path):
        self.f = open(_image_of(path), "rb")
        self.size, self.off = next((s for s in LAYOUTS if self._probe(*s)), (0, 0))
        if not self.size:
            self.close()
            raise ValueError("kein ISO9660")
        pvd = self.read(16, SECTOR)
        self.root = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]

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
        m = re.match(r"cdrom0?:[\\/]*(.+)", boot)
        if not serial or not m:
            return None
        elf = d.file(re.split(r"[\\/]+", m.group(1).split(";")[0]))
        crc = 0
        for (word,) in struct.iter_unpack("<I", elf[:len(elf) & ~3]):
            crc ^= word
        return (serial, crc) if crc else None
    except (OSError, ValueError, struct.error, IndexError):
        return None
    finally:
        d.close()
