# Features

Everything you need from the couch – on a small PC next to the TV, with no account and no ads in the system.

## Screenshots {#screenshots}

{{screens}}

## Interface {#interface}

- Tiles in the style of Windows 8, sorted into groups – add your own tiles
- Control it with a gamepad, remote, mouse or keyboard; controllers from Xbox, PlayStation, Nintendo, 8BitDo & co., plain USB pads and joysticks – also via Bluetooth, pairing without a keyboard
- On-screen keyboard for every input field – in Firefox and on YouTube too
- Themes: Dark, Light, High contrast and Nord; your own themes as a single CSS file
- Adjustable scaling and resolution, 60 Hz preferred
- 13 languages: German and English maintained by hand, plus Español, Français, Italiano, Latviešu, Magyar, Nederlands, Polski, Português (Brasil), Ελληνικά, Русский and Українська (machine-translated) – date, time and numbers in the language's format, launched programs follow
- Several programs at once – <kbd>Guide</kbd> or <kbd>Win</kbd> takes you back to the start screen from anywhere, with the mouse via the bottom right corner
- Controller as mouse in programs like Firefox, FreeTube or Discord – it switches itself off in games
- Sleep, woken by a USB keyboard, mouse or remote
- Sound: devices like “TV · HDMI” or “Headphones · Bluetooth” instead of cryptic profiles, format and microphone per device; new headphones take over the sound if you like

<div class="screens">
<figure><a href="/assets/screens/en/11-ton.webp"><img src="/assets/screens/en/11-ton.webp" alt="Sound: devices instead of profiles" loading="lazy" width="1600" height="900"></a><figcaption>Sound: devices instead of profiles</figcaption></figure>
</div>

## TV {#tv}

