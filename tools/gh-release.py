#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# =====================================================================
#  GitHub-Releases pflegen – laeuft in .github/workflows/release.yml
#
#  Stable-Stand (Zweig "stable"):  oberste Version aus CHANGELOG.en.md
#    -> fehlt das Release v<version>, wird es samt Tag auf dem stable-Commit angelegt
#  ISO (site/config.json auf "main", von "vspub --iso" gefuellt):
#    -> gibt es das Release v<iso.version> schon, bekommt es den Download-Abschnitt
#  Beides ist idempotent: ein bestehendes Release wird nur neu geschrieben, wenn
#  seine eigene ISO dazukommt oder sich deren Angaben aendern; Tags werden nie
#  verschoben. Von Hand geaenderte Release-Texte bleiben sonst erhalten.
#
#  Die ISO liegt auf SourceForge (GitHub erlaubt pro Datei hoechstens 2 GiB),
#  das Release verweist nur darauf.
#
#    python3 tools/gh-release.py --stable <checkout stable> --main <checkout main> [--repo owner/name]
#    python3 tools/gh-release.py ... --dry-run [--exists 0.15.0,...]   nur anzeigen, gh wird nicht aufgerufen
# =====================================================================
import argparse, json, os, re, subprocess, sys

HEAD_RE = re.compile(r"^##\s+(\S+)\s+[–-]\s+(\d{4}-\d{2}-\d{2})")
SITE = "https://voidstation.de/en/download/"


def changelog(path):
    """Versionen aus CHANGELOG.en.md: {version: {"date":…, "body": Markdown}} in Dateireihenfolge."""
    entries, cur = {}, None
    order = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = HEAD_RE.match(line)
            if m and m.group(1) == "Testing":
                cur = None                      # noch nicht freigegeben (sollte auf stable nie stehen)
            elif m:
                cur = {"date": m.group(2), "lines": []}
                entries[m.group(1)] = cur
                order.append(m.group(1))
            elif line.startswith("## "):
                cur = None                      # andere Ueberschrift beendet den Abschnitt
            elif cur is not None:
                cur["lines"].append(line.rstrip("\n"))
    for e in entries.values():
        e["body"] = "\n".join(e.pop("lines")).strip()
    return order, entries


def iso_info(main_dir):
    try:
        with open(os.path.join(main_dir, "site", "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        print(f"site/config.json nicht lesbar ({e}) – Releases ohne ISO-Angaben", file=sys.stderr)
        return {}, "https://github.com/Panther92/VoidStation"
    iso = cfg.get("iso") or {}
    if not (iso.get("version") and iso.get("url")):
        iso = {}
    return iso, cfg.get("github", "https://github.com/Panther92/VoidStation").rstrip("/")


def notes(version, entry, iso, github):
    out = [f"**Released:** {entry['date']} · German changelog: "
           f"[CHANGELOG.md]({github}/blob/stable/CHANGELOG.md)", "", "## What's new", "", entry["body"], "",
           "## Download", ""]
    if iso.get("version") == version:
        base = re.sub(r"/download/?$", "", iso["url"])
        name = base.rsplit("/", 1)[-1]
        size = f"{iso['size_mb'] / 1000:.1f} GB" if iso.get("size_mb") else ""
        built = f"built {iso['date']}" if iso.get("date") else ""
        meta = ", ".join(x for x in (size, built) if x)
        out += [f"**Live ISO:** [{name}]({iso['url']})" + (f" ({meta})" if meta else "") + " – hosted on SourceForge", ""]
        if iso.get("sha256"):
            out += [f"SHA-256: `{iso['sha256']}`", ""]
        out += [f"Checksum and signature: [{name}.sha256]({base}.sha256/download) · "
                f"[{name}.sha256.sig]({base}.sha256.sig/download) – "
                f"[how to verify]({github}#verifying-the-download)", ""]
    else:
        out += ["This version has no ISO of its own. Install the latest live ISO from "
                f"[voidstation.de]({SITE}) and update under *Settings → Updates*.", ""]
    out += ["## Updating", "",
            "Devices on the *Stable* channel get this version under *Settings → Updates* (or with `vsctl update`).", "",
            "> To install VoidStation, use the live ISO – the source code archives below are for developers.", ""]
    return "\n".join(out)


def gh(*args, check=True, capture=True):
    return subprocess.run(["gh", *args], check=check, text=True,
                          stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)


def main():
    ap = argparse.ArgumentParser(description="GitHub-Releases aus CHANGELOG und site/config.json pflegen")
    ap.add_argument("--stable", required=True, help="Checkout des Zweigs stable")
    ap.add_argument("--main", required=True, help="Checkout des Zweigs main (fuer site/config.json)")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Panther92/VoidStation"))
    ap.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts bei GitHub aendern")
    ap.add_argument("--exists", default="", help="nur mit --dry-run: Versionen, die als vorhanden gelten (Komma-Liste)")
    a = ap.parse_args()

    order, entries = changelog(os.path.join(a.stable, "CHANGELOG.en.md"))
    if not order:
        sys.exit("CHANGELOG.en.md (stable): keine Version gefunden")
    stable_ver = order[0]
    sha = subprocess.run(["git", "-C", a.stable, "rev-parse", "HEAD"], check=True, text=True,
                         stdout=subprocess.PIPE).stdout.strip()
    iso, github = iso_info(a.main)
    fake = {v.strip() for v in a.exists.split(",") if v.strip()}

    def body_of(tag):
        if a.dry_run:
            return "" if tag[1:] in fake else None
        r = gh("release", "view", tag, "--repo", a.repo, "--json", "body", check=False)
        return json.loads(r.stdout)["body"] if r.returncode == 0 else None

    todo = [stable_ver]
    if iso.get("version") and iso["version"] != stable_ver:
        todo.append(iso["version"])

    for ver in todo:
        tag = f"v{ver}"
        entry = entries.get(ver)
        if not entry or not entry["body"]:
            print(f"{tag}: noch nicht auf stable (kein Eintrag in CHANGELOG.en.md) – kommt mit der Freigabe")
            continue
        text = notes(ver, entry, iso, github)
        old = body_of(tag)
        if old is None:
            if ver != stable_ver:
                print(f"{tag}: noch nicht freigegeben (kein Release) – ISO-Angaben kommen mit der Freigabe")
                continue
            print(f"{tag}: lege Release auf {sha[:7]} an")
            if a.dry_run:
                print(text)
                continue
            gh("release", "create", tag, "--repo", a.repo, "--target", sha, "--title", f"VoidStation {ver}",
               "--notes", text, "--latest", capture=False)
        elif old.strip() == text.strip():
            print(f"{tag}: aktuell")
        elif iso.get("version") != ver:
            # config.json kennt nur die neueste ISO – aeltere Releases behalten ihren Download-Abschnitt
            print(f"{tag}: besteht, keine neue ISO dafuer – unveraendert")
        else:
            print(f"{tag}: aktualisiere den Text")
            if a.dry_run:
                print(text)
                continue
            gh("release", "edit", tag, "--repo", a.repo, "--notes", text, capture=False)


if __name__ == "__main__":
    main()
