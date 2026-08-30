# Article Filer

One tap in the New York Times, WSJ, FT, McKinsey, HBR or Economist app turns the
article you are reading into a PDF called

```
NYT - What the Fed's Pause Really Means.pdf
```

filed straight into

```
iCloud Drive / NYT-WSJ-Mckinsey-HBR-Economist Articles
```

No print dialog, no "Save to Files" folder picker, no renaming afterwards. The
same thing works on the MacBook and the iMac, because the folder is iCloud and
the Shortcut syncs across all three.

## Start here

**[`docs/FROM-THE-APPS.md`](docs/FROM-THE-APPS.md)** — filing from the NYT,
WSJ, FT and Economist apps, which offer no Print and no PDF. One tap on the
phone shares the link; the Mac renders it in Safari, where your subscription
lives, and files it as `NYT - Headline.pdf`.

## Also

**[`docs/THE-SETUP.md`](docs/THE-SETUP.md)** — what actually works, on both
devices, distilled. Read that first; the rest of this file is background.

## Yes, this can be done — here is the trick

The newspaper apps do not offer **Print**, which is what sends most people
around the houses. But they all offer **Share**, and iOS lets a *Shortcut* sit
in that Share sheet. A Shortcut can do everything the print route was for:
render the article to PDF, work out which paper it came from, build the
filename, and write it into a fixed iCloud folder without asking you anything.

In practice the Shortcut route could not be made to name files correctly, and
Safari's own **Export as PDF** does it perfectly — it names the file after the
page title, which is the one thing that cannot be recovered afterwards. So the
flow is **⌘⇧P → Return** on the Mac, and **Share → Options → PDF** on the
iPhone, with the Mac tool doing the naming and filing.

See [`docs/THE-SETUP.md`](docs/THE-SETUP.md).

## What is in this repository

| Piece | Runs on | What it does |
|---|---|---|
| `shortcut/` | iPhone, iPad, Mac | Generates the **File Article** Shortcut from the publication list — the one-tap path |
| `articlefiler/` | Mac | A small Python tool that renames and files anything that arrives by another route |
| `mac/` | Mac | A launch agent so the Mac tool runs quietly in the background |
| `docs/` | — | Setup, and an honest account of what paywalls do and do not allow |

The two halves share one publication registry
(`articlefiler/data/publications.json`), so the acronym your iPhone picks is the
acronym your Mac agrees with. Add a publication once and both sides learn it.

### One manual step you cannot skip

A generated shortcut can only carry a *subpath* for its Save File action, not
a folder. The device decides what that subpath hangs off, and left alone the
Shortcuts app uses its own local storage — so articles land in *On My iPhone →
Shortcuts →* your folder name, never sync, and cannot be found from the Mac,
while the Shortcut reports success the whole time.

So after importing, bind it once per device: edit the Shortcut, tap the **Save
File** destination, and choose your folder through the picker. That records
the real storage location; nothing written into the file can.

The Mac watcher also drains `iCloud Drive/Shortcuts/<library name>/`, which
covers the case where the subpath resolves there instead.

### Why there is a Mac half at all

The Shortcut handles the common case. The Mac watcher is the safety net for
everything else: a PDF you saved from Safari's own **Save as PDF**, something
you AirDropped, a download that came in with a name like `document-3.pdf`. Drop
any of those into the `_Inbox` folder and they get renamed and filed the same
way. It also fixes up anything the Shortcut had to guess at, because on the Mac
we can read the PDF's own metadata and the links inside it.

It is entirely optional. The iPhone half works on its own.

## Quick start

### On the Mac (5 minutes, once)

```bash
git clone https://github.com/s08kumar/AUto-Printing-iOS.git
cd AUto-Printing-iOS

./mac/install.sh              # folders + config + background watcher
make shortcut                 # builds "build/File Article.shortcut"
./shortcut/sign.sh 'build/File Article.shortcut'
```

Double-click the signed file to add the Shortcut to the Mac, then AirDrop it to
the iPhone — or just let iCloud sync carry it across. Check its **Save File**
destination once it arrives, and re-pick the folder through the picker.

### On the iPhone (2 minutes, once)

Build the Shortcut by hand — it is two actions, and it is the reliable route:

1. **Shortcuts → + → Add Action → Make PDF**, input: **Shortcut Input**.
2. **Add Action → Save File**. Turn **Ask Where to Save** off, then tap the
   destination and pick your `_Inbox` folder **through the picker**.
3. Name it **File Article**, then **ⓘ → Show in Share Sheet** on.

Full walkthrough: [`docs/QUICK-START-BY-HAND.md`](docs/QUICK-START-BY-HAND.md).

A Save File destination cannot be written into a generated shortcut file — it
has to be chosen through the picker on the device. The generated shortcuts in
`build/` are still useful as a starting point for the naming logic, but this
two-action version is what gets you working today, because the Mac does the
naming anyway.

From then on it is one tap. If you use it often, long-press **File Article** in
the Share sheet and drag it to the top so it is always the first thing you see.

### Check it worked

```bash
python3 -m articlefiler doctor
```

## Trying the naming rules without filing anything

