# The setup

**Filing from inside the newspaper apps — the actual problem — is in
[FROM-THE-APPS.md](FROM-THE-APPS.md).** The apps have no Print and no PDF, so
the phone shares the link and the Mac renders it. This page covers articles
you are reading in Safari.


Two devices, one route, one folder. This is what works, established by
testing rather than reasoning.

**The rule everything follows:** the filename must be set when the PDF is
made, from the page title. A PDF of a news page cannot be identified
afterwards — it links to a dozen other articles and nothing inside marks which
one it is. Every failed approach here was an attempt to work that out later.

Safari sets the filename from the page title. That is the whole solution.

## Mac

```bash
./mac/safari-pdf-hotkey.sh      # binds Cmd-Shift-P to Export as PDF
```

On any article: **⌘⇧P**, then **Return** — the save dialog remembers `_Inbox`.

## iPhone

> Share → **Options ›** (under the page title) → **PDF** → **Save to Files** →
> `_Inbox`

Three taps more than a Shortcut, and it works.

## Both

Safari renders the page you are already looking at, signed in to your
subscriptions, and names the file after its title. The watcher then renames it
to your convention and moves it into the library within seconds:

```
NYT - Search Continues for 2,400 Missing in Nepal Floods Amid 'Immense' Devastation.pdf
```

```bash
python3 -m articlefiler run --no-settle   # file anything waiting, now
python3 -m articlefiler verify            # articles, or paywall captures?
python3 -m articlefiler explain           # why a file was named what it was
make restart                              # after any git pull
```

## Why not a Shortcut

It would save two taps on the phone. It could not be made to produce a
correctly named file, over many attempts:

- **Make PDF** re-renders the page in a sandboxed web view. On a heavy news
  page it stalls indefinitely — a spinner in the menu bar and no error.
- It names its output with a **UUID**, and supplying a real name needs a
  **Set Name** action whose variable chip reads `Name` whether it refers to the
  Shortcut Input (the page title, wanted) or to the PDF (the UUID it just
  assigned). The two are indistinguishable in the editor, and every attempt
  resolved to the PDF.

The instructions remain in [QUICK-START-BY-HAND.md](QUICK-START-BY-HAND.md)
for anyone who wants to try, but Safari's export is the route to use.

## Paywalls

A Shortcut's web view is not signed in; Safari is. This is a further reason to
prefer it — sharing a bare link from a news app can capture the paywall rather
than the article. For anything Safari cannot reach, screenshot the article in
the app and share the images into `_Inbox`; that is paywall-proof.

`python3 -m articlefiler verify` flags captures that look like walls rather
than articles.
