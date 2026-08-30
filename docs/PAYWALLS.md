# Paywalls: what works, what doesn't, and what to do about it

This is the one part of the problem that code cannot fully solve, so it is worth
being straight about it.

## The constraint

When a Shortcut runs **Make PDF** on a *link*, iOS renders that link in a fresh
web view belonging to the Shortcuts app. That web view is not signed in to
anything. It does not share cookies with the NYT app, and it does not share
cookies with Safari.

So: share a bare link from the NYT app, and what gets rendered may be the
paywall page rather than the article you were reading.

Nothing in this repository tries to defeat that, and nothing should. What it
does instead is make the two legitimate routes fast.

## Route 1 — Share from Safari (best when it works)

Your NYT, WSJ, FT and Economist subscriptions all include web access, and Safari
keeps you signed in. Read the article in Safari, then **Share → File Article**.

Safari passes the page it has *already rendered* to the Shortcut, so the PDF is
the article you were looking at, subscription and all. This is the route to
prefer, and it is still just one tap.

Getting from the app to Safari is usually one tap too: most of these apps have
**Open in Safari** or **Open in Browser** in the same Share sheet.

A one-off setup that pays for itself: sign in to each paper's website in Safari
once, and tick "keep me signed in". After that Safari stays authenticated for
months.

## Route 2 — Share screenshots (always works)

Screenshot the article in the app — for a long piece, take two or three — then
select them in Photos and **Share → File Article**. The Shortcut turns the
images into a single PDF and names it exactly the same way.

This is paywall-proof, because you are filing pixels you were already looking
at. It is the fallback for anything that route 1 cannot reach: Apple News+
articles, apps with no "Open in Safari", the occasional site that renders badly.

On the iPhone, a full-page screenshot in Safari (screenshot → **Full Page** tab)
captures the whole article in one image, which makes this route much nicer than
it sounds.

## Route 3 — Safari's own Save as PDF (Mac and iPhone)

Safari can export a page to PDF directly: **Share → Options → PDF**, or on the
Mac **File → Export as PDF**. Save it into the `_Inbox` folder and the Mac
watcher renames and files it within a few seconds.

Slower than the Shortcut, but it is the highest-fidelity render, and Safari
helpfully names the file after the page title — which is exactly the signal the
watcher needs to identify the publication.

## What each publication does in practice

Behaviour changes as publishers adjust their own settings, so treat this as a
starting point rather than gospel.

| Publication | Sharing a link from the app | Recommended route |
|---|---|---|
| New York Times | Usually renders the opening paragraphs, then the wall | Safari |
| Wall Street Journal | Usually the wall | Safari or screenshots |
| Financial Times | Usually the wall | Safari or screenshots |
| The Economist | Usually the wall | Safari |
| McKinsey | Renders fully — no paywall | Link is fine |
| Harvard Business Review | Renders the abstract, then the wall | Safari |
| Reuters, Guardian, most Indian dailies | Render fully | Link is fine |
| Apple News+ | Never renders — links are opaque | Screenshots |

## Telling instantly which one you got

```bash
python3 -m articlefiler verify --suspect-only
```

That reads every filed PDF and flags the ones that look like a wall rather
than an article — by page count, size, how much text they actually contain,
and whether that text says things like "subscribe to continue". It is a
heuristic, not proof, but it turns "open forty PDFs to check" into a list of
the two worth opening.

If you file a lot from one publication, do the test once. Whatever that paper
does, it will do consistently, and you will know which route to use without
thinking about it again.
