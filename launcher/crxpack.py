#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""VoidStation-Tastatur fuer Chromium-Browser (Chromium, Brave, Brave Origin) einrichten.

Chromium laedt Erweiterungen ausserhalb des Web Stores nur als signierte .crx und per Richtlinie
(ExtensionInstallForcelist). Dieses Skript (als root aus install.sh/update.sh)
  * packt firefox/keyboard/ mit manifest.chromium.json als CRX3 und schreibt die Update-Datei (gupdate-XML),
    beides holt der Browser vom Launcher (http://127.0.0.1:8765/ext/keyboard.xml bzw. .crx),
  * schreibt die Richtlinien: Chromium bekommt dazu uBlock Origin Lite, Brave/Brave Origin uBlock Origin.

Schluessel: RSA 2048, je Geraet einmal erzeugt (in reinem Python, keine Abhaengigkeit) und behalten – daraus folgt die
Kennung der Erweiterung. Version: steigt nur, wenn sich der Inhalt aendert (sonst holte der Browser kein Update).

    python3 crxpack.py <quellordner> <zielordner> [<richtlinien-wurzel>]

<zielordner>: keyboard.crx, keyboard.xml, keyboard.key (nur root), keyboard.json (Kennung, Version, Pruefsumme).
<richtlinien-wurzel> (Standard /etc): <wurzel>/chromium/policies/managed/voidstation.json und
<wurzel>/brave/policies/managed/voidstation.json (Brave Origin liest dieselben)."""
import hashlib
import io
import json
import os
import secrets
import struct
import sys
import zipfile
from pathlib import Path

URL_BASE = "http://127.0.0.1:8765/ext/"
STORE = "https://clients2.google.com/service/update2/crx"
UBO = "cjpalhdlnbpafiamejdnhcphjbkeiagm"          # uBlock Origin (MV2: nur noch Brave liefert es selbst aus)
UBO_LITE = "ddkjiahejlhfcafbddmgiahcphecmpfh"     # uBlock Origin Lite (MV3, Chromium ab 150 die einzige Fassung)
FILES = ("background.js", "focus.js")


# ---------------------------------------------------------------------------
#  RSA (PKCS#1 v1.5, SHA-256) ohne Bibliotheken
# ---------------------------------------------------------------------------
def _probable_prime(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(40):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1      # obere zwei Bits gesetzt: n hat sicher 2*bits Bits
        if _probable_prime(c):
            return c


def new_key(bits=2048):
    e = 65537
    while True:
        p, q = _prime(bits // 2), _prime(bits // 2)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            return {"n": p * q, "e": e, "d": pow(e, -1, phi)}


def _der_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _der(tag, body):
    return bytes([tag]) + _der_len(len(body)) + body


def _der_int(v):
    b = v.to_bytes((v.bit_length() + 8) // 8, "big")         # fuehrende Null, wenn das oberste Bit gesetzt ist
    return _der(0x02, b)


def public_der(key):
    """SubjectPublicKeyInfo (DER), wie Chromium ihn in der CRX erwartet."""
    rsa = _der(0x30, _der_int(key["n"]) + _der_int(key["e"]))
    alg = _der(0x30, _der(0x06, bytes.fromhex("2a864886f70d010101")) + b"\x05\x00")
    return _der(0x30, alg + _der(0x03, b"\x00" + rsa))


def sign(key, data):
    k = (key["n"].bit_length() + 7) // 8
    t = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(data).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return pow(int.from_bytes(em, "big"), key["d"], key["n"]).to_bytes(k, "big")


def ext_id(pub):
    return "".join("abcdefghijklmnop"[c >> 4] + "abcdefghijklmnop"[c & 15] for c in hashlib.sha256(pub).digest()[:16])


# ---------------------------------------------------------------------------
#  CRX3
# ---------------------------------------------------------------------------
def _pb_bytes(field, data):
    tag, n, out = field << 3 | 2, len(data), b""
    for v in (tag, n):
        while True:
            b = v & 0x7F
            v >>= 7
            out += bytes([b | (0x80 if v else 0)])
            if not v:
                break
    return out + data


def crx3(key, zipdata):
    pub = public_der(key)
    signed = _pb_bytes(1, hashlib.sha256(pub).digest()[:16])            # SignedData.crx_id
    msg = b"CRX3 SignedData\x00" + struct.pack("<I", len(signed)) + signed + zipdata
    proof = _pb_bytes(1, pub) + _pb_bytes(2, sign(key, msg))            # AsymmetricKeyProof
    header = _pb_bytes(2, proof) + _pb_bytes(10000, signed)             # sha256_with_rsa, signed_header_data
    return b"Cr24" + struct.pack("<II", 3, len(header)) + header + zipdata


def build_zip(src, version):
    man = json.loads((src / "manifest.chromium.json").read_text(encoding="utf-8"))
    man["version"] = version
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in [("manifest.json", json.dumps(man, indent=2).encode())] + \
                          [(f, (src / f).read_bytes()) for f in FILES]:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))     # fester Zeitstempel: gleicher Inhalt
            info.compress_type = zipfile.ZIP_DEFLATED                          # = gleiche Pruefsumme
            z.writestr(info, data)
    return buf.getvalue()


def _write(path, data, mode=0o644):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data if isinstance(data, bytes) else data.encode())
    os.chmod(tmp, mode)
    tmp.replace(path)


def policies(root, kid):
    """Richtlinien schreiben: Tastatur + Werbeblocker, je Browserfamilie."""
    kbd = f"{kid};{URL_BASE}keyboard.xml"
    for name, extra in (("chromium", UBO_LITE), ("brave", UBO)):
        d = Path(root) / name / "policies" / "managed"
        d.mkdir(parents=True, exist_ok=True)
        pol = {"ExtensionInstallForcelist": [kbd, f"{extra};{STORE}"]}
        _write(d / "voidstation.json", json.dumps(pol, indent=2) + "\n")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, out = Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    keyf = out / "keyboard.key"
    try:
        key = {k: int(v) for k, v in json.loads(keyf.read_text()).items()}
    except (OSError, ValueError):
        key = new_key()
        _write(keyf, json.dumps({k: str(v) for k, v in key.items()}), 0o600)
    kid = ext_id(public_der(key))
    try:
        state = json.loads((out / "keyboard.json").read_text())
    except (OSError, ValueError):
        state = {}
    base = json.loads((src / "manifest.chromium.json").read_text(encoding="utf-8"))["version"]
    digest = hashlib.sha256(build_zip(src, base)).hexdigest()
    n = int(state.get("n", 0))
    if state.get("sha256") != digest or state.get("id") != kid or not (out / "keyboard.crx").exists():
        n += 1                                                   # neuer Inhalt: neue Version, sonst kein Update
    version = f"{base}.{n}"
    _write(out / "keyboard.crx", crx3(key, build_zip(src, version)))
    _write(out / "keyboard.xml",
           "<?xml version='1.0' encoding='UTF-8'?>\n"
           "<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>\n"
           f"  <app appid='{kid}'>\n"
           f"    <updatecheck codebase='{URL_BASE}keyboard.crx' version='{version}' />\n"
           "  </app>\n</gupdate>\n")
    _write(out / "keyboard.json", json.dumps({"id": kid, "version": version, "n": n, "sha256": digest}) + "\n")
    policies(argv[3] if len(argv) > 3 else "/etc", kid)
    print(f"VoidStation-Tastatur fuer Chromium-Browser: {kid} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
