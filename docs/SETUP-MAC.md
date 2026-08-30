# Setting up the Mac

The Mac half is optional — the Shortcut works on its own — but it is what makes
the setup forgiving. It watches one folder and quietly fixes up anything that
arrives by a route other than the Shortcut.

## Install

```bash
git clone https://github.com/s08kumar/AUto-Printing-iOS.git
cd AUto-Printing-iOS
./mac/install.sh
```

That creates the library and `_Inbox` folders, writes
`~/.config/article-filer/config.json`, and registers a launch agent that starts
at login and keeps running.

macOS ships a suitable Python, so there is nothing to install. To use a
different one:

```bash
PYTHON=/opt/homebrew/bin/python3 ./mac/install.sh
```

## Grant Full Disk Access — required

macOS keeps `~/Library/Mobile Documents` (which is iCloud Drive) behind Full
Disk Access. Without it the watcher starts, reports itself as running, and
files nothing at all — there is no error, because the folder simply reads as
empty.

1. System Settings → Privacy & Security → **Full Disk Access**
2. Click **+**, press ⌘⇧G, enter `/usr/bin/python3`, add it, switch it on.
3. Add **Terminal** as well
   (`/System/Applications/Utilities/Terminal.app`), so running
   `article-filer` by hand works too.
4. Restart the watcher:
   `launchctl kickstart -k gui/$UID/com.articlefiler.watcher`

`install.sh` checks this and tells you if it is missing. Nothing is lost while
it is: files wait in the inbox until the watcher can read them.

## Check it

```bash
python3 -m articlefiler doctor
```

It reports on the folders, whether the library really is inside iCloud Drive,
how many articles are waiting, and the exact path to set in the Shortcut.

## Everyday use

Drop anything into `_Inbox` and it gets renamed and filed within a few seconds:

- Safari's **Export as PDF** output
- a PDF someone AirDropped you
- a download that arrived as `document-3.pdf`

To file something without moving it there first:

```bash
python3 -m articlefiler file ~/Downloads/*.pdf
python3 -m articlefiler file -n ~/Downloads/x.pdf     # dry run, changes nothing
```

For a right-click option in Finder, see [../mac/quick-action.md](../mac/quick-action.md).

## The Shortcut on the Mac

The same Shortcut syncs to the Mac and works there too. In the Shortcuts app,
tick **Use as Quick Action → Services Menu**, and it appears in Safari's Share
menu and in the Services menu of any app.

Safari on the Mac is the best route of all: you are signed in to your
subscriptions, so what gets rendered is the real article.

## Filing an article: use Safari's own export

Shortcuts' **Make PDF** action renders a live page in its own web view, and on
a heavy news site — ads, lazy-loaded images, infinite scroll — it can stall
indefinitely. A stalled shortcut shows a spinner in the menu bar and never
finishes.

Safari's **File → Export as PDF…** has no such problem: the page is already
rendered and signed in to your subscription. It is what produced every article
filed so far.

Make it a keystroke:

```bash
./mac/safari-pdf-hotkey.sh          # Cmd-Shift-P, then restart Safari
```

Or by hand: System Settings → Keyboard → **Keyboard Shortcuts** → **App
Shortcuts** → **+**, Application **Safari**, Menu Title `Export as PDF…`
(the ellipsis is one character — copy it), and pick a key.

Then filing an article is:

1. **⌘⇧P**
2. **Return** — the save dialog remembers `_Inbox` from last time

The watcher renames it to `NYT - Headline.pdf` and files it within seconds.
Two keystrokes, and every part of it is proven.

## Reaching a Shortcut quickly

A Shortcut is not in Safari's Share menu by default, and hunting for it in the
Shortcuts app every time defeats the purpose. In rough order of how little
effort each costs you:

**A keyboard shortcut — best.** In the Shortcuts app, select **File Article**,
open the details pane on the right (⌘⌥1 if it is hidden), and click **Add
Keyboard Shortcut**. Press something free, such as ⌃⌥⌘F. From then on, one
keystroke on any Safari page files the article. No menus at all.

**In the Share menu.** Safari's Share menu only lists share extensions you
have enabled. Click **Edit Extensions…** at the bottom of that menu — or go to
System Settings → **Privacy & Security → Extensions → Sharing** — and tick
**File Article**. It then appears in the dropdown alongside AirDrop and
Messages.

