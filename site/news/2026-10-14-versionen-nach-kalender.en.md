# New version numbers: VoidStation follows the calendar

The next VoidStation won't be called 0.16.0 but **2026.11**. From now on, the version number says *when* a version came out – year and month. It comes with a fixed rhythm: an update for everyone every month, a new live ISO every three months.

> Update from October 16, 2026: the first calendar number arrived a month earlier than announced. Three fixes – the subscription import in FreeTube, the colour scheme of programs and the page arrows on the start screen – shouldn't wait until November. Since Stable had no calendar number yet that a hotfix like “.1” could build on, this fix is called **2026.10**. The plan stays the same: the first regular monthly update with new features is 2026.11 in early November, and from now on hotfixes are named as described, 2026.10.1, 2026.11.1 and so on.

## Why? {#why}

**VoidStation is built on a rolling release.** Void Linux gets new packages all the time; there is no “Void 5” or “Void 6”. A VoidStation ISO is therefore always a snapshot: VoidStation plus all Void packages as of the day it was built. For a snapshot, the date is the most honest label – it's what Arch Linux does with its ISOs, and Ubuntu with numbers like 24.04.

**The old numbers promised more than they said.** With 0.15.0 you wonder: is this still a beta? What comes with 1.0? Is 0.16 a big step or a small one? VoidStation improves bit by bit, not in big leaps – a number that hints at milestones doesn't fit.

**You can tell right away how current something is.** 2026.11 and 2027.05 – no need to look anything up to see which is newer and how much time lies in between. That goes for your device as well as for the ISO on the [download page](seite:download).

**A fixed rhythm makes VoidStation more dependable.** The new numbers come with a fixed path for how new things reach you – more on that below.

## How it works from now on {#process}

- **Testing first:** every change lands in the *Testing* channel first and stays there for at least 14 days, on several devices in daily use.
- **Once a month for everyone:** whatever has proven itself in Testing goes out at the beginning of the month to every device on the *Stable* channel – for example as version 2026.11. If nothing is ready in a given month, there is no update; there are no empty versions just for the date.
- **Bugs don't wait:** a bug in Stable doesn't wait for next month. After a short trial, the fix comes right away as a hotfix, e.g. 2026.11.1.
- **A new live ISO every three months:** in February, May, August and November, each shortly after that month's update. The ISO carries the same number as the version it contains – in `voidstation-2026.11-20261108.iso`, the version comes first and the build date last.

## What changes for you? {#for-you}

**Nothing you need to do.** Your VoidStation updates as before under Settings → Updates, and 0.15.0 is simply followed by 2026.11. Old version numbers stay in the history as they are.

If you use the *Testing* channel, you'll see numbers like `2026.11+testing.20261120` there – meaning: the state after 2026.11, last change on 20 November. If you switch from Testing back to Stable, your device waits until Stable has caught up, as before, instead of jumping back to an older version.

The first version under the new scheme is planned for early November, with the first matching live ISO shortly after. If you want to know exactly how versions are made, it's all in [RELEASING.md on GitHub](https://github.com/Panther92/VoidStation/blob/main/RELEASING.md).
