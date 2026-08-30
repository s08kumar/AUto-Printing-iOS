# The setup

What actually works, after establishing the hard way what does not. Two
devices, two routes, one folder.

The single rule everything follows: **the filename must be set when the PDF is
made, from the page title.** A PDF of a news page cannot be identified
afterwards — it links to a dozen other articles and nothing inside marks which
one it is. Every failed approach was an attempt to work that out later.

## Mac: Safari's own export

Safari names its export after the page title, renders the page you are already
looking at, and is signed in to your subscriptions.

```bash
./mac/safari-pdf-hotkey.sh      # binds Cmd-Shift-P
```

Then, on any article: **⌘⇧P**, **Return** (the dialog remembers `_Inbox`).

Do not use a Shortcut here. Its Make PDF action re-renders the page in a
sandboxed web view and can stall indefinitely on a heavy news site.

## iPhone: a three-action Shortcut

There is no Export as PDF on iOS, so Make PDF is unavoidable — but the name
must be supplied explicitly, or you get a UUID.

Build it on the Mac (easier to see what you are doing) and let iCloud sync it
across.

| # | Action | Setting |
|---|---|---|
| 1 | **Make PDF** | Input: **Shortcut Input** |
| 2 | **Set Name** | Name: **Shortcut Input → Name**. Don't Include File Extension: on |
| 3 | **Save File** | Destination: `_Inbox`, picked **through the picker**. Ask Where To Save: off. Subpath: empty |

Then **ⓘ → Show in Share Sheet**, with URLs, Safari web pages, Images, PDFs
and Text all ticked.

### The two settings that decide whether this works

**Action 2's variable.** The chip reads `Name` whether it refers to the
Shortcut Input or to the PDF, and they look identical. Shortcut Input's Name is
the page title; the PDF's Name is what Make PDF just produced, which is a UUID
— so binding it there sets the name to itself. Click the chip and check.

**Action 3's destination.** It arrives set to `Shortcuts` with a separate
*Subpath* field below. Subpath is a path *inside* the destination, not a place
to type where the file should go. Pick the folder through the picker; leave
Subpath empty.

### Verifying it, before trusting it

```bash
python3 -m articlefiler explain
```

Shows the most recent files and what the filer makes of them. A UUID filename
means action 2 is bound to the wrong variable. Nothing appearing at all means
action 3 is pointing somewhere else.

## Either way, the Mac finishes the job

Both routes drop a titled PDF into `_Inbox`. The watcher renames it to your
convention — `NYT - Search Continues for 2,400 Missing in Nepal Floods.pdf` —
and moves it into the library within seconds.

```bash
python3 -m articlefiler run --no-settle   # file anything waiting, now
python3 -m articlefiler verify            # articles, or paywall captures?
make restart                              # after any git pull
```

## Paywalls

A Shortcut's web view is not signed in. Sharing a bare link from the NYT app
can therefore capture the wall rather than the article. Two ways round, both
still one tap:

- Read it in **Safari** first (your subscription includes web access) and share
  from there.
- **Screenshot** the article in the app and share the images — Make PDF turns
  them into a PDF without rendering anything, so it is paywall-proof and
  cannot stall.

`verify` tells you which you got.
