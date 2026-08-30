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
