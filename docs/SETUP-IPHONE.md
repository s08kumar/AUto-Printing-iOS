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

## 4. Approve the folder, once

The first time you run it, iOS asks whether the Shortcut may save into
*NYT-WSJ-Mckinsey-HBR-Economist Articles*. Tap **Allow**. It will not ask again.

If you never see the prompt and the file never appears, open the Shortcut, tap
the **Save File** action, and re-pick the folder by hand — that re-establishes
the permission.

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

**Everything lands in `_Inbox` instead of the main folder.** That is the Save
File destination pointing one level too deep. Open the Shortcut, tap **Save
File**, and re-pick the parent folder.
