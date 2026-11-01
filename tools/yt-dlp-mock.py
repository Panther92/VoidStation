#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Attrappe fuer yt-dlp: Tests von YouTube Light ohne Netz (tools/qt-preview.py --player yt setzt VS_YTDLP darauf).
Antwortet auf -J/--version wie yt-dlp mit erfundenen, aber gleich aufgebauten Daten:
  ytsearchN:<q>                          Videos (darunter ein Short und ein 50-s-Clip, die YouTube Light ausblenden muss)
  .../results?search_query=…&sp=EgIQAg== Kanaele      sp=EgIQAw== Playlists
  .../channel/<id>/videos|streams|playlists
  .../playlist?list=<id>
  .../watch?v=<id>                       Stream-Adressen: VS_YT_MEDIA (Basis-URL mit v.mp4 und a.m4a); IDs mit
                                         "AgeLimit" bzw. "Outdated" scheitern wie bei YouTube
"""
import hashlib
import json
import os
import sys
import time

WORDS = ["Kochen", "Reise", "Retro", "Linux", "Musik", "Doku", "Technik", "Garten", "Spiele", "Natur", "Physik", "Bahn"]
CHANNELS = [("UCaaaaaaaaaaaaaaaaaaaaa1", "Retro Werkstatt"), ("UCbbbbbbbbbbbbbbbbbbbbb2", "Kochen mit Oma"),
            ("UCccccccccccccccccccccc3", "Linux Ecke"), ("UCddddddddddddddddddddd4", "Bahnfahrten"),
            ("UCeeeeeeeeeeeeeeeeeeeee5", "Natur pur")]


def vid(seed, i):
    return hashlib.sha1(f"{seed}{i}".encode()).hexdigest()[:10].replace("a", "A") + "x"


def video(seed, i, chan=None):
    cid, cname = chan or CHANNELS[i % len(CHANNELS)]
    v = vid(seed, i)
    return {"_type": "url", "ie_key": "Youtube", "id": v, "url": f"https://www.youtube.com/watch?v={v}",
            "title": f"{WORDS[i % len(WORDS)]}: Folge {i + 1} – {seed}", "channel": cname, "channel_id": cid,
            "duration": 180 + i * 97, "view_count": 1234 * (i + 1) ** 3, "live_status": "is_live" if i == 3 else None,
            "thumbnails": [{"url": f"https://i.ytimg.com/vi/{v}/hqdefault.jpg", "width": 480, "height": 360}]}


def out(d):
    print(json.dumps(d))
    return 0


def main(argv):
    if "--version" in argv:
        print("2026.10.10")
        return 0
    url = argv[-1]
    time.sleep(float(os.environ.get("VS_YTDLP_DELAY", "0.3")))
    if url.startswith("ytsearch"):
        q = url.split(":", 1)[1]
        ents = [video(q, i) for i in range(18)]
        ents[2]["url"] = f"https://www.youtube.com/shorts/{ents[2]['id']}"      # Short: muss raus
        ents[5]["duration"] = 50                                                 # kurzer Clip: muss raus
        return out({"_type": "playlist", "id": q, "title": q, "entries": ents})
    if "/results?" in url:
        if "EgIQAg" in url:
            return out({"_type": "playlist", "entries": [
                {"_type": "url", "ie_key": "YoutubeTab", "id": c, "url": f"https://www.youtube.com/channel/{c}", "title": n,
                 "channel_follower_count": 12000 * (i + 1),
                 "thumbnails": [{"url": f"//yt3.ggpht.com/{c}=s88", "width": 88, "height": 88}]}
                for i, (c, n) in enumerate(CHANNELS)]})
        return out({"_type": "playlist", "entries": [
            {"_type": "url", "ie_key": "YoutubeTab", "id": f"PLmock{i}xxxxxxxxxx", "title": f"Playlist {i + 1}",
             "url": f"https://www.youtube.com/playlist?list=PLmock{i}xxxxxxxxxx", "channel": CHANNELS[i][1],
             "thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid('pl', i)}/hqdefault.jpg", "width": 480, "height": 360}]}
            for i in range(4)]})
    if "/channel/" in url:
        cid = url.split("/channel/")[1].split("/")[0]
        name = dict(CHANNELS).get(cid, "Kanal " + cid[-4:])
        tab = url.rstrip("/").rsplit("/", 1)[-1]
        if tab == "playlists":
            ents = [{"_type": "url", "id": f"PLch{i}xxxxxxxxxxxx", "title": f"{name}: Reihe {i + 1}",
                     "url": f"https://www.youtube.com/playlist?list=PLch{i}xxxxxxxxxxxx",
                     "thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid(cid, i)}/hqdefault.jpg"}]} for i in range(3)]
        else:
            ents = [video(name, i, (cid, name)) for i in range(12)]
        return out({"_type": "playlist", "id": cid, "title": f"{name} - {tab.capitalize()}", "channel": name, "channel_id": cid,
                    "channel_follower_count": 54321,
                    "thumbnails": [{"id": "avatar_uncropped", "url": f"https://yt3.ggpht.com/{cid}=s900", "width": 900, "height": 900}],
                    "entries": ents})
    if "playlist?list=" in url:
        pid = url.split("list=")[1]
        return out({"_type": "playlist", "id": pid, "title": f"Playlist {pid[-6:]}", "channel": CHANNELS[0][1],
                    "channel_id": CHANNELS[0][0], "entries": [video(pid, i, CHANNELS[0]) for i in range(8)]})
    if "watch?v=" in url:
        v = url.split("v=")[1][:11]
        if "AgeLimit" in v:
            print(f"ERROR: [youtube] {v}: Sign in to confirm your age. This video may be inappropriate for some users.", file=sys.stderr)
            return 1
        if "Outdated" in v:
            print(f"ERROR: [youtube] {v}: Requested format is not available. Use --list-formats", file=sys.stderr)
            return 1
        base = os.environ.get("VS_YT_MEDIA", "http://127.0.0.1:8799/")
        hdr = {"User-Agent": "Mozilla/5.0 (Mock)"}
        return out({"id": v, "title": f"Testvideo {v}", "channel": CHANNELS[2][1], "channel_id": CHANNELS[2][0], "duration": 30,
                    "is_live": False, "language": "de", "http_headers": hdr,
                    "formats": [{"format_id": str(h), "height": h, "vcodec": "avc1.4d401f", "acodec": "none"} for h in (360, 480, 720, 1080)],
                    "requested_formats": [
                        {"url": base + "v.mp4", "height": 720, "vcodec": "avc1.4d401f", "acodec": "none", "http_headers": hdr},
                        {"url": base + "a.m4a", "vcodec": "none", "acodec": "mp4a.40.2", "http_headers": hdr}],
                    "subtitles": {"en": [{"ext": "vtt", "url": base + "en.vtt", "name": "English"}],
                                  "de": [{"ext": "vtt", "url": base + "de.vtt", "name": "Deutsch"}]}})
    print(f"ERROR: unbekannte Adresse {url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
