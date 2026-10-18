# Releasing VoidStation

How a change travels from a pull request to every device and onto the live ISO.
The tool for all of this is `tools/publish.sh` (alias `vspub`) on the maintainer's machine.

## Version numbers

VoidStation is built on Void Linux, a rolling release. So version numbers say **when** something was released,
not how big it is:

| Version | Meaning |
|---|---|
| `2026.11` | the release of November 2026 (a regular *release train*) |
| `2026.11.1`, `2026.11.2` | hotfixes to 2026.11 – or, rarely, a second train in the same month |
| `2026.11+testing.20261120` | what *Testing* devices show: the state after 2026.11, last change on 20 Nov 2026 |
| `0.1.0` … `0.15.0` | releases before the switch (October 2026), kept as they are |

The live ISO carries the number of the Stable version it contains, e.g. `voidstation-2026.11-20261108.iso`
(the second part is the build date – a respin with fresher Void packages keeps the version and gets a new date).
GitHub tags are `v<version>`.

Nobody types a version number by hand: `vspub --release` and `vspub --hotfix` assign it when releasing.

## Changelog

`CHANGELOG.md` (German) and `CHANGELOG.en.md` (English) have the same headings. New changes go under a section
at the very top:

```markdown
## Testing – 2026-11-20
- What users will notice, in one line
```

The date is the day of the latest change in that section. When releasing, `vspub` renames the section to
`## 2026.12 – <release date>`; changes that stay in Testing remain under `## Testing`. `build.sh` refuses to
build if the English section is missing, if `Testing` is not at the top or if versions are out of order.

## Channels

| Branch | Channel | Contents |
|---|---|---|
| `main` | *Testing* | everything merged – new features land here first |
| `stable` | *Stable* (default) | released versions only; written by `vspub --release` / `--hotfix`, never by hand |

## Who writes what

Only `vspub` on the publisher's machine builds and signs `dist/` – so code reaches `main` only through `vspub`.

| Change | Way in |
|---|---|
| Code, device files (`launcher/`, `iso/`, install/update scripts, changelog), `tools/`, `.github/` | bundle → `~/share/Updates` → `vspub` (or a pull request, merged and then published with `vspub`) |
| Pure documentation and website (`README*.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `RELEASING.md`, `site/`, `docs/screenshots/`) | may also be pushed to `main` directly; `site/` goes live on voidstation.de right away |
| `stable`, `dist/`, `keys/`, releases, hotfixes, ISO | `vspub --release` / `--hotfix` / `--iso` only, run by the publisher |

`vspub` pulls in anything pushed directly to `main` before applying a bundle, so direct documentation pushes
don't get in its way.

**Building a bundle:** `tools/mkbundle.sh <folder>` – always cumulative (everything since the current GitHub
state, `origin/main..main`), always with the ref `refs/heads/main`, test-applied before it is written. Only the
newest bundle is needed; older ones in `~/share/Updates` can be deleted. Never build one by hand with `HEAD` or a
commit hash as the end point – `vspub` then fails with "Konnte Remote-Referenz main nicht finden".

## Release train (monthly)

Once a month – usually on the first weekend – *Stable* is updated:

1. **Only what has been in Testing for at least 14 days goes along.** Younger changes wait for the next train.
   Only changes that reach the devices count (`launcher/`, `iso/`, install/update scripts, keys, changelog) –
   website or tooling changes don't hold anything up.
2. **Checklist** before releasing, on both reference devices (Intel: Esprimo, AMD: NiPoGi):
   update from the previous Stable version, restart, start screen, YouTube, Settings → Updates.
   If the installer changed: a run in QEMU + OVMF.
3. **No blockers:** an open bug that came in with one of the changes stops that change (release an older state
   with `vspub --release <commit>` or fix it first).
4. **Nothing ripe, no train.** No empty releases just because of the calendar.

```sh
vspub --status            # what's in Testing, since when, what is ripe?
vspub --release           # release everything that is ripe as YYYY.MM
vspub --release <commit>  # release exactly this state (e.g. HEAD – warns about anything younger than 14 days)
```

`vspub --release` builds a release commit (changelog section renamed, `dist/` rebuilt and signed), pushes it to
`stable` and merges it back into `main`, so that `main` always contains `stable`. GitHub tag and release follow
automatically (`.github/workflows/release.yml`), as does the version news on voidstation.de.

## Hotfixes

A bug in *Stable* doesn't wait for the train:

1. The fix goes to *Testing* like everything else (`vspub`), with a changelog line under `## Testing`.
2. After 2–3 days on both reference devices: `vspub --hotfix <commit>` (several commits allowed).
   For a boot or update problem, it may go faster – `vspub` warns but lets you continue.
3. `vspub` applies just these commits to `stable`, moves their changelog lines into a new section
   (`## 2026.11.1 – …`) and merges back into `main`.

If the fix doesn't apply cleanly to *Stable* (because it builds on something only in Testing), `vspub` stops
without changing anything – then a separate version of the fix for Stable is needed.

## Live ISO (quarterly)

A new ISO every three months: **February, May, August, November**, about a week after that month's train,
so the Stable version has already been out for a few days.

1. Build **from `stable`**, never from Testing (the build script refuses a Testing state):

   ```sh
   git -C ~/VoidStation fetch -q origin
   git -C ~/VoidStation show origin/stable:dist/build-iso.sh > /var/tmp/build-iso.sh
   sudo bash /var/tmp/build-iso.sh
   ```

2. Test in QEMU + OVMF (UEFI) and BIOS mode, and install on real hardware (NiPoGi).
3. `vspub --iso` – checksum, signature, upload to SourceForge, download page on voidstation.de.

**Respin** outside the schedule when the ISO itself has a problem (installer bug, a Void update breaks the build,
important hardware support): same procedure, same version number, new build date.

## A quarter at a glance

| When | What |
|---|---|
| beginning of November | train → Stable 2026.11 |
| about a week later | ISO 2026.11 |
| beginning of December | train → Stable 2026.12 (no ISO) |
| beginning of January | train → Stable 2027.01 (no ISO) |
| beginning of February | train → Stable 2027.02, then ISO 2027.02 |
| any time | hotfixes `.1`, `.2` … |

## Settings

`vspub` reads a few environment variables, e.g. for a shorter waiting time while testing the tool itself:
`VS_SOAK_DAYS` (default 14), `VS_HOTFIX_DAYS` (default 2), `VS_REPO`, `VS_INBOX`, `VS_KEY`.
