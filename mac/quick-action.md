# Finder right-click: "File this article"

A one-off way to file a PDF that is already sitting somewhere on the Mac —
useful for the odd download that never went through the inbox.

1. Open **Shortcuts** on the Mac and create a new shortcut named
   `File this article`.
2. In the sidebar tick **Use as Quick Action** → **Finder**, and set
   *Receive* to **Files** from **Quick Actions**.
3. Add one action: **Run Shell Script**.
   - Shell: `/bin/bash`
   - Pass input: **as arguments**
   - Script:

     ```bash
     cd "$HOME/path/to/AUto-Printing-iOS" || exit 1
     /usr/bin/python3 -m articlefiler file "$@"
     ```

     Replace the path with wherever you cloned this repository.

Right-clicking any PDF in Finder now offers **Quick Actions → File this
article**, which renames it and moves it into the library.
