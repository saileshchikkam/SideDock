# Changelog

## 1.0.0 — Release candidate

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

### Distribution
- Portable Windows executable with version information, icon and SHA-256 checksum.
- Shared per-user startup integration for Python and executable installs.
- GitHub Actions Windows build and isolated source and binary smoke tests.

### Known limitations and release gates
- Full native interactive desktop testing is pending.
- Clipboard history and stored copies are not encrypted.
- Executable is unsigned.
- No automatic update mechanism; release artifacts are static snapshots.
- License selection and stable publication are pending.
