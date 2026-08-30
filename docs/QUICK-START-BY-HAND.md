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
   - Turn **Ask Where to Save** **off**.
   - Tap the destination and pick, through the picker:
     **iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist Articles → _Inbox**
   - Picking it here is the step that matters. Do not type a path.
4. Tap the shortcut's name at the top → rename it **File Article**.
5. Tap **ⓘ** → **Show in Share Sheet** on.
   Under **Share Sheet Types**, tick URLs, Safari web pages, Images, PDFs and
   Text.
6. Done.

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
