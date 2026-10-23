# Help

Controls, updates, the shared folder and the most common questions. Something missing? [Ask in the Discussions](https://github.com/Panther92/VoidStation/discussions).

## Getting help {#support}

- **Questions, ideas, experiences:** in the [Discussions on GitHub](https://github.com/Panther92/VoidStation/discussions). In *Q&A*, answers can be marked as the solution, so others find them later.
- **Something is broken:** open an [issue on GitHub](https://github.com/Panther92/VoidStation/issues). What helps is listed under [Reporting bugs](seite:contribute#bugs).

Reading needs no account; posting needs a free GitHub account.

## Controls {#controls}

| | Controller | Keyboard | Mouse |
|---|---|---|---|
| Move | D-pad / left stick | Arrow keys | point, wheel scrolls |
| Open / select | <kbd>A</kbd> | <kbd>Enter</kbd> | Click |
| Back | <kbd>B</kbd> | <kbd>Esc</kbd> / Backspace | Right-click |
| Close program, favorite | <kbd>X</kbd> / <kbd>Y</kbd> | <kbd>Del</kbd>, <kbd>F</kbd>, <kbd>Y</kbd> | ✕ on the tile |
| Next / previous group | <kbd>RT</kbd> / <kbd>LT</kbd> | PgDn / PgUp | Arrows at the top right |
| Volume down / up | <kbd>LB</kbd> / <kbd>RB</kbd> | <kbd>−</kbd> / <kbd>+</kbd> | |
| Open update (when shown at the bottom right) | <kbd>Select</kbd> | <kbd>U</kbd> | Click the notice |
| Power off, sleep | <kbd>Start</kbd> | | ⏻ at the top right |
| Back to the start screen (from any program) | <kbd>Guide</kbd> / Home | <kbd>Win</kbd> | Bottom right corner, then **Start screen** |
| Close a program (from inside it) | | | Bottom right corner, then **Close app** |

**Sleep** (⏻ → Sleep, or Settings → System): programs stay open, the radio stops. Wake it with a USB keyboard, mouse or a remote with a USB receiver (air mouse). Bluetooth deliberately doesn't wake it – a controller drops its connection when the device goes to sleep, and the adapter took that as a wake-up call. After waking, the controller reconnects on its own. If waking doesn't work, look for “Wake on USB” or similar in the BIOS/UEFI; what woke the device, or why sleep was cancelled, is logged in `~/.local/share/voidstation/launcher.log`.

The arrows at the top right appear as soon as a page is wider than the screen; the bright dot marks the current group. Pair Bluetooth gamepads under **Settings → Bluetooth**.

**Controller as mouse:** In programs like Firefox/YouTube, FreeTube or Discord, the right stick moves the mouse pointer (the further, the faster), <kbd>R2</kbd> clicks (hold to drag), <kbd>L2</kbd> is right-click and the left stick scrolls. In games and emulators this is off by itself, because sticks and shoulder buttons belong to the game there. <kbd>R3</kbd> (press the right stick) toggles it in any program; a short notice at the bottom right shows the state. To turn it off completely: **Settings → System → Controller as mouse**.

## TV {#tv}

The *TV* tile opens the channel list with search, filters by country and topic and an A–Z bar. <kbd>A</kbd> tunes in; after that you stay in the picture:

| | Controller | Keyboard / remote | Mouse |
|---|---|---|---|
| Next / previous channel | ▲ / ▼ | ↑ / ↓, PgUp / PgDn, CH+ / CH− | Arrows at the top right |
| Volume down / up | ◀ / ▶ | ← / →, <kbd>−</kbd> / <kbd>+</kbd> | Wheel, − / + at the top right |
| Info (channel, show now and next) | <kbd>A</kbd> | <kbd>Enter</kbd> | Click |
| Channel list (list, favorites, recent) | <kbd>X</kbd> | <kbd>L</kbd> | Double-click |
| Favorite on / off | <kbd>Y</kbd> | <kbd>F</kbd> | ☆ at the top right |
| Previous channel | <kbd>LB</kbd> / <kbd>RB</kbd> | | |
| Sound & picture (audio track, subtitles, aspect ratio, quality) | <kbd>Start</kbd> | <kbd>M</kbd> | Menu at the top right |
| Technical info (resolution, decoder, display level) | <kbd>Select</kbd> | <kbd>I</kbd> | |
| Start screen, TV keeps playing | <kbd>Guide</kbd> | <kbd>Win</kbd> | ⊞ at the top right |
| Quit TV | <kbd>B</kbd> twice | <kbd>Esc</kbd> twice | ✕ at the top right |

If a channel can't be reached, the reason is shown on screen (blocked, timeout, stream no longer exists, no internet). ▲ jumps straight to the next one, <kbd>A</kbd> tries again. Such a channel is then marked with ⚠ in the channel list for 24 hours. Starting TV stops the radio.

## Videos & Music {#media}

The *Videos & Music* tile shows what's in the shared folder under `share/Videos` and `share/Musik`, plus plugged-in USB drives – with thumbnails and album covers. *Play all* plays a whole folder.

**Videos:**

| | Controller | Keyboard |
|---|---|---|
| Pause / resume | <kbd>A</kbd> | <kbd>Enter</kbd>, Space |
| 10 seconds back / forward | ◀ / ▶ | ← / → |
| 1 minute back / forward | <kbd>LB</kbd> / <kbd>RB</kbd> | PgDn / PgUp |
| Volume down / up | ▼ / ▲ | ↓ / ↑, <kbd>−</kbd> / <kbd>+</kbd> |
| Audio & subtitles | <kbd>Start</kbd> | <kbd>M</kbd> |
| Stop – the position is remembered | <kbd>B</kbd> | <kbd>Esc</kbd> |

*Continue watching* lists videos you started; next time VoidStation asks whether to pick up where you left off.

**Music:**

| | Controller | Keyboard |
|---|---|---|
| Pause / resume | <kbd>A</kbd> | <kbd>Enter</kbd>, Space |
| Previous / next track | ◀ / ▶ | ← / → |
| 10 seconds back / forward | <kbd>LB</kbd> / <kbd>RB</kbd> | PgDn / PgUp |
| Volume down / up | ▼ / ▲ | ↓ / ↑ |
| Change repeat mode | <kbd>Y</kbd> | <kbd>F</kbd> |
| Shuffle | <kbd>X</kbd> | <kbd>L</kbd> |
| *Playback* menu (repeat, order, audio, “Search cover again”) | <kbd>Start</kbd> | <kbd>M</kbd> |
| Stop | <kbd>B</kbd> | <kbd>Esc</kbd> |

*Repeat* works like on an MP3 player: **Continue with next folder** (default – at the end of an album the next one follows, across artist folders too), **Repeat folder**, **Folder, then stop** and **Repeat track**. Your choice and the order are remembered.

<kbd>Guide</kbd> / <kbd>Win</kbd> or *Start → Go to start page* (for controllers without a Guide button) takes you to the start screen without quitting: music keeps playing, a video pauses. The tile shows what's playing. Starting the radio pauses the music.

**Album covers** arrive by themselves: first the picture embedded in the files, otherwise VoidStation looks up artist and album on [MusicBrainz](https://musicbrainz.org) and fetches the cover from the [Cover Art Archive](https://coverartarchive.org). On the library's start page:

- **Load covers automatically** (on/off) – for the folders you are looking at.
- **Load all covers** – goes through the whole collection, with progress.
- **Save covers in files** (off by default) – writes found covers and missing tags (artist, title, album, year, track number) into MP3, M4A and FLAC files, so other players and your phone see them too. Existing tags are left alone.

### Find music {#find-music}

Under *Download → Find music* you search for and download music. The first time, you tick where to search yourself – nothing is preselected:

- **Free music (Internet Archive):** netlabels, live recordings and albums under Creative Commons or in the public domain, whole albums at once.
- **YouTube** and **SoundCloud:** single tracks as MP3. Please only download what you are allowed to – use is at your own responsibility, and the platform's terms apply.

<kbd>Y</kbd> jumps to the search field (with the on-screen keyboard), <kbd>A</kbd> downloads a result, <kbd>X</kbd> changes the sources. Downloads run one after another, progress is shown on each result. Single tracks get artist, album, track number, year, genre and cover and end up in `share/Musik/<artist>/<album>/` (without an album in `<artist>/Singles/`).

## Updates {#updates}

**Settings → Updates → Update** is the only update button. It checks and installs everything in one go: Void packages (including the kernel), Flatpaks, AppImages, Proton-GE and VoidStation itself. Your tiles, favorites and settings are kept.

- Devices check shortly after startup and then every six hours. A yellow notice at the bottom right announces a new VoidStation version right away.
- Plain system updates are only flagged once the system hasn't been updated for 30, 60 or 90 days (Settings → Updates, default 90).
- **Update channel:** *Stable* for everyone, or *Testing* if you want new versions first.
- In the terminal, `vsctl update` does the same as the button. `sudo xbps-install -Su` updates only the Void packages – VoidStation notices that.

## Shared folder: files from your PC {#share}

Every VoidStation has a Windows share. On your PC, type `\\<hostname>\share` into Explorer (e.g. `\\livingroom\share`) and log in with the user name and password from the installation. Movies, music, pictures and games go in there: videos into `share/Videos` and music into `share/Musik` (both show up in the *Videos & Music* tile), games into `share/ROMs/<system>`.

## Games and emulators {#games}

Emulators are in the AppCenter under *Emulators*. ROMs go into the shared folder under `share/ROMs/<system>`, for example `gba`, `gbc`, `snes`, `nes`, `psx`, `psp`, `nds`, `gamecube` or `dreamcast`. The emulator tile then shows a game list; without games, the emulator starts directly. The mGBA tile lists Game Boy Color games (`gbc`) together with `gba`; DOSBox Staging starts ready to go with `share/ROMs/dos` as drive C.

A running game belongs to its tile: after <kbd>Guide</kbd> / <kbd>Win</kbd>, the tile brings it back with <kbd>A</kbd>, and <kbd>Y</kbd> or *Close app* in the corner ends it. While the start screen or another program is in front, the emulator pauses and later continues exactly where it was (not for Steam and network games).

## TV program guide {#epg}

The current and next show appear when you switch channels and with <kbd>A</kbd>. Off by default. To turn it on, enter the address of an XMLTV file (`.xml` or `.xml.gz`) – it is downloaded daily:

```
echo 'https://…/epg.xml.gz' | sudo tee /usr/local/share/voidstation/epg-url
```

## Frequently asked questions {#faq}

### Do I need an account?

No. VoidStation does not sign you in to any service. Only streaming apps like Netflix want their own account, of course.

### Does it run on a Raspberry Pi?

No, only on 64-bit PCs (x86_64). A used mini PC or office PC is ideal.

### Can I keep Windows?

Yes: the live ISO installs next to Windows (in UEFI mode). Turn off Fast Startup in Windows first and shut Windows down instead of hibernating it. A short boot menu then appears at startup.

### Where did VLC go?

“Videos & Music” replaces VLC; the update removes VLC along with its tile. If you need VLC for DVD menus, converting or unusual formats, get it back with one click: **AppCenter → Media → VLC**. If you had installed VLC yourself through the AppCenter, you keep it.

### Covers are missing or wrong

Choose **Load all covers** on the library's start page. If a cover is wrong, open **Start → Playback → More → Search cover again** on the music screen: VoidStation removes what it wrote itself (your own covers and tags stay) and searches again. The search works best with tags or file names like `Artist - Title.mp3`.

### The picture stays black or stutters

<kbd>Select</kbd> (or <kbd>I</kbd>) in the player shows resolution, decoder and display level – please add that to every bug report. If playback doesn't work on a graphics card, VoidStation steps down by itself, for TV all the way to a plain full-screen player.

### Which languages are there?

Thirteen: Deutsch, English, Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский and Українська – **Settings → Language**. Apart from German and English, the translations are machine-made; corrections are welcome as a [pull request](seite:contribute#translating). The installer and the stick's boot menu are German and English only for now.

### The interface doesn't start – what now?

After two failed starts, VoidStation reinstalls the XLibre display server once. If it still fails, a rescue console appears. `sudo /usr/local/sbin/voidstation-pkg xserver status` helps there.

### Where are the logs?

In `~/.local/share/voidstation/logs/`. During installation, the installer's log is at `/run/voidstation-installer/install.log` and can be saved straight to a USB stick.

### Is VoidStation an official Void Linux project?

No. VoidStation is an independent project built on Void Linux. Please don't take questions about VoidStation to the Void team – ask [in the Discussions](https://github.com/Panther92/VoidStation/discussions) instead.
