# Filing from the newspaper apps

The NYT, WSJ, FT and Economist apps offer no Print and no PDF. The only thing
they will give you is a link. So the phone shares the link, and the Mac — the
one place signed in to your subscriptions — renders it.

**iPhone: one tap. Mac: nothing, it happens by itself.**

## The iPhone Shortcut — two actions

No Make PDF, and no name to get right: the file is a scrap of text and nothing
cares what it is called.

1. **Shortcuts → + → Add Action → Text**
   - Clear the field, then insert the **Shortcut Input** variable into it.
2. **Add Action → Save File**
   - **Ask Where to Save**: off
   - Destination: pick `_Inbox` **through the picker**
   - Subpath: empty
3. Name it **File Article**, then **ⓘ → Show in Share Sheet**, with URLs and
   Safari web pages ticked.

That is the whole thing. In the NYT app: **Share → File Article.** Done.

## The Mac side

Already installed. The watcher notices the dropped link, opens it in Safari,
waits for it to load, exports it as PDF named after the page title, files it
as `NYT - Headline.pdf`, and deletes the link.

Two permissions are needed the first time, because driving Safari's menus
counts as controlling your computer:

- **System Settings → Privacy & Security → Accessibility** — add and enable
  **Terminal**, and `/usr/bin/python3` for the background watcher.
- An **Automation** prompt appears the first time: allow control of Safari and
  System Events.

Check it:

```bash
python3 -m articlefiler doctor        # says whether rendering is ready
python3 -m articlefiler render 'https://www.nytimes.com/2026/08/30/world/asia/nepal-floods.html'
```

That renders one URL and files it, printing what it did at each step. Do this
once from Terminal before relying on the phone, so the permission prompts
appear while you are watching.

## What this route gets you

- **The article, not the paywall** — Safari is signed in.
- **The real headline** — taken from the page title at render time.
- **One tap on the phone**, from inside the app, with no Print option needed.

## What it costs

- **The Mac must be awake** and logged in. Links dropped while it sleeps are
  filed when it wakes; nothing is lost.
- **Safari comes to the front** for a few seconds per article. It is doing
  real work in a real window, which is also why it can see your subscription.
- **It drives menus.** Apple gives Safari no scripting command for Export as
  PDF, so this clicks the menu item through System Events. If a macOS update
  renames that item, rendering stops with a clear error and
  `EXPORT_MENU_ITEM` in `articlefiler/render.py` is the single line to change.

## If a render fails

The link stays in the inbox and is retried on the next pass, so nothing is
lost. `python3 -m articlefiler run --no-settle` retries immediately and prints
the reason.
