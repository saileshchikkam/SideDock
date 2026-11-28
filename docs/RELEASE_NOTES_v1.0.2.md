# SideDock v1.0.2 — Windows multitasking stability

## Refreshed v1.0.2 Windows build — startup and desktop recovery

The existing public v1.0.2 release was refreshed in place after post-launch
reports that SideDock could be difficult to reach after Windows logon, Win+D,
quickly closing windows, or switching applications.

- The six-pixel edge stays recoverable after Explorer Show Desktop and other
  desktop transitions. Explorer's own fullscreen-sized desktop windows are
  no longer mistaken for fullscreen apps.
- A small independent visibility watchdog restores a hidden, minimized or
  demoted tool window without deliberately taking focus. Actual fullscreen
  apps, OCR selection and active drags remain protected.
- The edge can appear earlier at sign-in by deferring the initial saved-card
  layout until after its window is shown. Windows itself can schedule
  Startup apps later than sign-in; the app cannot guarantee boot timing.
- Opening the shortcut while SideDock is already running wakes the existing
  instance without spawning a second clipboard watcher.

**Important for existing v1.0.2 users:** The release tag, EXE filename and
public download URL remain **unchanged**, but the installer bytes and
SHA-256 have been updated. If you downloaded the original v1.0.2 installer,
download it again and compare its SHA-256 with the current `SHA256SUMS.txt`
asset on this release. The installer is unsigned; follow Windows security
policy and do not disable malware protection.

This is a **revised build of v1.0.2**, not an additional release or v1.0.3.
The successful Windows build and detailed acceptance matrix are linked in
[Windows startup and desktop acceptance](https://github.com/saileshchikkam/SideDock/blob/main/docs/V1_0_2_RELIABILITY_ACCEPTANCE.md).
Interactive logon and device-specific monitor scenarios need validation on
the actual hardware; automated CI alone cannot certify every configuration.


SideDock v1.0.2 is a stability update to the free, open-source Windows 10/11 edge dock. It addresses a case where opening or switching between other applications prevented the collapsed dock from reopening on hover.

## What's improved

- **More reliable edge reveal.** A guarded, low-overhead cursor fallback recovers when another window prevents Qt from delivering an edge-hover event.
- **No unwanted focus changes.** Revealing SideDock restores its always-on-top placement without deliberately activating the dock or interrupting the foreground application.
- **Better display-change recovery.** SideDock recalculates its screen-edge position and opacity after geometry and DPI changes. Fullscreen and OCR-selection checks prevent unwanted reveals.
- **Local diagnostics.** Rotating log files in `%USERPROFILE%\SideDockData` record application lifecycle, geometry and health metadata, without logging clipboard contents or note text.

## Verified build and tests

The Windows release pipeline runs unit tests, source/packaged OCR smoke tests, builds the Windows application and per-user installer, verifies startup registration, runs installation/uninstallation checks, and regression-tests an in-place upgrade from the official v1.0.1 installer with disposable history, notes, favorites and settings data. Installer SHA-256 is included as a separate release asset.

Controlled edge-event and native window tests validated the hover recovery and non-activating topmost behavior. The maintainer also reports that the v1.0.2 candidate worked well during personal Windows testing.

**Coverage limits:** Automated tests, a limited real-device check and successful build checks cannot guarantee error-free behavior on every Windows 10/11 machine. In particular, comprehensive interactive Windows Snap, mixed-DPI/multi-monitor, long-duration use and every third-party application combination have not been certified.

## Install or upgrade

Download `SideDock-Setup-1.0.2.exe` from this release. No Python or GitHub account is required. If already using v1.0.1, exit SideDock and install v1.0.2 over the existing installation to preserve saved data. Backing up `%USERPROFILE%\SideDockData` before upgrading is recommended.

**Security and privacy:** The installer is **unsigned**, so Microsoft Defender SmartScreen may show an unknown-publisher warning. Verify the installer source and SHA-256 file, and do not disable security protection or override malware detections. SideDock is local-first, but stored clipboard history and notes **are not encrypted**. Avoid capturing sensitive credentials or private tokens. See [Security and privacy](https://github.com/saileshchikkam/SideDock/blob/main/SECURITY.md) and the [installation guide](https://github.com/saileshchikkam/SideDock/blob/main/docs/INSTALLATION.md).

For issues or feedback, use [GitHub Issues](https://github.com/saileshchikkam/SideDock/issues).

**SideDock — Everything you copy. One edge away.**
