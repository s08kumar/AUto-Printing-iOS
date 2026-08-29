# Building the Shortcut by hand

`shortcut/build_shortcut.py` generates the Shortcut for you, and that is the
quick path. But a generated Shortcut is a property list written blind: Apple
changes action parameters between iOS releases, and if an action lands in the
Shortcuts app looking odd, this page is the ground truth. It takes about ten
minutes and it is worth doing once, because afterwards you can adjust anything
you like.

Open **Shortcuts → + → Add Action** and add these in order.

## Set up the Shortcut

Tap the ⓘ button first:

- **Name**: `File Article`
- **Show in Share Sheet**: on
- **Share Sheet Types**: URLs, Safari web pages, Images, PDFs, Text
- **Show in Menu Bar** (Mac): on, if you want it in Finder's Services menu

## The actions

### 1 — Get the article's link

| Action | Setting |
|---|---|
| **Get URLs from Input** | Input: **Shortcut Input** |
| **Get Item from List** | Get: **First Item** |
| **Set Variable** | Name: `ArticleURL` |

### 2 — Reduce the link to a host name

| Action | Setting |
|---|---|
| **Replace Text** | Input: `ArticleURL` |
| | Find (**Regular Expression** on): `^\s*[a-z]+://(?:www\.\|m\.\|amp\.\|mobile\.)?([^/?#:]+).*$` |
| | Replace: `$1` |
| **Set Variable** | Name: `Host` |
| **Replace Text** | Input: `Host`, Find: `^.*?([^.]+\.[^.]+)$`, Replace: `$1` |
| **Set Variable** | Name: `RootHost` |

`Host` is `economictimes.indiatimes.com`; `RootHost` is `indiatimes.com`. The
first is tried before the second, so the Economic Times does not get filed as
the Times of India.

### 3 — Look up the acronym

| Action | Setting |
|---|---|
| **Dictionary** | One row per domain: key `nytimes.com`, value `NYT`, and so on |
| **Set Variable** | Name: `PubMap` |
| **Get Dictionary Value** | Get **Value** for key `Host` in `PubMap` |
| **Set Variable** | Name: `AcronymExact` |
| **Dictionary** | The same, keyed on root domains |
| **Set Variable** | Name: `RootMap` |
| **Get Dictionary Value** | Get **Value** for key `RootHost` in `RootMap` |
| **Set Variable** | Name: `AcronymRoot` |

To fill the dictionaries without typing sixty rows:

```bash
python3 -m articlefiler publications --export-map
```

### 4 — Take whichever lookup answered

There is no `If` block here on purpose — two regular expressions do the same job
and cannot get tangled.

| Action | Setting |
|---|---|
| **Text** | `AcronymExact` ␣ `AcronymRoot` (both variables, one space between) |
| **Set Variable** | Name: `AcronymRaw` |
| **Replace Text** | Input `AcronymRaw`, Find `^\s+`, Replace empty |
| **Set Variable** | Name: `AcronymTrimmed` |
| **Replace Text** | Input `AcronymTrimmed`, Find `\s.*$`, Replace empty |
| **Set Variable** | Name: `Acronym` |

That leaves the first non-empty answer, or nothing at all if neither matched.

### 5 — Clean up the headline

| Action | Setting |
|---|---|
| **Get Name** | Input: **Shortcut Input** |
| **Set Variable** | Name: `RawTitle` |
| **Replace Text** | Strip the paper's own name off the end. Find: `\s*[\|–—·•-]\s*(?:The New York Times\|WSJ\|The Wall Street Journal\|Financial Times\|The Economist\|McKinsey.*\|Harvard Business Review\|Bloomberg\|Reuters)\s*$` |
| **Set Variable** | Name: `TitleNoPublisher` |
| **Replace Text** | Find: `[/\\:*?"<>\|#\[\]]`, Replace: `-` |
| **Set Variable** | Name: `TitleSafe` |
| **Replace Text** | Find: `\s{2,}`, Replace: a single space |
| **Set Variable** | Name: `Title` |

The generator builds that first pattern from the full publication list; the
handful above covers the papers you read most.

### 6 — Compose the filename

| Action | Setting |
|---|---|
| **Text** | `Acronym` ` - ` `Title` |
| **Set Variable** | Name: `NameRaw` |
| **Replace Text** | Find: `^\s*-\s*`, Replace empty |
| **Set Variable** | Name: `NameTrimmed` |
| **Replace Text** | Find: `\s*-\s*$`, Replace empty |
| **Set Variable** | Name: `FileName` |

Those last two matter: if the paper was not recognised you get
`Headline.pdf` rather than a limp ` - Headline.pdf`.

### 7 — Render, name, save

| Action | Setting |
|---|---|
| **Make PDF** | Input: **Shortcut Input**; Include Margin: off |
| **Set Name** | Name: `FileName`; **Don't Include File Extension**: on |
| **Save File** | Destination: `NYT-WSJ-Mckinsey-HBR-Economist Articles` in iCloud Drive; **Ask Where to Save**: **off** |
| **Show Notification** | Body: `FileName` — optional, but useful confirmation |

**Ask Where to Save must be off.** It is the difference between one tap and the
folder-picking you are trying to escape.

## Testing it

Share an article and watch what lands. The two things that usually need a nudge:

- **The name is right but the file is not there** — the Save File destination is
  pointing at the wrong folder. Tap it and re-pick.
- **The name has no acronym** — that publication's domain is not in the
  dictionary. Add a row, or run
  `python3 -m articlefiler publications --add ACR "Full Name" domain.com` and
  regenerate.

Anything that lands with an imperfect name still gets fixed by the Mac watcher
the next time it syncs, so nothing is ever lost.
