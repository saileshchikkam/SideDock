<p align="center"><img src="docs/brand-mark.svg" width="96" alt="SideDock logo"></p>

<h1 align="center">SideDock</h1>
<p align="center"><strong>Everything you copy. One edge away.</strong></p>
<p align="center">A local-first clipboard and drag-and-drop dock for Windows 10/11.</p>

> **Release candidate:** the automated Windows build, unit tests and isolated smoke tests passed. Interactive testing on real Windows desktops is pending. There is no stable public release yet.

## A workspace between apps

SideDock hides at the edge of your screen until you need it. Collect a screenshot, a code snippet, a URL or a file, then move it into your next application without opening a separate window.

- **Edge-peek** — a thin, auto-hiding dock with smooth expansion, pinning, resizing and monitor-aware positioning.
- **Clipboard capture** — searchable text, links, screenshots, images, and local files, with Windows clipboard privacy exclusions respected when supplied by the source application.
- **Drag and drop** — save items by dragging them onto the dock; drag them out to compatible apps.
- **Quick-Paste** — access up to three recent items from a keyboard shortcut or the eight-second popup.
- **Favorites** — star important items to preserve them when clearing unstarred history.
- **Local controls** — pause capture, switch shortcut presets, and manage startup from the notification-area icon.
- **Appearance** — improved contrast in the Dark and near-black Deep Dark palettes, plus Windows accent-aware mode.
- **Notes** — save handwritten text and snippets locally without changing the system clipboard.
- **Screen text** — optional offline OCR for English screenshots using a locally installed Tesseract executable.
- **Storage tools** — open the data folder, inspect usage and manually remove only unreferenced SideDock-managed copies.

## Try the Windows release candidate

1. Open the [successful Windows build](https://github.com/saileshchikkam/SideDock/actions/runs/45027136525).
2. Download the **SideDock-Windows** artifact (GitHub sign-in may be required; artifacts expire).
3. Extract the ZIP to a permanent folder, verify the checksum, and run `SideDock.exe`.
4. Hover over the right screen edge to open SideDock.

No Python installation is required for the portable executable. It is unsigned, so Windows may display a trust warning. Do not bypass security warnings unless you have verified the source and checksum and trust the publisher.

Verify the SHA-256 digest in PowerShell:

```powershell
Get-FileHash .\SideDock.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

Compare the hashes before running the file.

### Install from source

Requires Windows and Python 3.10+; Git must be available for the Git URL installation.

```powershell
python -m pip install "git+https://github.com/saileshchikkam/SideDock.git@release/v1.0-hardening"
python -m sidedock
```

To stop SideDock, choose **Quit SideDock** from its notification-area menu. To disable automatic startup, turn off **Start with Windows** before removing the executable.

## Notes, screenshot and text extraction

**Add Note** appears directly below search. Enter text and press Save to keep a searchable, pinnable note; manually saved notes do not trigger the rapid-copy workflow.

**Screenshot** opens Windows screen snipping. **Text OCR** also opens screen snipping, then attempts offline English OCR after the selected image reaches the clipboard. Text is shown for editing before it is saved. Text OCR is optional and requires installing the [Tesseract OCR command-line program](https://github.com/tesseract-ocr/tesseract) on the Windows computer and restarting SideDock. The portable EXE **does not bundle Tesseract**. This feature never uploads the screenshot; if Tesseract is unavailable, SideDock displays setup guidance instead. If the snip is not automatically copied to the clipboard, copy it manually from Snipping Tool. OCR output can contain mistakes; verify it before using it.

## Keyboard shortcuts

| Action | Classic | Alternative |
| --- | --- | --- |
| Paste normally (show remaining recent items when available) | Ctrl+V | Ctrl+V |
| Open Quick-Paste | Ctrl+Shift+V | Ctrl+Alt+V |
| Select a visible slot | Ctrl+Alt+1/2/3 | Ctrl+Shift+Alt+1/2/3 |

Change the preset or disable the global shortcuts from the tray menu. Numbered shortcuts are registered only while their slots are visible. If Windows denies focus restoration, the selected item stays on the clipboard rather than sending an unchecked paste.

## Privacy and data

SideDock stores local history in `%USERPROFILE%\SideDockData`. There is no account or backend service in the application. The history JSON and saved copies **are not encrypted**. Only clipboard applications that supply the Windows exclusion format can be automatically excluded; do not assume every password or sensitive value is excluded.

- Pause automatic clipboard capture in Settings or the tray. Manual drops and deliberately started OCR remain available.
- Settings provides the same shortcut enable switch and presets as the tray. It also shows storage usage and offers manual cleanup of unreferenced copies.
- Clear removes unstarred saved items and their managed copies; this is not an undoable operation.
- Original source files are not removed by Clear. Folders are referenced rather than copied.
- Existing history is preserved when capture is paused or when storage limits change.

| Limit for new imports | Value |
| --- | --- |
| History items | 500 |
| Text item | 256 KiB |
| File or image | 50 MiB |
| Managed file copies | 500 MiB |

If a limit is reached, new imports are skipped. Remove items to make space.

## Development and building

```powershell
git clone -b release/v1.0-hardening https://github.com/saileshchikkam/SideDock.git
cd SideDock
python -m pip install -e . -r requirements-build.txt
python -m unittest discover -s tests -v
python -m sidedock --smoke-test
python scripts/build_windows.py
```

Build on Windows with Python 3.12. Outputs: `dist/SideDock.exe` and `dist/SHA256SUMS.txt`. GitHub Actions builds and uploads the portable package after the checks succeed; it does not publish releases automatically.

## Release information

- [Changelog](CHANGELOG.md)
- [Windows acceptance and release checklist](docs/RELEASE_CHECKLIST.md)
- [Security and privacy notes](SECURITY.md)

License selection is pending. Public repository visibility alone does not establish an open-source license.
