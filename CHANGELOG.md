# Changelog

## 1.0.2 candidate

- The dock can detect a pointer at its six-pixel strip when another window prevents Qt from delivering a hover event. Revealing the dock restores its topmost position without activating it.
- Refreshes dock placement and opacity after monitor work-area and DPI changes. Keeps edge polling suspended during region OCR and when Windows input is unavailable.
- Adds bounded local lifecycle and health logs in `SideDockData`. Logs record timing, geometry and window state. Clipboard contents and note text are excluded.

## 1.0.1 — Rapid-copy Quick-Paste correction (2026-11-27)

- Restore the **one-time** recent-copies popup only for a *fresh burst* of two or more consecutive copies (at most 20 seconds between copies, paste within 45 seconds of the last copy).
- Preserve standard Ctrl+V: the latest copied item pastes normally, then only earlier copied items appear as slots 2 and 3 for eight seconds.
- No popup for a single copy, old saved clipboard history, repeated Ctrl+V, or an expired burst. Copying a fresh sequence re-arms it.
- Keep Ctrl+Shift+V / Ctrl+Alt+V for manual Quick-Paste history; use the current-monitor bottom-right popup and suppress spurious popups from SideDock's automatic paste.
- **Enable SideDock shortcuts** remains ON by default for new installations; users can opt out and existing settings are respected.

## 1.0.0 — Public source edition

### Core
- Edge-peek, smooth expand/collapse, pinning, resize and movable dock.
- Capture text, links, screenshots, images and files; two-way drag and drop.
- Favorites, search, local persistence and Quick-Paste.

### Hardening
- Single-instance lock, atomic JSON writes, capture pause and bounded new imports.
- Duplicate-file checks before copying and exact clipboard text preservation.
- Monitor-aware positioning, tray controls, selectable hotkey presets.
- Guarded auto-paste that verifies the intended foreground window.

### Design
- Monochrome visual identity, scalable app and tray icon, content type labels.
- Improved card hierarchy, capture state, history counts and empty states.
- Theme-aware Quick-Paste with countdown feedback.

### Final UX refinement
- Stronger Dark and Deep Dark contrast and improved tooltip/hover feedback.
- Manual local notes, empty-state shortcut hints and shortcut configuration inside Settings.
- Note editor and OCR review now live inside the dock instead of floating dialog windows.
- Screenshot button label; English screenshot OCR now has an in-dock workspace and uses bundled Tesseract and English recognition data in Windows packages.
- Scrollable Settings panel, data directory overview and manual cleanup of safely identified unused copies.
- Removed LOCAL from the dock header; PAUSED remains visible when capture is disabled.

### Documentation & onboarding
- Public-facing README with features, use cases, keyboard shortcuts, install/build prerequisites, diagrams, privacy guidance and developer credits.
- Illustrated SmartScreen setup walkthrough; authentic final-installer screenshots still pending.
- Installer SHA-256 published to CI run summary to help users verify exact downloads.

### Distribution
- New per-user Inno Setup Windows installer with normal uninstall, Start Menu shortcut, optional desktop shortcut, MIT license and no admin requirement.
- Automated install → exact-binary verification → uninstall smoke test. Clipboard data is preserved.
- Fast-start PyInstaller onedir Windows application (installed by one setup EXE) with version information, icon and SHA-256 checksum.
- Start with Windows checkbox is enabled by default for the installing user; Windows may stagger launch after sign-in.
- Shared per-user startup integration for Python and executable installs.
- GitHub Actions Windows build and isolated source and binary smoke tests.

### Known limitations and release gates
- Additional native Windows 10/11 hardware and cross-application testing remains desirable.
- Clipboard history and stored copies are not encrypted.
- Executable is unsigned.
- No automatic update mechanism; release artifacts are static snapshots.
- MIT-licensed source is public on `main`. Direct GitHub Release EXE downloads are now available; broader Windows 10/11 device coverage remains an ongoing quality goal.