**In the Services menu.** With **Use as Quick Action → Services Menu** ticked
in the shortcut's details, it appears under **Safari → Services**, and in the
right-click menu on a selection.

**In the menu bar.** Tick **Pin in Menu Bar** in the details pane, and it sits
in the Shortcuts menu-bar icon, one click from anywhere.

The keyboard shortcut is the one worth setting up. The others are there for
when your hands are already on the mouse.

## After updating the code

The launch agent keeps running whatever it imported when it started, so
`git pull` alone changes nothing about its behaviour:

```bash
git pull && make restart
```

Forgetting this is easy to misread as a fix not working.

## Watching what it does

```bash
tail -f ~/Library/Logs/article-filer.log
launchctl print gui/$UID/com.articlefiler.watcher | head -20
```

Stop or restart it:

```bash
launchctl bootout gui/$UID/com.articlefiler.watcher
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.articlefiler.watcher.plist
```

Remove it entirely — your articles and config stay put:

```bash
./mac/uninstall.sh
```

## Configuration

`~/.config/article-filer/config.json`:

| Key | Default | What it does |
|---|---|---|
| `library` | the iCloud folder | Where filed articles end up |
| `inbox` | `<library>/_Inbox` | Where the watcher looks |
| `template` | `{acronym} - {title}` | Also understands `{date}` |
| `subfolder` | `none` | Or `publication`, or `month` |
| `max_title_length` | `110` | Where long headlines get trimmed |
| `fallback_acronym` | `""` | Prefix for unrecognised publications; empty means no prefix |
| `poll_interval` | `5.0` | Seconds between checks |
| `resolve_redirects` | `true` | Follow `apple.news` and shorteners to find the publisher |
| `extensions` | pdf, png, jpg, heic, … | What the watcher will touch |

After changing `library`, rebuild the Shortcut so the iPhone saves to the new
place:

```bash
make shortcut && ./shortcut/sign.sh 'build/File Article.shortcut'
```

## Destination and Subpath are two different things

Expand the Save File action and it shows:

> Save `PDF` to `Shortcuts`
> - Ask Where To Save
> - Subpath:
> - Overwrite If File Exists

The button in the first line is the **destination folder**, and it arrives set
to `Shortcuts`. **Subpath** is an extra relative path *inside* that
destination — not a place to type where you want the file to go.

Typing a path into Subpath is the trap. `Shortcuts` + a subpath of
`iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist` asks to save into a folder
called "iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist" inside the Shortcuts
folder — arrow character included. Nothing exists there, nothing is created,
and the run reports success.

Set it up as:

1. Click the destination button (`Shortcuts`) and pick, through the picker,
   **iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist Articles → _Inbox**.
2. Leave **Subpath empty**.
3. Leave **Ask Where To Save** off.

It should then read `Save PDF to _Inbox` with Subpath blank.

## The first run asks permission

The first time the Shortcut runs on a given site, macOS asks:

> Allow "File Article" to access 1 Safari item while loading web content on
> "www.nytimes.com"?

Click **Always Allow**. Until you answer, the shortcut sits there waiting —
which looks exactly like a hang, complete with a spinning indicator in the
menu bar. The dialog can also open behind the Safari window, so if a run seems
to stall, look for it before assuming anything is broken.

**Always Allow** is per-site, so expect it once for nytimes.com, once for
wsj.com, and so on. **Allow Once** works but asks again every single time.

The same prompt appears on the iPhone the first time you share from a given
site.

## Troubleshooting

**Nothing gets filed.** Almost always Full Disk Access — see the section
above. `python3 -m articlefiler doctor` now tests this directly and prints the
fix.

**Files sit in `_Inbox` unfiled.** They are probably iCloud placeholders that
have not downloaded yet — `ls -la` shows them as hidden `.name.pdf.icloud`
files. The watcher requests a download and files them on a later pass. If they
never arrive, open the folder in Finder to force iCloud to fetch them.

**A file is named wrong.** Run
`python3 -m articlefiler name --title "the title you expected" --json` to see
which signal it used and why. Usually the publication just needs adding to the
registry.
