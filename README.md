# SideDock

An auto-hiding Windows 10/11 productivity dock for text, screenshots and files. Everything stays on your PC.

## Install from source (Windows, Python 3.10+)

```powershell
pip install git+https://github.com/saileshchikkam/SideDock.git
python -m sidedock
```

Hover the right screen edge to open the dock. Drag the top handle to move it, or use Settings to change side and theme.

## Controls

- Copy text, URLs, screenshots or files to collect them automatically.
- Drag items in or out; click a saved card to paste it.
- Star important items; Clear removes unstarred items.
- Ctrl+Shift+V opens the latest three slots. Ctrl+Alt+1/2/3 selects a displayed slot.
- After copying several items, Ctrl+V opens the remaining quick-paste slots.

## Privacy and limits (hardening branch)

Data is stored in `%USERPROFILE%\SideDockData` as local JSON and files, **not encrypted**. Password-manager exclusion is honored when the source application supplies the Windows exclusion format; it is not a guarantee that every secret is excluded. Settings lets you pause automatic capture (manual drops still work). Existing history is not deleted when pausing.

New imports stop at 500 history items, 256 KiB per text item, 50 MiB per file/image or 500 MiB of stored copies. Clear or remove items to make room. Existing history above the limits is retained. Folders are referenced, not copied.

## Development

```powershell
pip install -e .
python -m unittest discover -s tests
python -m sidedock
```

Optional Python-install startup toggle: `python setup_autostart.py`. This launches the installed module using pythonw if available. An executable installer and public release are planned separately.

## Tray and monitors

The notification-area icon opens the dock, pauses automatic capture, toggles global shortcuts, selects a shortcut preset, or quits SideDock. The classic preset uses Ctrl+Shift+V and Ctrl+Alt+1/2/3; the alternative uses Ctrl+Alt+V and Ctrl+Shift+Alt+1/2/3. Numbered shortcuts are registered only while their slots are visible. Disable global shortcuts to avoid conflicts with other apps. Drag the top handle to another monitor to move the dock; its monitor is remembered. If Windows refuses foreground restoration, SideDock leaves the item on the clipboard instead of sending an unchecked paste.
