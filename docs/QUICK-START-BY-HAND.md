# The two-minute shortcut

Build this by hand in the Shortcuts app. It is two actions, and it gets you
the whole feature: one tap in the news app, a PDF named
`NYT - Headline.pdf` in your iCloud folder.

Why by hand: a Save File destination cannot be expressed in a generated
shortcut file. It has to be chosen through the folder picker on the device,
which records the actual storage location. Everything else can be generated;
that one thing cannot.

## Build it

1. Open **Shortcuts** → **+** (new shortcut).
2. Tap **Add Action**, search **Make PDF**, add it.
   - Set its input to **Shortcut Input** (tap the input field if it does not
     say that already).
3. Tap **Add Action**, search **Save File**, add it.
   - It arrives reading **Save PDF to `Shortcuts`**. That word is the
     destination folder, and it is the default. Click it and pick your folder
     through the picker.
   - Expanding the action also reveals **Subpath**. That is a relative path
     *inside* the destination, not a place to type where the file should go.
     Leave it empty. Typing a path there — especially one copied from a Finder
     breadcrumb, arrows and all — asks for a folder that cannot exist, and the
     save silently does nothing.
   - Turn **Ask Where to Save** **off**.
   - Tap the destination and pick, through the picker:
     **iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist Articles → _Inbox**
   - Picking it here is the step that matters. Do not type a path.
4. Tap the shortcut's name at the top → rename it **File Article**.
5. Tap **ⓘ** → **Show in Share Sheet** on.
   Under **Share Sheet Types**, tick URLs, Safari web pages, Images, PDFs and
   Text.
6. Done.

## If you add a Set Name action

Optional — the Mac can name the file on its own — but it gets you the right
name immediately.

Put **Set Name** between Make PDF and Save File, and in its Name field insert
a variable. The trap is *which* variable: the chip reads `Name` whether it
refers to the Shortcut Input or to the PDF, and they look identical.

- **Shortcut Input → Name** is the page title. Correct.
- **PDF → Name** is the name of the file Make PDF just produced, which has
  none — so it is a UUID, and you end up setting the name to itself.

Click the chip to see which one it is bound to, and switch it if needed.

## Building it on the Mac instead

Easier than on the phone, and it syncs to the iPhone afterwards.

1. Open **Shortcuts** on the Mac → **File → New Shortcut**.
2. Search the right-hand action list for **Make PDF**, drag it in.
   Set its input to **Shortcut Input**.
3. Search for **Save File**, drag it in below.
   - Turn **Ask Where to Save** off.
   - Click the destination and pick, through the file picker:
     **iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist Articles → _Inbox**
4. Rename it **File Article** (double-click the name in the toolbar).
5. In the sidebar on the right: tick **Show in Share Sheet**, and
   **Use as Quick Action → Services Menu**.

Test it straight away: open an article in Safari, **Share → File Article**.
Safari is signed in to your subscriptions, so what gets rendered is the real
article rather than a paywall.

## Delete the generated ones first

`File Article.signed`, `File Article (Simple)` and `File Article (Ask)` will
only confuse matters — and the 45-action one hangs. Remove them from the
Shortcuts app before building this, so there is one shortcut with one name.

## Use it

Open an article, **Share** → **File Article**.

The PDF lands in `_Inbox` under whatever name iOS gives it. The Mac watcher
renames it to `NYT - Headline.pdf` and moves it into the library, usually
within a few seconds of syncing.

## Why only two actions

The naming — working out the publication, cleaning the headline, composing
`<Publication> - <Headline>.pdf` — all happens on the Mac, where it is
ordinary Python that can be tested. Putting that logic in the Shortcut as
well was an optimisation for filing while the Mac is asleep. It is not worth
fighting the Shortcuts app for.

If you want the phone to name files by itself later,
[BUILD-SHORTCUT-BY-HAND.md](BUILD-SHORTCUT-BY-HAND.md) has all 45 actions.
Add them once this two-action version is proven to work.

## Checking it worked

On the Mac:

```bash
python3 -m articlefiler run --no-settle   # file anything waiting
python3 -m articlefiler verify            # are they articles or paywalls?
```

If `run` says "nothing to file" and lists the watched folders, the PDF has not
reached the Mac: either iCloud has not synced yet, or the picker was pointed
somewhere else. Open Files on the iPhone and look at the folder you picked —
whatever is there is the truth.
