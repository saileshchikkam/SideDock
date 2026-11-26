# Security and privacy

SideDock monitors clipboard changes and persists selected content on the local machine. Treat its storage directory as potentially sensitive.

## Current protections

- Local-only storage; no application backend or account.
- Capture pause available from Settings and the tray. Intentionally initiated OCR is still allowed while automatic clipboard history capture is paused.
- Screenshot OCR uses a bundled offline Tesseract executable in official Windows builds. Source-only development runs may require Tesseract installed on the computer. OCR never uploads images to any service.
- Local cleanup requires a confirmation and removes only SideDock-named unreferenced managed copies; there is no automatic eviction.
- Windows exclusion clipboard format respected when the source sets it.
- Atomic JSON replacement, bounded new imports, and guarded foreground paste.

## Limitations

- History JSON and cached files are not encrypted.
- Applications that do not mark sensitive clipboard content may have that content captured.
- The executable is unsigned; independently verify the artifact checksum.
- A checksum establishes correspondence to the published artifact, not publisher identity or safety.

Do not submit clipboard contents, tokens, passwords, personal files or private screenshots in public issues. For non-sensitive problems, use the repository's issue tracker. A private vulnerability reporting channel has not been configured; use a private channel with the maintainer before sharing sensitive details.
