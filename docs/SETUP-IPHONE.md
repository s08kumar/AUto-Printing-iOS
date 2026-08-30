# Setting up the iPhone

Ten minutes once, then one tap forever.

## 1. Get the Shortcut onto the phone

The Shortcut has to be built and signed on a Mac first — iOS has no way to sign
one. From the repository on your Mac:

```bash
make shortcut
./shortcut/sign.sh 'build/File Article.shortcut'
```

Then either:

- **AirDrop** `build/File Article.signed.shortcut` to the iPhone and tap it, or
- **double-click** it on the Mac to add it there; iCloud sync carries it to the
  iPhone within a minute or two.

Prefer to build it yourself in the Shortcuts app? See
[BUILD-SHORTCUT-BY-HAND.md](BUILD-SHORTCUT-BY-HAND.md) — it is a good idea to
read it once anyway, so you know what the Shortcut is doing.

## 2. Put it in the Share sheet

1. Open **Shortcuts**, find **File Article**, tap the **ⓘ**.
2. Turn on **Show in Share Sheet**.
3. Under **Share Sheet Types**, make sure URLs, Safari web pages, Images, PDFs
   and Text are all ticked. Images matter — that is the screenshot route.

## 3. Move it to the top of the Share sheet

Worth doing, because otherwise you scroll for it every time.

1. Open any article and tap **Share**.
2. Scroll to the bottom of the action list and tap **Edit Actions…**.
3. Find **File Article** and tap the **+** to add it to Favourites.
4. Drag it to the top.

## 4. Bind the Save File destination — required, once per device

This is the step that trips everyone up, so do it before your first real
article.

A generated shortcut can only carry a *subpath*, not a folder. Which folder
that subpath hangs off is decided by the device, and left to itself the
Shortcuts app resolves it against its own **local** storage — so articles land
in *On My iPhone → Shortcuts →* your folder name, never sync, and appear
nowhere on the Mac. The Shortcut reports success throughout, because from its
point of view it succeeded.

To bind it properly:

1. Open **Shortcuts** and tap **File Article** to edit it (not the ⓘ button).
2. Scroll to the last action, **Save File**.
3. Tap the folder shown next to *Subpath* / the destination.
4. In the picker, choose **iCloud Drive** →
   **NYT-WSJ-Mckinsey-HBR-Economist Articles**.
5. Leave **Ask Where to Save** off.

Picking through the picker records the actual storage location, which a typed
subpath cannot. Do the same for **File Article (Simple)**, pointing it at the
`_Inbox` inside that folder.

### Checking where it really went

After running the Shortcut, open **Files** and look in both roots:

- **iCloud Drive → NYT-WSJ-Mckinsey-HBR-Economist Articles** — correct.
- **On My iPhone → Shortcuts → NYT-WSJ-…** — not bound yet; redo the steps
  above. Drag the files across while you are there; nothing is lost.

## 5. Approve the folder, once

The first time you run it, iOS asks whether the Shortcut may save into
*NYT-WSJ-Mckinsey-HBR-Economist Articles*. Tap **Allow**. It will not ask again.

If you never see the prompt and the file never appears, open the Shortcut, tap
the **Save File** action, and re-pick the folder by hand — that re-establishes
the permission.

## The first run asks permission

The first time you share from a given site, iOS asks whether the Shortcut may
access the Safari item. Tap **Always Allow** — it is per-site, and **Allow
Once** means answering again every time.

Until you answer, the Shortcut waits, which is indistinguishable from it
having stalled.

## Safari's own PDF export

The most reliable route on iOS, and the equivalent of Export as PDF on the
Mac:

> Share → **Options ›** (just under the page title) → **PDF** →
> **Save to Files** → `_Inbox`

The PDF is the page Safari already rendered, named after its title. The
watcher does the rest. Prefer this whenever a Shortcut misbehaves.

## Using it

**Any article, any app**: Share → **File Article**. A notification confirms the
name it filed under.

**Screenshots**: take them, open Photos, select them all, Share →
**File Article**. They become one PDF. This is the route that always works —
see [PAYWALLS.md](PAYWALLS.md).

**From Safari**: same thing, and this is the route that gets past your
subscription's paywall, because Safari is already signed in.

## Making it even faster

- **Back Tap**: Settings → Accessibility → Touch → Back Tap → Double Tap →
  File Article. Two taps on the back of the phone, no Share sheet at all.
  (It runs on whatever is on screen, so it suits the screenshot route best.)
- **Ask Siri**: "Hey Siri, file article".
- **Home Screen**: Shortcuts → ⋯ → Add to Home Screen, if you would rather have
  an icon.

## When something looks wrong

**The Shortcut does not appear in the Share sheet.** Share Sheet Types is
probably too narrow — check that URLs *and* Images are ticked.

**It saves, but with no acronym.** That publication's domain is not in the
lookup table yet. Add it on the Mac and regenerate:

```bash
python3 -m articlefiler publications --add ACR "Full Name" domain.com
make shortcut
```

Nothing is lost in the meantime: the Mac watcher fixes the name once the file
syncs.

**The PDF is the paywall, not the article.** Expected for some papers — see
[PAYWALLS.md](PAYWALLS.md). Use the Safari or screenshot route for that
publication.

**It says it filed the article, but the folder is empty.** The file is not
lost. The Save File action takes a *subpath*, resolved against a base that
cannot be set from a generated shortcut, so articles land in
`iCloud Drive/Shortcuts/NYT-WSJ-Mckinsey-HBR-Economist Articles/`.

This is handled: the Mac watcher drains that folder too, and moves the
articles into the real library. `python3 -m articlefiler doctor` lists every
folder it watches.

If you want the iPhone to write straight to the library without waiting for
the Mac, bind it by hand once per device: edit the Shortcut, tap the **Save
File** action's destination, and pick the folder through the picker. Choosing
it that way records the location properly, which a typed subpath cannot.

**Everything lands in `_Inbox` instead of the main folder.** That is the Save
File destination pointing one level too deep. Open the Shortcut, tap **Save
File**, and re-pick the parent folder.
