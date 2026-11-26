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
- **Screen text** — on-device English OCR from a screenshot region or saved image, included in the Windows release without a separate setup.
- **Storage tools** — open the data folder, inspect usage and manually remove only unreferenced SideDock-managed copies.

## Try the Windows release candidate

1. Open the [Windows build workflow](https://github.com/saileshchikkam/SideDock/actions/workflows/windows-build.yml), then select the latest **successful run on `release/v1.0-hardening`**.
2. Download the **SideDock-Windows-Installer** artifact from the run's *Artifacts* section (GitHub sign-in may be required; artifacts expire).
3. Extract the GitHub artifact ZIP. It now contains **only `SideDock-Setup-1.0.0.exe`**; run that installer. GitHub Actions always wraps artifacts in a ZIP even when they contain a single EXE.
4. Launch SideDock and hover over the right screen edge.

Neither installer nor portable executable requires Python on the destination PC. Both are currently unsigned and may trigger a Windows SmartScreen warning. Scan the file and verify its checksum before deciding whether to trust it.

**Installer behavior:** installs per-user without administrator permission, creates a Start Menu shortcut and an optional desktop shortcut. **Start SideDock automatically when I sign in to Windows** is selected by default during setup; you can uncheck it or change it later from the system tray. The startup permission applies to the current Windows user and does not request administrator rights. A normal uninstaller is registered. Uninstall preserves `%USERPROFILE%\SideDockData` (including history, notes and copied files), which must be managed separately. Before upgrading from the portable build, quit it and disable **Start with Windows** to avoid a stale startup entry.

Verify the SHA-256 digest in PowerShell:

```powershell
Get-FileHash .\SideDock.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

The CI build prints both SHA-256 hashes to its logs. The artifact contains only the installer; the portable EXE and checksum manifest remain CI build outputs but are not bundled in the download. Compare the installer hash with the build log before running it.

### Install from source

Requires Windows and Python 3.10+; Git must be available for the Git URL installation.

```powershell
python -m pip install "git+https://github.com/saileshchikkam/SideDock.git@release/v1.0-hardening"
python -m sidedock
```

To stop SideDock, choose **Quit SideDock** from its notification-area menu. To disable automatic startup, turn off **Start with Windows** before removing the executable.

## Notes, screenshot and text extraction

**Add Note** appears below search. It opens an editor **inside the existing SideDock panel**, not in a separate dialog. Save creates a searchable, pinnable local note card; cancel discards the unsaved draft. Manual notes do not trigger Quick-Paste.

**Screenshot** continues to use Windows screen snipping. **Text OCR** now opens a **SideDock-internal OCR workspace** with three options: Select Screen Region (using SideDock's pixel-aligned, unzoomed selection overlay; the highlighted preview exactly matches the cropped screenshot at 100%–200% display scaling), Use Clipboard Image or Use Latest Saved Image. The OCR result opens in SideDock's inline text editor for correction before saving a card. The Windows installer and portable EXE package the English Tesseract OCR engine and its language data to avoid a separate OCR installation. Source-only Python installations may still need Tesseract installed locally. No screenshots or text are uploaded. OCR recognition can make mistakes; verify the output before using it.

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
python scripts/build_installer.py  # requires Inno Setup 6
```

Build on Windows with Python 3.12 and Inno Setup 6. Outputs: `dist/SideDock.exe`, `dist/SideDock-Setup-1.0.0.exe` and `dist/SHA256SUMS.txt` (checksums for both binaries). CI performs a silent install with autostart enabled, verifies the installed EXE matches the portable build, checks the startup registry entry, and tests uninstall removes that entry. **The downloadable GitHub Actions artifact contains one installer EXE only.** For a truly direct EXE download (without a GitHub artifact ZIP), the installer must be attached to an approved GitHub Release. Stable publication remains gated on native Windows testing.

## Release information

- [Changelog](CHANGELOG.md)
- [Windows acceptance and release checklist](docs/RELEASE_CHECKLIST.md)
- [Security and privacy notes](SECURITY.md)

## License

SideDock is released under the [MIT License](LICENSE). You may use, modify and redistribute it, including commercially, while preserving the copyright and license notice. The software is provided without warranty.