```bash
$ python3 -m articlefiler name --url https://www.wsj.com/x --title "Fed holds rates steady - WSJ"
WSJ - Fed holds rates steady.pdf

$ python3 -m articlefiler name --title "Reimagining energy efficiency | McKinsey" --json
{
  "filename": "MCK - Reimagining energy efficiency.pdf",
  "acronym": "MCK",
  "publication": "McKinsey & Company",
  "source": "title-suffix"
}
```

## Adding a publication

Both halves read the same list, so add it once:

```bash
python3 -m articlefiler publications --add DTE "Down To Earth" downtoearth.org.in
make shortcut          # rebuild the Shortcut so the iPhone learns it too
```

`python3 -m articlefiler publications` lists the 31 that ship by default —
NYT, WSJ, FT, Economist, McKinsey, HBR, Bloomberg, Reuters, Nature, Science,
IEA, IRENA, and the Indian dailies among them.

Prefixes are one word with no spaces, because the "already filed" check reads
the prefix up to the first space. `WashPost`, not `Washington Post`.

## Changing the folder or the naming pattern

Everything lives in `~/.config/article-filer/config.json`:

```json
{
  "library": "/Users/satish/Library/Mobile Documents/com~apple~CloudDocs/NYT-WSJ-Mckinsey-HBR-Economist Articles",
  "template": "{acronym} - {title}",
  "subfolder": "none",
  "max_title_length": 110
}
```

- `template` also understands `{date}`, e.g. `"{date} {acronym} - {title}"`.
- `subfolder` can be `none`, `publication` (a folder per paper) or `month`.
- After changing `library`, run `make shortcut` again so the Shortcut saves to
  the new place.

## The first run asks permission

macOS and iOS ask, once per site, whether the Shortcut may access the Safari
item it was handed. Answer **Always Allow**. Until you do, the Shortcut waits
for you — and a waiting shortcut looks identical to a hung one, so check for
the dialog (it can open behind the browser window) before concluding anything
is wrong.

## The one honest caveat: paywalls

A Shortcut renders the page in its own web view, which is **not** signed in to
your subscription. Share a link straight from the NYT app and what gets rendered
can be the paywall rather than the article.

This is a real constraint of how iOS sandboxes things, not something code can
fix — but there are two reliable ways round it, and both are still far quicker
than the current hoops:

1. **Share the rendered page, not the link.** Read the article in Safari (your
   NYT/WSJ/FT subscription includes web access and Safari stays signed in), then
   Share → **File Article**. Safari hands over the page it already rendered.
2. **Share screenshots.** Screenshot the article in the app, then share the
   images to **File Article** — it turns them into a PDF and names it the same
   way. Paywall-proof, because the pixels are already yours.

`docs/PAYWALLS.md` goes through which publication behaves which way, and how to
tell within a second or two which route you are on.

## On the Mac: two keystrokes, no Shortcuts

Shortcuts' Make PDF action can stall indefinitely rendering a heavy news page.
Safari's own **Export as PDF** cannot — the page is already rendered, and
signed in to your subscription. Give it a hotkey:

```bash
./mac/safari-pdf-hotkey.sh      # Cmd-Shift-P
```

Then: **⌘⇧P**, **Return** (the dialog remembers `_Inbox`), and the watcher
files it as `NYT - Headline.pdf`. Every part of that path is proven.

## Reaching a Shortcut in one keystroke

A Shortcut is not in Safari's Share menu until you enable it as a share
extension, and digging it out of the Shortcuts app each time is no better than
the hoops you started with. Give it a keyboard shortcut instead: Shortcuts app
→ select **File Article** → details pane → **Add Keyboard Shortcut** → ⌃⌥⌘F.

One keystroke on any Safari page, and the article is filed. See
[`docs/SETUP-MAC.md`](docs/SETUP-MAC.md) for the Share-menu and Services
routes if you prefer a menu.

## Checking what you filed

```bash
python3 -m articlefiler verify --suspect-only
```

Flags filed PDFs that look like a paywall capture rather than the article —
one page, little text, "subscribe to continue". Worth running occasionally;
see [`docs/PAYWALLS.md`](docs/PAYWALLS.md) for what to do about the ones it
finds.

## Requirements

- iOS 15 or later, macOS 12 Monterey or later.
- Python 3.9+ — the `/usr/bin/python3` that ships with macOS is fine. There are
  no third-party dependencies, deliberately: nothing to install, nothing to
  break at the next OS update.

## Documentation

- [`docs/SETUP-IPHONE.md`](docs/SETUP-IPHONE.md) — the iPhone side in detail
- [`docs/SETUP-MAC.md`](docs/SETUP-MAC.md) — the Mac side, and the background watcher
- [`docs/BUILD-SHORTCUT-BY-HAND.md`](docs/BUILD-SHORTCUT-BY-HAND.md) — build the
  Shortcut yourself in the Shortcuts app, action by action
- [`docs/PAYWALLS.md`](docs/PAYWALLS.md) — what works where, and why
- [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md) — how a publication is identified

## Tests

```bash
make test        # 135 tests, standard library only
```
