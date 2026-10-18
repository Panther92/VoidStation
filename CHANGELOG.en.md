# Changes

English version of `CHANGELOG.md`, shown in the update dialog when the interface is set to English.
Same format and the same headings as the German file, followed by bullet points.

Calendar versions (since 2026.11): `## 2026.11 – 2026-11-07` (the November release train),
hotfixes to it `## 2026.11.1 – …`. New changes go first under `## Testing – <date of the last change>`
at the top; `vspub --release` or `vspub --hotfix` assigns the number when releasing (see `RELEASING.md`).
Older versions (up to 0.15.0) still use the old numbering.

## Testing – 2026-10-18
- Settings → Sound now shows devices instead of PipeWire profiles: “TV · HDMI”, “MCHOSE X9 · USB”, “JBL … · Bluetooth” and so on at the top, the active one is marked – previously the profiles of all sound cards were in one long list without device names, with a checkmark per card. Below, only what the chosen device really offers: format (stereo, surround 5.1/7.1; for Bluetooth the codec, e.g. AAC) and microphone on/off. VoidStation remembers format and microphone per device. Bluetooth headphones run in full quality (A2DP) by themselves; the microphone switches to call quality and therefore stays off until you need it. New: “Use new devices automatically” (on by default) – a USB headset that is plugged in or a Bluetooth headset that is switched on takes over the sound; not controllers with a headphone jack (e.g. DualSense via USB) or webcams, and not during boot or right after standby. On first start, HDMI is set to stereo instead of 7.1 once if nobody has picked a format yet: TVs have two speakers, and with 7.1 dialogue easily got lost there. With an AV receiver or soundbar: Settings → Sound → Format
- VLC is removed with this update, tile included – “Videos & Music” takes over. If you need VLC for DVD menus, converting or exotic formats, it is one click away: AppCenter → Media → VLC. If you installed VLC yourself from the AppCenter, you keep it
- Videos & Music: the cover search by artist and title sometimes picked a compilation instead of the original album (e.g. "25 Jahre Spex" instead of "Mellow Gold" for Beck – Loser). Now all hits are ranked together: official studio album before single before EP, compilations, live albums and "Various Artists" last. New in the menu (Start → Playback → More): "Search cover again" – removes what VoidStation wrote into the file itself (cover and added tags, your own stay) and searches again. Also works for files the first version from today already wrote to. Data written by VoidStation is now marked in the file (tag VOIDSTATION). Also, a download or cover search could get stuck if it was started exactly as the previous one finished
- Videos & Music: picking a track in a folder now really starts that track – playback used to begin with the folder's first track. Cover search for files with no tags and no "Artist - Title" in the name (e.g. "Beck loser.mp3"): VoidStation tries the possible splits into artist and title and only takes a hit where both match. Folders with tagged and untagged files side by side count as a loose collection
- Videos & Music: new switch "Save covers in files" on the library start page (off by default). When on, VoidStation writes found covers and missing tags straight into the music files (MP3, M4A, FLAC), so other players and phones show them too. Existing tags are left alone; only missing ones are added – artist, title, album, year and track number from MusicBrainz, otherwise artist and title from the file name. Writing goes through a checked copy (audio and length must match), modification date and permissions are kept; files on read-only drives are skipped. "Load all covers" then goes through the whole collection
- Videos & Music: every track shows its own cover, on its tile too – the one embedded in the file, otherwise the folder's. If a track has none (e.g. in a loose collection), VoidStation looks it up in the background by artist and album on MusicBrainz/Cover Art Archive, without an album tag by artist and title (if need be from the file name "Artist - Title"). It is stored in the cache, not in your files; each album is looked up only once. "Load all covers" now covers loose collections too. If a folder holds tracks from different albums – e.g. everything loose in share/Musik – VoidStation no longer looks for a shared folder cover; a wrong cover.jpg created that way is removed the next time the folder is opened (only if it is exactly the first track's picture, your own covers stay). The "Up next" list on the music screen shows only as many tracks as fit above the hint line instead of covering it
- Videos & Music → "Find music": search for music and download it, similar to ytmdl. The first time you open it you pick the sources: "Free music (Internet Archive)" is preselected – netlabels, live recordings and albums under Creative Commons or in the public domain, whole albums at once. YouTube and SoundCloud can be added (with a note: only download what you are allowed to). Single tracks become MP3 and get artist, album, track number, year, genre and cover art (via the iTunes search), saved under `share/Musik/Artist/Album/` or `Artist/Singles/`. Several downloads run one after another, progress is shown on each result. Change sources: X or "Sources". New packages: yt-dlp, Node.js (for YouTube), ffmpeg
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
- Sleep: ⏻ → Sleep (also under Settings → System). Programs stay open, the radio stops. Wake it with a USB keyboard, mouse or a remote with a USB receiver, depending on the adapter also with a Bluetooth keyboard. Wi-Fi and Bluetooth reconnect on their own afterwards (a community request)
- Back to the start screen with the mouse: move the pointer all the way into the bottom right corner – while a program is open, a small card in the colour of its tile floats there with “Start screen” (the program keeps running) and “Close app”. Works for every program started from a tile, fullscreen included (a community request)
- Flatpak programs (e.g. FreeTube, Brave): if the program was already running, its tile didn't bring it back to the front, and the start screen kept treating it as “still starting”. Their windows are now recognised at start
- Eleven new interface languages: Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский, Українська – Settings → Language. Date, time and numbers follow the language; programs like VLC and YouTube follow on their next start. The translations are machine-made – corrections are welcome as pull requests. The installer and the boot menu of the stick stay German/English for now
- Calendar version numbers: year and month of the release, e.g. 2026.11. Hotfixes to it are 2026.11.1, 2026.11.2 and so on; the live ISO carries the same number as the version it contains
- The Testing channel shows its state as e.g. “2026.11+testing.20261120” (after 2026.11, last change on 20 Nov). Switching from Testing to Stable still never offers an older update

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