- Free-to-air channels from all over the world (channel list by [iptv-org](https://github.com/iptv-org/iptv)), with search, filters by country and topic, an A–Z bar and favorites
- Its own player: switch channels with ▲▼ right in the picture, channel list at the edge of the screen (list, favorites, recent), “Sound & picture” for audio track, subtitles, aspect ratio and quality
- When switching: logo, channel name and – once an XMLTV source is configured – the current and next show
- If a channel can't be reached, VoidStation says why; the player bridges short network dropouts
- The graphics card decodes (VA-API, NVDEC on NVIDIA) – less load, quieter fans
- Pluto TV and the German public broadcasters' media libraries (ARD, ZDF, ARTE) in the AppCenter

<div class="screens">
<figure><a href="/assets/screens/en/7-tv-player.webp"><img src="/assets/screens/en/7-tv-player.webp" alt="TV player with channel info over a scene from Big Buck Bunny" loading="lazy" width="1600" height="900"></a><figcaption>TV: switch channels right in the picture, with program info. Picture: “Big Buck Bunny” © Blender Foundation | <a href="https://peach.blender.org">peach.blender.org</a>, <a href="https://creativecommons.org/licenses/by/3.0/">CC BY 3.0</a></figcaption></figure>
</div>

## Radio {#radio}

- Tens of thousands of stations via [radio-browser.info](https://www.radio-browser.info), with search and favorites
- The radio tile shows the station and current track – the radio keeps playing while you use other tiles

## Videos & Music {#media}

- Library for the shared folder (`share/Videos`, `share/Musik`) and USB drives, with thumbnails and “Continue watching” where you left off
- Videos with audio and subtitle selection, music with cover, track list and “Play all”
- Repeat like on an MP3 player (including “Continue with next folder”) and shuffle
- Album covers arrive by themselves (MusicBrainz, Cover Art Archive), optionally written into the files together with missing tags
- Music and TV keep playing while you're on the start screen or in another program
- **Find music:** free music from the Internet Archive, optionally YouTube and SoundCloud too – as MP3 with artist, album, track number and cover, sorted into `share/Musik`

<div class="screens">
<figure><a href="/assets/screens/en/12-video.webp"><img src="/assets/screens/en/12-video.webp" alt="Video playback with progress bar over a scene from Big Buck Bunny" loading="lazy" width="1600" height="900"></a><figcaption>Videos with audio and subtitle selection. Picture: “Big Buck Bunny” © Blender Foundation | <a href="https://peach.blender.org">peach.blender.org</a>, <a href="https://creativecommons.org/licenses/by/3.0/">CC BY 3.0</a></figcaption></figure>
<figure><a href="/assets/screens/en/8-mediathek.webp"><img src="/assets/screens/en/8-mediathek.webp" alt="The library with album covers" loading="lazy" width="1600" height="900"></a><figcaption>The library with album covers</figcaption></figure>
<figure><a href="/assets/screens/en/9-musik.webp"><img src="/assets/screens/en/9-musik.webp" alt="Music with cover, repeat and shuffle" loading="lazy" width="1600" height="900"></a><figcaption>Music with cover, repeat and shuffle</figcaption></figure>
<figure><a href="/assets/screens/en/10-musik-suchen.webp"><img src="/assets/screens/en/10-musik-suchen.webp" alt="“Find music”: you choose the sources" loading="lazy" width="1600" height="900"></a><figcaption>“Find music”: you choose the sources</figcaption></figure>
</div>

## YouTube and streaming {#streaming}

- Full-screen YouTube (Firefox in kiosk mode)
- Netflix, Prime Video, Disney+, Joyn, RTL+ and Twitch from the AppCenter – copy protection (Widevine) is enabled for them
- Kodi, Jellyfin, Plex HTPC, Spotify and FreeTube from the AppCenter; VLC is still there with one click

## AppCenter {#appcenter}

61 hand-picked apps in seven categories – install and remove with one click:

- **Gaming:** Steam with Proton-GE, Heroic Games Launcher, Lutris, itch, Prism Launcher (Minecraft), Moonlight, Steam Link, Discord
- **Emulators:** DuckStation, PCSX2, PPSSPP, Dolphin, Cemu, Flycast, mGBA, melonDS, Azahar, Snes9x, Nestopia, Rosalie's Mupen GUI, MAME, DOSBox Staging, ScummVM, VICE, Stella, RetroArch
- **Games:** SuperTuxKart, SuperTux, Neverball, Luanti, Xonotic, Hedgewars, Battle for Wesnoth, OpenTTD
- **Media, streaming, browsers and tools:** from Kodi to LocalSend (send files from your phone)

Native Void packages come first; Flatpak or AppImage only where no Void package exists. “Installed” shows everything on the device – including programs installed from the terminal.

## Games {#games}

- Native Steam from the Void repositories, Proton-GE is kept up to date automatically
- Emulator tiles list the games from the shared folder (`share/ROMs/<system>`) and launch them directly; in the background the game pauses and later continues at the same spot
- DOSBox Staging set up and ready, Game Boy Color in the mGBA tile
- Stream games from your gaming PC with Moonlight or Steam Link

## Updates {#updates}

- One button for everything: Void packages including the kernel, Flatpaks, AppImages, Proton-GE and VoidStation itself
- VoidStation updates are signed – devices only install what the publisher has signed
- Channels **Stable** (for everyone) and **Testing** (new versions first)
- No daily nagging: plain system updates are only flagged after 30, 60 or 90 days; a restart is only requested when it is needed

## Under the hood {#technology}

- [Void Linux](https://voidlinux.org) (glibc, rolling release) with runit, Openbox and PipeWire
- [XLibre](https://github.com/X11Libre/xserver) display server; if the interface fails to start twice, VoidStation repairs itself, then offers a rescue console
- Start screen and player are programs of their own in Python + Qt 6 that draw straight on the graphics card; playback uses [mpv](https://mpv.io). The web interface (WebKitGTK) stays as a fallback
- Windows share `\\<hostname>\share` for movies, music and ROMs; remote access via SSH if you want it
- Live ISO with an installer in the same tile design: whole SSD, next to Windows or Linux, into free space or manual partitioning
