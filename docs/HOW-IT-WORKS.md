# How a publication gets identified

Given a PDF and whatever context came with it, the job is to answer two
questions: *which paper is this from*, and *what is the headline*. Four signals
are consulted, in descending order of trustworthiness.

## 1. The URL

The strongest signal, when there is one. The host is reduced to a comparable
form — scheme, `www.`, port and path removed — and matched against the domains
in `articlefiler/data/publications.json`. The longest matching domain wins, so
`news.example.com` beats `example.com` when both are registered.

Sub-domains match their parent (`ftalphaville.ft.com` → FT) but lookalikes do
not (`notft.com` is not FT).

Link shorteners and aggregators — `apple.news`, `bit.ly`, `t.co`, Google News —
are explicitly excluded, because their domain says nothing about who wrote the
article. For those, the Mac side can optionally follow the redirect to find the
real publisher; that is the only time this tool makes a network request, it only
ever happens for that short list of hosts, and `resolve_redirects: false` in the
config turns it off entirely.

## 2. The page title

Almost every publisher signs its own headlines: `Fed holds rates steady - WSJ`,
`The heat pump decade | Financial Times`. Each publication carries a list of the
names it uses, and the longest matching suffix wins — which is why
`Steel prices - The Hindu BusinessLine` is filed as The Hindu BusinessLine and
not as The Hindu.

This is what rescues Apple News links and screenshots, neither of which carries
a usable URL.

## 3. The PDF's own metadata

Safari and most print-to-PDF paths record the page title in the PDF, and the
article's links survive as annotations inside it. `articlefiler/pdfmeta.py`
reads both, including from Flate-compressed object streams and XMP packets,
using nothing but the standard library.

URLs found this way are ranked by how often they appear, which reliably
separates the article's own address from the site's navigation and advertising
links.

Titles that a PDF producer invented rather than a person wrote — `Untitled`,
`document3`, `Microsoft Word - draft.docx` — are discarded rather than used.

## 4. The existing filename

A file already called `NYT - Old article.pdf` is recognised as such and left
alone. This makes the whole thing idempotent: running the filer twice over the
same folder changes nothing the second time, and a file that iOS renamed to
`NYT - Old article (2).pdf` on a collision is still understood.

## Building the filename

The winning title is then:

- HTML-decoded (`&rsquo;` → `’`) and Unicode-normalised;
- stripped of the publisher suffix;
- made filesystem-safe — `:` and `/` become `-`, since they carry meaning in a
  headline, while `? " < > | *` and control characters are removed;
- collapsed to single spaces, and truncated at a word boundary (110 characters
  by default), with no trailing comma left dangling.

Then `{acronym} - {title}.pdf`. If no publication was identified, the template
collapses cleanly to `{title}.pdf` rather than leaving ` - Headline.pdf`.

## Filing

The file is moved into the library. If something is already there under that
name, the contents are compared: an identical file means you filed the same
article twice, and the duplicate is dropped; a different file gets ` (2)`.

Files that iCloud has not yet downloaded appear as hidden `.name.pdf.icloud`
placeholders. Those are recognised, left alone, and a download is requested;
they get filed on a later pass once the bytes have actually arrived.
