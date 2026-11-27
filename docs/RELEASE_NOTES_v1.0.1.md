# SideDock v1.0.1 — Rapid-copy Quick-Paste correction

**Everything you copy. One edge away.**

This is the latest public SideDock Windows 10/11 release, containing the maintainer-tested **Ctrl+V recent-copies popup correction**, while preserving all v1.0.0 features.

## What's fixed

- Native **Ctrl+V always pastes the newest copied item normally**.
- Only after copying **two or more items close together** does a one-time popup appear with **the earlier one or two copies**, never the already-pasted newest item.
- The popup does **not** open after a single copy, stale clipboard history, an old sequence, or a second Ctrl+V without fresh multiple-copy activity.
- Fresh multiple-copy sequences qualify when consecutive captures are within **20 seconds** and the user pastes within **45 seconds** of the last copy.
- The popup closes automatically after eight seconds. The dedicated **Ctrl+Shift+V Quick-Paste** history shortcut remains available independently.
- **Enable SideDock shortcuts** is enabled by default on new installations, with an opt-out if another application conflicts; existing preferences are respected.
- Dragging files into SideDock does not trigger clipboard-copy popups.
- The popout is positioned on the monitor with your current cursor.

## Install or update

Download **SideDock-Setup-1.0.1.exe** below. It's a direct public `.exe`—no ZIP extraction, GitHub account, Python, pip, or Tesseract setup is required.

Close the older SideDock tray instance before upgrading. The installer upgrades the existing per-user program and **preserves `%USERPROFILE%\SideDockData` clipboard history and notes**. The default Start-with-Windows setting remains opt-out.

The installer is **unsigned**. Verify the exact release file and its SHA-256 digest, scan with Microsoft Defender, and follow Windows security policy. Never turn off malware protection to install software.

Downloading an executable does not automatically install it; Windows requires you to launch and approve the installer.

## Verification

The change was validated in PR [#2](https://github.com/saileshchikkam/SideDock/pull/2) with **41/41 Windows unit tests**, packaged offline OCR, desktop smoke testing, installer startup integration and uninstall smoke checks. The maintainer also confirmed the intended popup behavior on their Windows PC.

**Privacy:** SideDock works locally and its stored clipboard history is not encrypted. Pause capture before copying confidential material.

[Source code](https://github.com/saileshchikkam/SideDock) · [Safe installation guide](https://github.com/saileshchikkam/SideDock/blob/main/docs/INSTALLATION.md) · [MIT license](https://github.com/saileshchikkam/SideDock/blob/main/LICENSE)
