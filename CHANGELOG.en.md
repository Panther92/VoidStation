# Changes

English version of `CHANGELOG.md`, shown in the update dialog when the interface is set to English.
Same format and the same headings as the German file, followed by bullet points.

Calendar versions (since 2026.11): `## 2026.11 – 2026-11-07` (the November release train),
hotfixes to it `## 2026.11.1 – …`. New changes go first under `## Testing – <date of the last change>`
at the top; `vspub --release` or `vspub --hotfix` assigns the number when releasing (see `RELEASING.md`).
Older versions (up to 0.15.0) still use the old numbering.

## Testing – 2026-10-28
- **Button mapping and game list for the remaining emulators**: PCSX2 (PlayStation 2), Rosalie's Mupen GUI (Nintendo 64), Azahar (Nintendo 3DS), Cemu (Wii U), MAME (arcade), DOSBox Staging (DOS) and RetroArch get the game list with “Button mapping” – each with a sketch of its controller (N64 pad, DualShock 2, 3DS, Wii U GamePad, arcade panel, keyboard, RetroPad). VoidStation writes the mapping into the emulator's settings before every start (formats checked against the source of the Flathub or Void builds); as before, your own mapping always applies, the default only as long as nothing was changed in the emulator. In RMG this is what plugs the controller in at all; the C buttons start out on the right stick (which also counts when asking for buttons). Extras: save states and fast forward through the emulators' keys – where they have none, VoidStation sets them (PCSX2: hold turbo on Tab, Azahar: Shift+F1/F1, turbo F12). In RMG and Azahar fast forward turns on when pressed and off when released. **DOS**: the controller types on the keyboard (Space, Ctrl, Alt, Shift, Enter, Esc, Y/N, Tab, F1, arrows) – VoidStation presses the keys while DOSBox is in front. Cemu has no save states. Texts in all 13 languages
- **New in the AppCenter: xemu (original Xbox)**. Games from `share/ROMs/xbox` (XISO images) start from the game list, button mapping with an Xbox pad (White/Black on L1/R1 at first), save states via snapshots (Shift+F5 save, F5 load). Xenia (Xbox 360) doesn't run usefully on Linux and is therefore not included
- **BIOS in a folder per system**: BIOS files go into `share/ROMs/<system>/bios` – each emulator only reads its own folder, so files of the same size from different consoles no longer get in each other's way. Required for PlayStation (`psx`), PlayStation 2 (`ps2`) and Xbox (`xbox`): the game list of DuckStation, PCSX2 and xemu tells you when something is missing – for xemu separately MCPX boot ROM, flash BIOS and hard disk image. Optional for Dreamcast (Flycast, file `dc_boot.bin`), Nintendo DS (melonDS, ARM9 and ARM7 BIOS plus firmware together), Game Boy Advance and Game Boy (Color) (mGBA, folders `gba` and `gbc`). Each of these folders holds a note “BIOS required – README.txt” or “BIOS optional – README.txt” in the interface language saying what belongs there and what it brings. Names don't matter (except for Flycast): VoidStation recognises the files the way the emulators do and points the emulator at them when a game starts, as long as it finds nothing in its own folder. Files from the previous folder `share/BIOS` (PlayStation 1/2, Xbox) are moved to their new place once. PCSX2: after setup, VoidStation also enters the BIOS file itself if none is selected (setup wizard finished without a BIOS); companion files of a dump (`.rom1`, `.nvm` …) don't count as a BIOS of their own. Note: in PCSX2's setup wizard the folder can't be picked with “Browse…” – just finish the wizard without a BIOS, everything is set on the next start. If you did pick a folder there, the settings hold a document-portal path (`…/doc/…`) that the Flatpak itself can't see – VoidStation now replaces such paths (PCSX2, DuckStation, xemu)
- **Covers in the music collection**: the search now understands files from YouTube & co. – “Artist_-_Title_Lyrics.mp3”, additions such as “(Official Video)”, “Live at …”, “Remastered 1996” or “ft. …”, lost apostrophes (“Fat Larry s Band”) and title tags with the channel as artist (“Royals - Lorde (Lyrics)” by “Pillow”: both orders are tried). If MusicBrainz finds nothing or is overloaded, VoidStation searches iTunes – which also finds titles without an artist such as “Funkytown”. When MusicBrainz answers “503”, VoidStation waits and, after several failures, pauses it for 15 minutes instead of letting every track fail; such tracks don't count as “nothing found”. Embedded video stills (wider than tall) are replaced by the real cover in the display as soon as one is found – the picture in the file stays as it is. “Load all covers” now also counts the individual tracks of loose collections (before: “1 of 1 · 0 found”). Your own picture for a single track: put it next to it with the same name (`Artist - Title.jpg` or `.png`) – it beats everything else. “Search cover again” now only removes what is still in the file exactly as VoidStation wrote it – tags corrected by hand (e.g. with EasyTAG) and a picture you inserted yourself stay. Tiles and the “Up next” list show title and artist from the tags instead of the file name (before e.g. “Original Sin Junior s Earth Mix Edit”); without fitting tags the cleaned-up file name
- **Pictures in the game list now also for DOS, ScummVM and MAME**: for DOS and ScummVM the games are folders – the picture search skipped anything that isn't a file and didn't know the collections for these systems. It searches by folder name (e.g. `mad-tv` → “Mad TV”), for MAME by game title instead of set name. Your own picture may also sit in the game folder (`cover.jpg`, `folder.jpg`, `box.png` …). The `Cover` folder no longer shows up as a game
- **DOSBox: starting a game matches the basic configuration**: when starting from the game list, C: is also the whole `share/ROMs/dos` share (as without a game) – a game installed inside DOSBox (e.g. to `C:\KQ5`) finds its paths again. Only folders with a long name (copied from a PC, reachable in DOS only as `NAME~1`) become C: themselves. If an older basic configuration already mounts C: itself, the game still starts – before, mounting failed and DOSBox closed again right away. VoidStation now finds the start file in a game folder more reliably: helpers such as DOS4GW, intros, sound setup or packers don't count, and if there are several, the one matching the folder name wins (e.g. `mad-tv` → `MTV.EXE`, `doom` → `DOOM.EXE`). Where that isn't enough, a file `start.txt` in the game folder names the start file, optionally with arguments (e.g. `SIERRA RESOURCE.CFG`). Without a clear start file DOSBox stays at the prompt; start files with a long name are not called (DOS can't find them). Your own `.conf` files (e.g. from GOG) may mount relative to their folder. Slovak keyboard with the correct DOS code
- Game lists: **PCSX2, RMG, xemu, Azahar and Cemu** read their folders `share/ROMs/ps2`, `n64`, `xbox`, `3ds` and `wiiu` (created on install and update, plus `mame`), games start in fullscreen. **MAME** shows game titles instead of set names (e.g. “Street Fighter II” instead of sf2) and creates its basic settings itself on the first start. **DOS and ScummVM**: folders count as games – DOSBox makes the game folder drive C:, starts the game (if there's exactly one start file; installers don't count) and quits afterwards. **RetroArch** starts games from `share/ROMs/retroarch` with the matching installed core and lists every extension the cores read. **VICE and Stella** now show their games too (C64, Atari 2600). Game pictures now also for PlayStation 2, Xbox and 3DS
- Flatpak emulators now see the `share` folder (RMG couldn't open games from there at all, xemu needs write access to the hard disk image); the save backup now also covers RMG, Cemu, MAME and Azahar save states
- **Button mapping now for every emulator with a game list**: besides mGBA, Nestopia (NES), Snes9x (Super Nintendo), melonDS (Nintendo DS), DuckStation (PlayStation), PPSSPP (PSP), Dolphin (GameCube) and Flycast (Dreamcast) get the “Button mapping” button – each with a sketch of its console that asks for one button after another. Buttons are mapped by position (Nintendo: A right, B bottom; PlayStation: ✕ bottom …), the analog sticks always work too. VoidStation writes the mapping into the emulator's settings before every start – your own mapping from VoidStation always applies, the default only as long as you haven't changed it in the emulator itself. So controllers now work out of the box where the emulators didn't map them at all (DuckStation, Snes9x, Dolphin) or only partly (PPSSPP: L/R). Extras as in mGBA: save/load state (hold) and fast forward – free at first on consoles that need every button of the controller; Flycast fast forward only (save states via its menu on Select). Where the emulator has no keys for them, VoidStation sets them (Snes9x: Shift+F1/F1/Tab, PPSSPP: F2/F4, melonDS and Nestopia: fast forward on Tab). DuckStation picks up the mapping once it has been set up. The game list of these emulators now also opens without games (with “Start emulator without game” and “Button mapping”). Texts in all 13 languages
- New under **Settings → Display**: **“Match refresh rate to video”** (off by default). While a video, TV, a DVD or YouTube Light is playing in front, the screen switches to its frame rate – 25/50 fps (European channels) to 50 Hz, 23.976 fps (films) to 23.98 Hz, 29.97 fps to 59.94 Hz. This removes the steady judder of, say, a 50 fps channel on 60 Hz. It only switches when the current resolution offers the rate and the current one doesn't fit anyway; the picture goes black for 1–3 seconds while switching. The home screen, music and leaving the player use the normal refresh rate again. The player's technical overlay (Select) shows when the rate was matched
- Settings → Display: the **refresh rate** can now also be set to a fixed value (“Automatic” = ~60 Hz as before, or e.g. 50 Hz). The resolution list only shows modes with at least ~50 Hz (plus the current and the preferred one), up to eight instead of six – on 4K TVs that report only 30 Hz without “Input Signal Plus”, 1920×1080, for example, used to be missing
- `vsctl` without arguments now lists all commands; new is `vsctl version` (version, build and update channel). In the terminal, Tab completes the commands and, after `vsctl launch`, the tile IDs
- The text console (Ctrl+Alt+F2 …) greets with “VoidStation <version>” instead of “Void” – a custom text in `/etc/issue` is kept
- Windows that Openbox frames itself – dialogs and helper windows, e.g. from emulators (such as “Load state” in mGBA) – now use the colours of the selected tile theme instead of Openbox's light grey default: title bar and border like the tiles, Noto Sans font, the close button turns red on hover. Switching the theme applies to open windows right away
- More comfortable terminal: **Tab** now also completes commands, options and package names (e.g. `xbps-install fire` + Tab; new package bash-completion). **↑/↓** search the history for what you've already typed (`ls` + ↑ only shows earlier `ls` commands; on an empty line it works as before). The history keeps 10,000 commands without duplicates and no longer gets lost with several terminals open. New prompt `paul@Wohnzimmer ~/share $` in petrol (red as root); after an error the exit code is shown in red before it. Plus `ll`, `la`, `..` and coloured output for `ls`, `grep`, `diff` and `ip`. Applies to every terminal and over SSH; your own settings in `~/.bashrc` take precedence – only Void's default prompt line there is commented out once
- The terminal follows the theme (light/dark) with calmer colours, announces 256 colours (htop, nano & co. look better) and keeps 10,000 lines of scrollback; the cursor is now a blinking vertical bar instead of a block. **Ctrl +** / **Ctrl −** change the font size, **Ctrl 0** resets it. The tile, Ctrl+Alt+T and terminal programs such as the system monitor now use the same font (DejaVu Sans Mono); the fixed colours in these tiles are dropped by the update
- nano shows syntax colours and line numbers (your own settings in `~/.nanorc` take precedence)
- The system now identifies itself as **VoidStation**: `fastfetch` and other tools show “VoidStation <version>” instead of “Void Linux”, and fastfetch shows the VoidStation logo (four tiles with a V). This comes from a separate `/etc/os-release` (ID `voidstation`, based on `void`); Void's original stays in `/usr/lib/os-release`, and system updates don't overwrite the file. Your own fastfetch settings in `~/.config/fastfetch/config.jsonc` take precedence
- mGBA game list: new **“Mute game”** switch – the emulator stays silent, e.g. while a podcast is playing. It flips mGBA's own switch (Audio → Mute), so both always agree; applies from the next game start
- Button mapping: picking a button in the list now offers “Remap”, **“Leave free”** or “Back”. Free buttons do nothing – e.g. fast forward, if it's too easy to hit by accident. “Default” brings them back
- mGBA: save state (△) and load state (□) only trigger when you **hold the button for half a second** – an accidental tap does nothing. Triggers once per press
- New: **Button mapping for mGBA** – in the game list (open the tile) via the “Button mapping” button. The page shows a sketch of the Game Boy Advance; “Map all, one by one” blinks one console button after another, and you press the button on your controller that should do it. Pressing nothing leaves a button as it is, the PS/Guide button cancels. Next to it is the whole mapping (e.g. “A → ○”); picking a button remaps just that one, and if the controller button is already used elsewhere, the two swap. Plus the extras VoidStation handles itself: save state (△) and load state (□), hold to rewind (L2) and fast forward (R2). “Default” restores the defaults. Applies from the next start of mGBA, per controller; the home screen works as before. More emulators will follow, each with its own controller (DuckStation: PlayStation pad etc.). Stored in `~/.config/voidstation/emu-pads.json`
- mGBA with a PS4 controller: ✕ (B) opened the “Load state” window and □ “Save state” – this came from mGBA’s built-in profile for “Wireless Controller”, which counts the buttons as on Windows. VoidStation now turns these two shortcuts off, even if mGBA has already saved the profile itself; your own shortcuts stay. Kept from the profile: **hold L2 = rewind, hold R2 = fast forward**
- Terminal: pasting from the clipboard now works – with Ctrl+Shift+V, Shift+Insert or right-click (L2 on the controller). Until now the terminal only pasted selected text, not what was copied with Ctrl+C (e.g. from Firefox). Selecting text in the terminal also copies it to the clipboard, as does Ctrl+Shift+C
- mGBA: controller mapping fixed – on PS4 controllers and clones A and B were off, and ✕ opened the load dialog (mGBA’s built-in profile for “Wireless Controller” counts the buttons as on Windows). VoidStation now asks SDL which button is where – the same library and controller database mGBA uses – and maps accordingly: ○ = A, ✕ = B, Share/Options = Select/Start. VoidStation’s old, wrong mapping is replaced automatically on the next start; anything you mapped in mGBA yourself stays. For controllers SDL doesn’t know, your own mapping from `~/.config/voidstation/pads.json` (as for the start page) now also applies in mGBA
- mGBA: **△** saves a save state (slot 1), **□** loads it – the message shows at the bottom of the screen
- Games from the game list start in fullscreen (the emulator without a game stays windowed): mGBA and DuckStation with their own fullscreen option, Snes9x, Nestopia, melonDS, Stella, VICE and RetroArch through the window manager. **Hold L3** (press the left stick for about a second) to leave fullscreen in the emulator in front and to go back – for example to reach mGBA’s menus (then R3 for controller as mouse). Only works when an emulator really is in front. Turn off with `"emu_fullscreen": false` in `settings.json`, per tile with `"fullscreen": false` in `tiles.json`. Newly installed: xdotool
- mGBA with sensible defaults: controllers now work out of the box – until now mGBA only knew old Xbox 360 pads, on all others (Xbox Series, DualSense, DualShock 4, Switch Pro, 8BitDo …) A, B, Start and Select were not mapped. Buttons are mapped as arranged on the Game Boy (right button = A, bottom = B), plus L/R, d-pad and left stick. Also: the game state is saved automatically every 10 seconds and on exit and resumed on the next start, rewind is on, sharp pixels (integer scaling, no smoothing). VoidStation only touches what hasn’t been changed in mGBA itself – your own settings and your own controller mapping stay
- Save backups: every 30 minutes and shortly after an emulator closes, the saves go to the share under `Spielstand-Backups/<date_time>` – only if something changed. Backed up: saves next to the games in `ROMs` (e.g. `.sav`, save states `.ss0`–`.ss9`) and the folders of DuckStation, PPSSPP, Dolphin, RetroArch, PCSX2, Flycast, Mednafen, Nestopia and ScummVM. Unchanged files take no space (hard links). All backups of the last 24 hours are kept, then one per day for 30 days. Restore from the PC: copy the file back to where it came from (`LIESMICH.txt` in the folder). Turn off with `"save_backup": false` in `settings.json`
- Game list with pictures: VoidStation looks up the box art of every game online (libretro-thumbnails, the same pictures as in RetroArch) and keeps it under `ROMs/<system>/Cover/<name of the game>.png`. Works best with the usual file names like “Pokemon - Crystal Version (USA, Europe)”; ROM hacks and self-named files often find nothing – put your own picture named like the game into the `Cover` folder (`.png`, `.jpg` or `.webp`), it always wins. Games without a match are looked up again after 14 days. Turn off with `"rom_covers": false` in `settings.json`
- Videos & Music plays DVDs: when a video DVD is in the drive, a “DVD” tile with the disc’s name appears on the library’s start page. It lists the DVD’s titles with length and chapters – on series DVDs usually one title per episode; short intros and warnings are hidden, “Play all titles” plays them in order. Playback continues automatically from the chosen title, X/Y jumps to the next/previous title. Audio tracks, subtitles and aspect ratio (4:3 stays 4:3) work as for videos; the menu can deinterlace (against comb artifacts on series DVDs, costs CPU time). DVD menus themselves don’t work (mpv can’t do them). The “Eject” tile opens the drive. Newly installed: lsdvd; the user is added to the drive’s group (takes effect after the next restart)
- AppCenter on 32-bit computers (experimental): apps that don’t exist there are no longer offered – everything from Flathub (no longer builds 32-bit, e.g. FreeTube, Spotify, Discord, Heroic), Netflix, Prime Video, Disney+, Joyn and RTL+ (Widevine copy protection is 64-bit only), DuckStation, Steam and Prism Launcher. 36 apps remain, including Kodi, Jellyfin, VLC, RetroArch, the emulators from Void, the games and the on-demand services. Nothing changes on 64-bit
- New: **YouTube Light** – YouTube without a browser and without a Google account, built into the VoidStation player and fully usable with the controller. Start page with continue watching, new videos from your own subscriptions, “Watch later” and your subscribed channels; search for videos, channels and playlists; channel pages (videos, live, playlists), playlists with “Play all”, history. Playback via yt-dlp and mpv (H.264 preferred, quality selectable up to 1080p, the video’s subtitles). Subscriptions, history and lists stay on the device; subscriptions can be imported from Google Takeout (also as ZIP), NewPipe and FreeTube – put the file into the share or onto a USB stick. Shorts are left out. On first start a notice appears (YouTube does not explicitly allow third-party players) that has to be confirmed. If a video fails because YouTube changed something, a button downloads the latest yt-dlp directly from the yt-dlp project (with checksum) and keeps it up to date weekly afterwards; “Find music” uses it too. In the AppCenter under Media; on 32-bit computers YouTube Light replaces the YouTube tile (Firefox), which would be too heavy there – on new installations and once on update, in the same place and size (also if YouTube Light was already installed from the AppCenter). On 64-bit the YouTube tile stays
- TV and videos on 32-bit computers (experimental): the player shows the picture via Xv there – the graphics card does the scaling itself, even old chips without a 3D driver (e.g. Radeon 7500/9000 in the ThinkPad T41). VoidStation also installs the matching graphics driver on 32-bit (ATI, Intel, NVIDIA or VIA) and decodes with shortcuts that save noticeable CPU time on old processors. TV starts there with the quality set to “Data saver”
- TV: the chosen quality (Best/Data saver) is now remembered. The technical overlay (Select / I) also names the video output next to the level (e.g. “Level 2 · xv”)
- TV: many channels (e.g. 3sat, ZDF and other HLS streams) couldn't keep up since the new player – the buffer ran dry, the picture stuttered or didn't appear at all. The cause was an automatic-reconnect setting that applied to every single segment of these streams. It has been removed; the player still handles dropouts itself
- Updates and the installation now write everything to disk before showing “Done”. If the computer was switched off hard right after an update (power button, power cut), VoidStation files could be left empty – the home screen then no longer came up
- TV and videos on graphics cards without video acceleration (e.g. old notebooks; the player then shows the picture in a separate mpv window): the picture stayed behind the player and you only heard the sound until you picked the tile a second time. Now the picture comes to the front by itself
- Sound: on slow computers and in the live system there was sometimes no sound – the radio connected but stayed silent, TV channels reported “not reachable” (timeout) and the volume showed “no audio service”. Cause: WirePlumber, which manages sound, ran twice, and one of them got stuck during startup. Now PipeWire starts it exactly once by itself; the home screen also still connects to the sound system if it only becomes ready later (reported by the community)
- Live ISO: a 32-bit version can now be built experimentally (`sudo bash build-iso.sh --arch i686`) – for old computers such as ThinkPads with a Pentium M. It comes without the NVIDIA driver and boot splash and starts with the kernel parameter `forcepae`, which Pentium M processors need (they support PAE but don't report it); the installer carries it over to the installed system and accepts the 32-bit version with as little as 1 GB of memory (64-bit: still 4 GB). The live system creates its writable layer there with OverlayFS – the previous way (device mapper) made the 32-bit boot hang. Boots to the home screen in QEMU; there is no 32-bit ISO to download so far
- AppCenter: the “YouTube TV interface” is gone. It pretended to be a smart TV so that youtube.com/tv would load at all – but Google now only allows that interface on real TVs and otherwise reports that the device is not recognized. If you had installed it, this update removes its tile and browser profile. The regular YouTube tile stays, and so does FreeTube in the AppCenter
- Emulators: a game started from the game list (e.g. mGBA) could no longer be reached after Home/Guide – the tile opened the list again, every further game and “Launch emulator without game” started a new instance, and Y or “Close app” in the corner did nothing. The game now counts as the tile’s running program: the tile shows it as running and A brings it back, Y or the corner close it (the save prompt works like Alt+F4). Emulators also pause while the home screen or another program is in front – until now the game in the background reacted to every button press on the controller. Back in the game it continues exactly where it was. Applies to all emulators from the AppCenter (mGBA, DuckStation, PPSSPP, Dolphin, DOSBox …), not to Steam or online games; can be turned off per tile with `"suspend": false` in `tiles.json`
- Sleep: with a Bluetooth controller connected, VoidStation woke up again right away – the controller loses its connection when the device goes to sleep, and the Bluetooth adapter reported that as a wake-up call. Bluetooth therefore no longer wakes the device (a controller's Home button can't wake a PC anyway); wake it with a USB keyboard, mouse or a remote with a USB receiver. The controller reconnects by itself after waking up. What woke the device, or why going to sleep was aborted, is now written to the log (`launcher.log`)
- Videos & Music: the technical overlay (Select / I) shows format and bitrate for music (e.g. "MP3 · 320 kbit/s"), sample rate, channels and the audio output instead of resolution and dropped frames; videos get an extra "Audio" line
- Settings → Sound now shows devices instead of PipeWire profiles: “TV · HDMI”, “MCHOSE X9 · USB”, “JBL … · Bluetooth” and so on at the top, the active one is marked – previously the profiles of all sound cards were in one long list without device names, with a checkmark per card. Below, only what the chosen device really offers: format (stereo, surround 5.1/7.1; for Bluetooth the codec, e.g. AAC) and microphone on/off. VoidStation remembers format and microphone per device. Bluetooth headphones run in full quality (A2DP) by themselves; the microphone switches to call quality and therefore stays off until you need it. New: “Use new devices automatically” (on by default) – a USB headset that is plugged in or a Bluetooth headset that is switched on takes over the sound; not controllers with a headphone jack (e.g. DualSense via USB) or webcams, and not during boot or right after standby. On first start, HDMI is set to stereo instead of 7.1 once if nobody has picked a format yet: TVs have two speakers, and with 7.1 dialogue easily got lost there. With an AV receiver or soundbar: Settings → Sound → Format
- VLC is removed with this update, tile included – “Videos & Music” takes over. If you need VLC for DVD menus, converting or exotic formats, it is one click away: AppCenter → Media → VLC. If you installed VLC yourself from the AppCenter, you keep it
- Videos & Music: the cover search by artist and title sometimes picked a compilation instead of the original album (e.g. "25 Jahre Spex" instead of "Mellow Gold" for Beck – Loser). Now all hits are ranked together: official studio album before single before EP, compilations, live albums and "Various Artists" last. New in the menu (Start → Playback → More): "Search cover again" – removes what VoidStation wrote into the file itself (cover and added tags, your own stay) and searches again. Also works for files the first version from today already wrote to. Data written by VoidStation is now marked in the file (tag VOIDSTATION). Also, a download or cover search could get stuck if it was started exactly as the previous one finished
- Videos & Music: picking a track in a folder now really starts that track – playback used to begin with the folder's first track. Cover search for files with no tags and no "Artist - Title" in the name (e.g. "Beck loser.mp3"): VoidStation tries the possible splits into artist and title and only takes a hit where both match. Folders with tagged and untagged files side by side count as a loose collection
- Videos & Music: new switch "Save covers in files" on the library start page (off by default). When on, VoidStation writes found covers and missing tags straight into the music files (MP3, M4A, FLAC), so other players and phones show them too. Existing tags are left alone; only missing ones are added – artist, title, album, year and track number from MusicBrainz, otherwise artist and title from the file name. Writing goes through a checked copy (audio and length must match), modification date and permissions are kept; files on read-only drives are skipped. "Load all covers" then goes through the whole collection
- Videos & Music: every track shows its own cover, on its tile too – the one embedded in the file, otherwise the folder's. If a track has none (e.g. in a loose collection), VoidStation looks it up in the background by artist and album on MusicBrainz/Cover Art Archive, without an album tag by artist and title (if need be from the file name "Artist - Title"). It is stored in the cache, not in your files; each album is looked up only once. "Load all covers" now covers loose collections too. If a folder holds tracks from different albums – e.g. everything loose in share/Musik – VoidStation no longer looks for a shared folder cover; a wrong cover.jpg created that way is removed the next time the folder is opened (only if it is exactly the first track's picture, your own covers stay). The "Up next" list on the music screen shows only as many tracks as fit above the hint line instead of covering it
- Videos & Music → "Find music": search for music and download it, similar to ytmdl. The first time you open it you tick the sources yourself – nothing is preselected: "Free music (Internet Archive)" (netlabels, live recordings and albums under Creative Commons or in the public domain, whole albums at once), YouTube and SoundCloud (with a note: only download what you are allowed to). Single tracks become MP3 and get artist, album, track number, year, genre and cover art (via the iTunes search), saved under `share/Musik/Artist/Album/` or `Artist/Singles/`. Several downloads run one after another, progress is shown on each result. Change sources: X or "Sources". New packages: yt-dlp, Node.js (for YouTube), ffmpeg
- Videos & Music: shuffle with X or in the menu (Start → Playback → Order). The current track keeps playing, then the rest of the folder follows in random order; with “Continue with next folder” every new folder is shuffled too. The setting is remembered
- Videos & Music: album covers appear by themselves, similar to the scraper in Batocera. For folders without a picture, VoidStation first uses the cover embedded in the files, otherwise it looks up artist and album (from the tags or the folder names) on MusicBrainz and downloads the cover from the Cover Art Archive. It is saved as cover.jpg in the folder so other players see it too; for read-only folders (e.g. a USB stick) in the cache. Tiles update as soon as a cover arrives. On the library's start page: “Load covers automatically” (on/off) and “Load all covers” for the whole collection, with progress. Artist folders without their own picture show the cover of their first album
- Videos & Music: repeat like on an MP3 player – “Continue with next folder” (when an album ends, the next one starts, across artist folders too), “Repeat folder”, “Folder, then stop” and “Repeat track”. Switch with Y or in the menu (Start); the choice is remembered. The music screen shows folder and mode, ▶ on the last track jumps straight to the next folder
- Videos & Music and TV: go to the start page without quitting – with Guide/Win or via Start → “Go to start page” (also for controllers without a Guide button). Music and TV keep running, a video pauses; meanwhile you can open other apps, e.g. an emulator. The “Videos & Music” tile shows what's playing, and the hint line now mentions Start and Guide everywhere. Starting the radio pauses the music in the player
- Built-in player for TV: switch channels with ▲▼ right in the picture, without going back to the start page. Switching shows the logo, channel name, position in the list and the current and next show (EPG). X opens the channel list at the edge of the screen (list, favorites, recent), Y marks the channel as a favorite, Start opens “Sound & picture” (audio track, subtitles, aspect ratio, quality), ◀▶ change the volume, LB/RB jump to the previous channel. Press B twice to quit TV. Works with controller, keyboard, remote or mouse – in the VoidStation look and in all languages
- TV: a channel that can't be reached now says why (blocked, timeout, stream no longer exists, no internet) instead of simply doing nothing; ▲ jumps straight to the next one. In the channel list it is dimmed and marked with ⚠ for 24 hours. The player bridges short network dropouts instead of giving up
- TV and videos are now decoded by the graphics card (VA-API, NVDEC on NVIDIA) instead of the processor – less load, less heat, quieter fans
- New “Videos & Music” tile instead of VLC: a library for the shared folder (share/Videos, share/Musik) and USB drives, with thumbnails and “Continue watching” where you left off. Videos with audio track and subtitle choice (◀▶ 10 seconds, LB/RB 1 minute), music with cover and track list – play whole folders at once. VLC is still available in the AppCenter
- The radio stops as soon as TV or a video starts
- If the player's display doesn't work on a graphics card, VoidStation steps down by itself – for TV all the way to the previous mpv full screen. Select (or I) shows resolution, decoder and display level in the player for bug reports
- Controller as mouse: in apps like Firefox/YouTube, FreeTube, Discord, VLC or mGBA the right stick moves the mouse pointer (the further, the faster), R2 clicks (hold to drag), L2 right-clicks, the left stick scrolls. In games and emulators it is off by default because the right stick and shoulder buttons belong to the game – R3 (press the right stick) toggles it in any app, a short note in the bottom right shows the state. Turn it off completely: Settings → System → Controller as mouse. No extra program: the start page creates a virtual mouse for this
- Bluetooth: paired devices can be renamed – “Rename” next to “Unpair”, e.g. “PS4 controller” instead of “Wireless Controller”. The name is kept until the device is unpaired; “Original name” (or an empty field) brings back the name the device reports itself
- Game Boy Color: new share folder `share/ROMs/gbc`. The mGBA tile lists the games from `gba` and `gbc` together (Game Boy `.gb` games work in either folder)
- DOSBox Staging starts ready to use: fullscreen, as a 386 with 4000 cycles (Ctrl+F11/F12 change the speed), drive C is the share `share/ROMs/dos`, language and keyboard as set in VoidStation. The base settings (`~/.config/dosbox/dosbox-staging.conf`) are only created if there are none yet – your own settings are kept
- TV: the channel list stopped after 80 channels – in Germany around “F”, so ZDF and others could only be found via search. Now every channel is reachable: an A–Z bar next to the list jumps straight to a letter, and at the end of a letter “Next: …” moves on. Long lists come in pages of 200 channels (e.g. all countries under “T”: about 1,450) with “More channels” at the end and “Back” at the start. Search now also matches names without accents (reported by the community)
- Sleep: ⏻ → Sleep (also under Settings → System). Programs stay open, the radio stops. Wake it with a USB keyboard, mouse or a remote with a USB receiver. Wi-Fi and Bluetooth reconnect on their own afterwards (a community request)
- Back to the start screen with the mouse: push the pointer to the bottom right – it doesn’t have to hit the exact corner, the bottom or right edge just before it is enough (up to about a tenth of the screen height away). While a program is open, a small card in the colour of its tile floats there with “Start screen” (the program keeps running) and “Close app”. Works for every program started from a tile, fullscreen included (a community request)
- Flatpak programs (e.g. FreeTube, Brave): if the program was already running, its tile didn't bring it back to the front, and the start screen kept treating it as “still starting”. Their windows are now recognised at start
- Eleven new interface languages: Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский, Українська – Settings → Language. Date, time and numbers follow the language; programs like VLC and YouTube follow on their next start. The translations are machine-made – corrections are welcome as pull requests. The installer and the boot menu of the stick stay German/English for now
- Calendar version numbers: year and month of the release, e.g. 2026.11. Hotfixes to it are 2026.11.1, 2026.11.2 and so on; the live ISO carries the same number as the version it contains
- The Testing channel shows its state as e.g. “2026.11+testing.20261120” (after 2026.11, last change on 20 Nov). Switching from Testing to Stable still never offers an older update
- Button mapping and “Mute game” are now translated into the eleven other languages too (were English before)

## 2026.10.1 – 2026-10-27
- Updates: the dialog opens right away instead of waiting minutes for the package check. System updates are checked in the background and added to the dialog once that's done. Loading the package lists takes at most 90 seconds per attempt – before, a stalled server could block the check for 5 minutes
- Fastest Void server: before every update VoidStation measures the official Void mirrors (Frankfurt, Helsinki, Fastly, Chicago) and downloads from the fastest – instead of whichever one `repo-default` happens to hand out (today: Helsinki at 270 KB/s). If a server doesn't answer, it switches right away. Your own package source in `/etc/xbps.d` is left alone; check with `sudo voidstation-pkg mirror status`

## 2026.10 – 2026-10-16
- FreeTube and other Flatpak programs: the file dialog only showed an empty home folder – e.g. subscriptions could not be imported. Now a dialog with access to all your folders opens; the program only gets the chosen file. Applies to programs started after the update
- Programs and browsers follow the VoidStation theme: with “System default” as colour scheme in FreeTube and others, it used to be always light, while YouTube and the media libraries were always dark. Now everything is dark with dark themes and light with “Default Light” – Firefox tiles, Chromium, Brave, LibreWolf, GTK and Qt programs. Applies the next time a program starts, some switch right away
- Page arrows at the top right of the start screen: they often only moved the focus frame to the next group without scrolling. Now the next or previous group moves to the left edge; LT/RT and Page Up/Down scroll the same way
- Interface changes sometimes didn't arrive after an update: the start screen kept running a cached older version until Void next updated Qt. It now detects changed files itself

## 0.15.0 – 2026-10-07
- Bluetooth rebuilt: VoidStation now handles pairing itself, no keyboard needed – headphones, controllers and joysticks using “Just Works” are confirmed, older devices that need a PIN automatically get 0000, 1234 or 1111. Until now such devices failed silently
- Keyboards that ask for a code while pairing: the code is shown at the bottom right until pairing is done
- Other devices cannot pair on their own – requests are only accepted during a scan and for 3 minutes after it
- Scanning takes 30 instead of 10 seconds; found devices stay selectable for 3 minutes. If a device has disappeared in the meantime, a short rescan runs before pairing
- Cleaner list: phones, PCs and TVs nearby and devices without a name no longer show up. Instead each entry says what it is (audio, controller, keyboard, mouse) and – where the device reports it – the battery level
- Error messages with a reason (“Device is not responding – is it in pairing mode?” instead of just “Pairing failed”) and a hint on how common devices enter pairing mode (AirPods, PlayStation, Xbox, Switch)
- Headphones: sound switches to them right after connecting
- Two Bluetooth adapters (e.g. a USB dongle in addition to the built-in chip): the newer one is used, the other is switched off. To pick one: put its address in `/usr/local/share/voidstation/bt-adapter`
- Bluetooth blocked by the radio switch: “Turn on” lifts the block
- Controllers that forgot their pairing (reset, other device) pair again without “Unpair” first; headphones reconnect faster
- Start page: plain USB pads without their own driver, joysticks and arcade sticks now control the interface too. Custom mapping via `~/.config/voidstation/pads.json`
- Steam, emulators and SDL games may access controllers from all common brands directly (Sony, Microsoft, Nintendo, Valve, 8BitDo, Logitech, Hori, PDP, PowerA, Thrustmaster, GameSir and more, over USB and Bluetooth) – previously PlayStation only

## 0.14.3 – 2026-10-05
- Old kernels are removed automatically once the system runs fine with the newest kernel (interface up for 10 minutes) – saves about 300 MB per kernel
- Direct boot (EFISTUB): if the firmware rearranges the boot order itself (e.g. always GRUB first), it is left that way instead of being overwritten on every kernel update – GRUB also starts the newest kernel. To force it: `sudo voidstation-efistub --order`

## 0.14.2 – 2026-10-05
- Kernel updates: the yellow “Restart required” notice stayed after restarting because the PC kept booting the old kernel. Direct boot (EFISTUB) now uses one fixed boot entry, “VoidStation EFISTUB”, that stays the same across kernel updates – the new kernel is placed on the EFI partition under a fixed name
- The initramfs no longer contains graphics drivers (they load later anyway) – about 200 MB smaller per kernel; the EFI partition was almost full. Old kernel files are removed from it
- If a kernel doesn’t fit on the EFI partition, GRUB starts automatically with the newest kernel
- Existing devices are switched over during the update (the initramfs is rebuilt once, then restart once)
- If a new kernel still doesn’t start after a restart, Settings → Updates shows a note instead of the permanent notice
- Updates: instead of “Update server not reachable” right after starting, the check now runs immediately; without a network it says “offline – no internet connection”, and the server message only appears when the network is up and the server really doesn’t answer

## 0.14.1 – 2026-10-04
- English interface: the clock shows “2:53 PM” again in the afternoon instead of “14:53 PM”

## 0.14.0 – 2026-10-04
- The installer is now a Qt program as well: the live system and the installation run without WebKit – smooth even with the NVIDIA driver in 4K, mouse included
- All paths as before: whole SSD, next to another system (move the boundary with the d-pad or drag it with the mouse), free space, manual partitioning with GParted; account and hostname via the on-screen keyboard or a real keyboard; “hold A” to install; progress, error page with “Try another way” and log
- “Wi-Fi” in the installer opens the Wi-Fi settings directly
- Stick boot menu: pick the language first (Deutsch / English), then the two boot entries in that language – interface, installer and keyboard start out matching (English with a US keyboard)
- The page arrows at the top right work again (they had no effect with the Qt start page)
- The web interface stays as a fallback: if the Qt interface fails to start three times, it takes over – in the live system too

## 0.13.3 – 2026-10-03
- Wi-Fi: a wrong password now shows “Wrong password? Please enter it again.” instead of the raw nmcli message, the field is cleared and the on-screen keyboard opens again; “network not found”, “not responding” and “no Wi-Fi adapter” are shown in plain words too
- Wi-Fi: connecting with a password replaces an old saved profile for the same network, and a failed attempt no longer leaves a half-made profile behind (it used to block the next attempt)

## 0.13.2 – 2026-10-03
- Keyboard and gamepad no longer jump back to the tile under the mouse pointer – the mouse only sets the focus when it is moved

## 0.13.1 – 2026-10-03
- Wi-Fi: scanning gets enough time for USB adapters (instead of “nmcli not available”), connecting waits up to 90 s; country radio rules (wireless-regdb package, country from the time zone), no random MAC while scanning and no power saving – helps many USB adapters
- Keyboard: the interface uses the layout chosen in the installer (it was always German before, e.g. wrong with a US keyboard)
- elogind no longer restarts every second (“elogind is already running” flooding the console); booting via GRUB without a flood of messages
- Web interface (live system, installer, “Classic”) with the NVIDIA driver: runs in Firefox instead of WebKit – smooth even in 4K
- Live ISO: the boot menu never runs in 4K (barely reacted to keys on some NVIDIA cards), 15 s countdown; the regular entry reliably blocks the NVIDIA driver, and the installer only keeps it when the card really uses it

## 0.13.0 – 2026-10-03
- New start page as a program of its own (Python + Qt 6) instead of a web page in WebKit: draws directly on the graphics card – also with the NVIDIA driver and in 4K – and needs less memory
- Everything as before: tiles, radio, TV with programme info, games, AppCenter, settings, on-screen keyboard and themes, controlled by gamepad, keyboard and mouse
- Settings → System → Interface: switch between “New (Qt)” and “Classic (web)”. If the new interface fails to start three times, the classic one takes over automatically
- The live system and the installer keep the web interface for now

## 0.12.1 – 2026-10-02
- No more dark screen while starting: until the home screen is ready it shows the logo with loading dots – seamlessly following the boot splash
- The home screen starts earlier (no longer waits for audio and the launcher), and the background is dark grey from the start instead of black
- Live ISO: boot splash with logo in BIOS mode (Legacy/CSM) too, instead of text messages

## 0.12.0 – 2026-10-02
- Home screen on NVIDIA cards: the interface picks a suitable rendering path by itself (no DMA-BUF on NVIDIA, no GPU at all if none is available) and steps down to a safer mode after repeated crashes – instead of a black screen with a mouse pointer
- Live ISO: new boot menu with logo in the tile design, just “Start VoidStation Live”, “Start VoidStation Live (NVIDIA only)” and “Reboot” (UEFI and BIOS)
- Live ISO: NVIDIA driver included (GeForce GTX 16xx, RTX 20xx and newer) – only loaded via “NVIDIA only”; the regular entry uses nouveau with GSP firmware
- Live ISO: boot splash with logo
- Installer: installing from “NVIDIA only” keeps the NVIDIA driver; otherwise it is removed along with DKMS and the compiler. Boot splash and GParted stay on the stick

## 0.11.1 – 2026-10-01
- The on-screen keyboard opens for every input field, also on mouse click – and now in Firefox/YouTube too (“FX OSK” extension, works offline)
- PlayStation controllers (DualSense/DualShock) via Bluetooth; the D-pad also works on controllers that report it as an axis
- Logos and tiles can no longer be dragged by accident, no text selection while navigating
- Installer: the size split next to another system can be dragged with the mouse
- Thanks to DevSpeX!

## 0.11.0 – 2026-10-01
- Installation also works in BIOS mode (Legacy/CSM): older PCs and virtual machines with default settings (VirtualBox, QEMU) no longer need UEFI. BIOS mode offers “Use the whole SSD”; installing next to other systems and manual partitioning remain UEFI-only
- An SSD installed in BIOS mode also boots when the firmware is later switched to UEFI (GRUB for both modes)
- The stick's boot menu now offers “Install VoidStation” and the English entries in BIOS mode too
- The installer only requires Secure Boot to be off; the instructions for that are shorter

## 0.10.1 – 2026-10-01
- AppCenter: visible scrollbars next to the categories and the apps, so you can tell there is more; the category list fades out at the bottom when more follows

## 0.10.0 – 2026-10-01
- AppCenter rebuilt: “Installed” and the categories on the left, the apps as tiles on the right – the list scrolls down instead of sideways, and the number of columns adapts to resolution and scaling
- “Installed” shows everything on the device at a glance, grouped by category – including programs installed outside the AppCenter
- Controls: up / down switches the category and shows it right away, right goes into the apps, left goes back; LT / RT (PgUp/PgDn) jumps to the previous / next category from anywhere; the mouse wheel scrolls the list
- Much more choice (60 instead of 22 apps), still curated:
  - Gaming: Heroic Games Launcher, Lutris, itch, Prism Launcher (Minecraft), Steam Link, Discord
  - Emulators: PCSX2 (PS2), Rosalie's Mupen GUI (N64), Azahar (3DS), Cemu (Wii U), MAME (arcade)
  - Games: SuperTuxKart, SuperTux, Neverball, Luanti, Xonotic, Hedgewars, Battle for Wesnoth, OpenTTD
  - Media: Jellyfin, Plex HTPC, Spotify, FreeTube, Strawberry; Kodi now comes with controller support and streaming add-ons
  - Streaming: Netflix, Prime Video, Disney+, Joyn, RTL+, Pluto TV, Twitch
  - Browsers: Firefox (normal, with address bar), Chromium, Brave, LibreWolf
  - Tools: Mission Center, LocalSend (send files from your phone), AntiMicroX (controller mapping)
- Streaming apps with copy protection (Netflix & co.) enable Widevine in their Firefox profile
- The AppCenter opens faster: installation status is checked with one call for all apps instead of one per app

## 0.9.0 – 2026-10-01
- Updates in one place: Settings → Updates → “Update” checks and installs everything in one go – Void packages (incl. the kernel), Flatpaks, AppImages, Proton-GE and VoidStation itself; anything already up to date is skipped
- The AppCenter no longer has update buttons, it is only for installing and removing programs
- Devices now also check for system updates (every 6 hours). New VoidStation versions show up right away and bring pending system updates along; system-only updates are flagged at the bottom right only after 30, 60 or 90 days (default 90, Settings → Updates) – no daily nagging on a rolling release. The confirmation lists all packages
- Updates done in a terminal (`sudo xbps-install -Su`) are detected: finished updates disappear from the display, and after a new kernel “Restart required” appears
- A restart is only requested when it is really needed (new kernel or new VoidStation version)
- New in the terminal: `vsctl update` does the same as the button in Settings, with a live log

## 0.8.3 – 2026-10-01
- Settings adapt to every resolution and scale: long lists (Wi-Fi, Bluetooth) scroll along instead of disappearing under the hint line; long names wrap
- Page titles shrink when space is tight instead of overlapping the page arrows
- Fixed: at large scales (e.g. 2.25× at 720p) opening Radio could hang the interface (endless re-layout loop)

## 0.8.2 – 2026-10-01
- Settings: the top row of tiles is no longer cut off, and the focus frame on the bottom row no longer covers the hint line

## 0.8.1 – 2026-10-01
- Tidier settings: one tile per area (Language, Display, Appearance, Sound, Network, Bluetooth, Shared folder, Updates, System) – each tile shows the current state, Esc / B returns to the overview
- A pending update shows up on the “Updates” tile; U / Select jumps straight there

## 0.8.0 – 2026-09-30
- Themes: Dark, Light, High Contrast and Nord – under Settings → Display
- On-screen keyboard for search fields and the Wi-Fi password – works with a controller, a remote or a keyboard
- Bluetooth: find, pair, connect and unpair headphones and controllers in Settings (restart once after the update)
- Games: emulator tiles list the games from the share (share/ROMs/<system>) and launch them directly
- TV: program guide (EPG) with the current and next show – as soon as an EPG source is set
- Thanks to DevSpeX for this release!

## 0.7.8 – 2026-09-29
- Installer: the user and root passwords are now actually set – before, both accounts were left without a password and sudo and su failed; the installer now checks this and stops otherwise
- Installed system: the live stick's greeting (“root:voidlinux …”) no longer appears on the text console

## 0.7.7 – 2026-09-29
- Installer: the password for the Windows share “share” is now actually set – before, the share stayed locked (error 0x80004005)
- Dialogs with long text (e.g. “What's new”): the text scrolls with ↑ ↓, the mouse wheel or the D-pad, the buttons always stay visible

## 0.7.6 – 2026-09-29
- Intel PCs load the current CPU microcode at boot (intel-ucode) – fixes freezes on older Skylake machines with an old BIOS; also in the live ISO

## 0.7.5 – 2026-09-29
- Installer: the progress screen appears right after holding (large tile with percentage, steps and explanation) – no going back until the restart
- Installer finished: only “Restart now” remains

## 0.7.4 – 2026-09-29
- Installer: “Erase and install” got stuck – fixed
- mGBA is no longer preinstalled but available in the AppCenter (Games); existing installations keep it
- AppCenter: new section “On this device” – programs installed in a terminal can get a tile
- Image viewer (GPicView) with a black background

## 0.7.3 – 2026-09-29
- No more “update” to an older version (e.g. when Stable is still behind the installed version)
- Live system: no update status in Settings

## 0.7.2 – 2026-09-29
- ISO build: the live-system setup script is now executable (fixes the abort at step 7/13)

## 0.7.1 – 2026-09-29
- ISO build: packages that no longer exist in the Void repositories (e.g. mesa-vdpau) are skipped instead of aborting the build

## 0.7.0 – 2026-09-29
- XLibre is now the only display server – the update removes X.Org, and the choice in Settings is gone
- If the interface fails to start twice, XLibre gets reinstalled once; after that a rescue console follows
- Remote access (SSH) can be switched on and off under Settings → System
- The update channels are now called “Stable” and “Testing” in both languages
- htop, nano, fastfetch and the Mousepad editor are now always included
- New: live ISO with an installer in the tile design – whole SSD, next to Windows or Linux, into free space, or partition manually with GParted

## 0.6.1 – 2026-09-28
- Programs like VLC, the file manager and YouTube start in the selected language
- Arrows at the top right show that there is more to the left or right; one dot per group
- Jump group by group: LT / RT on the controller, Page Up / Page Down on the keyboard
- Update notice at the bottom right with a yellow warning triangle – open it with U or Select on the controller

## 0.6.0 – 2026-09-28
- Language: German or English, switch under Settings → Language · Sprache
- “What's new” is shown in the selected language
- Time, date and numbers in the format of the selected language
- Default tiles are translated too, your own tile names stay as they are

## 0.5.1 – 2026-09-28
- Moved to GitHub (github.com/Panther92/VoidStation) – devices now get their updates from there
- Short command for a fresh install: xbps-fetch https://panther92.github.io/VoidStation/vs

## 0.5.0 – 2026-09-28
- Display server: XLibre instead of X.Org (xlibre-void repository, key pinned)
- Safety net: if the interface fails to start twice, VoidStation automatically switches back to X.Org
- Choose between XLibre and X.Org under Settings → System → Display server

## 0.4.0 – 2026-09-28
- Update channels: “Stable” for everyone, “Testing” to try new versions early
- Updates are signed – devices only install updates with a valid signature
- Automatic update check with a notice on the start page
- Version numbers and “What's new” in the update dialog
- License: GPL-3.0

## 0.3.0 – 2026-09-28
- Update button: VoidStation updates itself from the settings
- Steam natively from the Void repository (nonfree + multilib) with the latest Proton-GE
- The splash screen stays until a program really shows a window
- Resolution: 60 Hz preferred, interlaced modes (1080i) are avoided
- Swap file on computers with less than 8 GB of RAM

## 0.2.0 – 2026-09-27
- New name: VoidStation
- Fresh install of a whole SSD with one command from the official Void ISO
- Screenshots; grids adapt to the space above the hint bar

## 0.1.0 – 2026-09-27
- Tile interface with a WebKit start page, radio, TV, AppCenter, settings
- Samba share, dark theme, large mouse pointer, EFISTUB
