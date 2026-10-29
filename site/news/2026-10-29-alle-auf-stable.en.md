# From 2026.11 on, every device runs Stable

With VoidStation 2026.11 on November 6, something fundamental changes: the choice between *Stable* and *Testing* disappears from the installer and from the settings. Every VoidStation will run on Stable – including those that were set to Testing until now. Testing is still there, but only for testers, who turn it on in the terminal.

## Why? {#why}

**Testing is the development state.** Whatever gets built lands there right away, untested. That's great for trying things out, but not for a device that should simply work in the evening when you want to watch YouTube or TV after work.

**The installer asked the wrong question.** Someone setting up VoidStation can hardly tell what "Testing" really means – "new versions first" sounds like "better". One click, and the living-room PC runs code nobody has properly tried yet. That's not a decision anyone should have to make in passing.

**Testing only helps if someone reports bugs.** The time in Testing is meant to catch bugs before they reach everyone. That only works if the devices on it report back – and that's exactly who Testing is for now: our own test devices and anyone who wants to help with testing.

## What changes for you? {#for-you}

**You're on Stable** (the default): nothing changes.

**You had picked Testing:** your device switches to Stable by itself with 2026.11. Since 2026.11 contains everything that was in Testing by then, you won't lose anything and don't have to do anything. Until then, Settings → Updates shows "Channel Testing", with a "Switch to Stable" button if you don't want to wait.

**You want to test:** in the terminal, `vsctl channel testing` turns on the development state (VoidStation asks first), `vsctl channel stable` switches back. Please report bugs as an [issue on GitHub](https://github.com/Panther92/VoidStation/issues) – what helps is listed under [Reporting bugs](seite:contribute#bugs).

## Everything at once, just this time {#exception}

Normally a monthly update only takes what has been in Testing for at least 14 days (as described in the [post on calendar versions](/en/news/versionen-nach-kalender/)). So that every device ends up on the same state on November 6, 2026.11 takes everything that's ready by then – just this once. From Tuesday, November 3, nothing new goes in, only bug fixes. From 2026.12 on, the 14 days apply again.

## Schedule {#schedule}

- **Friday, November 6 – VoidStation 2026.11** for everyone, the first big monthly update. What's in it will be in the news as usual once it's out. One new thing up front: updates no longer show a log but a calm screen with three steps – programs updated, new version downloaded and verified, set up.
- **About a week later – the 2026.11 live ISO.** The main news is the installer: it now speaks all 13 languages of the interface instead of just German and English – German, English, Spanish, French, Italian, Dutch, Polish, Portuguese (Brazil), Greek, Latvian, Hungarian, Russian and Ukrainian. New installations always run on Stable.

The translations were made by machine. If something sounds odd in your language, corrections on [GitHub](https://github.com/Panther92/VoidStation) are very welcome.
