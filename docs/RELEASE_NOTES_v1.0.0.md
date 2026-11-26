# SideDock v1.0.0 — Windows

**Everything you copy. One edge away.**

SideDock is a free, open-source, local-first Windows 10/11 desktop dock for clipboard history, screenshots, in-app notes, offline English OCR, searchable cards, Quick-Paste shortcuts, file handling and everyday productivity.

## Install for Windows

Download the **SideDock-Setup-1.0.0.exe** asset below. This is a **direct installer download**—no GitHub Actions page, artifact ZIP, or GitHub account is needed. Downloading does not automatically execute or install software; open the downloaded installer and approve it in Windows to proceed.

SideDock installs for the current Windows user and offers **Start SideDock when I sign in to Windows** (selected by default). Windows may delay some startup apps after login. Python, pip and a separate Tesseract installation are **not required** for the packaged installer.

## Verified installer

- File: `SideDock-Setup-1.0.0.exe`
- SHA-256: `25c9bf3d04d7dc72ff5a20a4a153b2cd8af4777c24fac93db6e334e0ef73119c`
- Verified CI build: https://github.com/saileshchikkam/SideDock/actions/runs/45848413201
- 30/30 Windows unit tests and automated EXE/OCR/installer smoke checks passed.

## Before you install

This installer is **unsigned**, so Microsoft Defender SmartScreen may show an unfamiliar-app warning. Verify the download's source, checksum and Defender scan before deciding whether to run it. Do not disable security protection or bypass malware detections.

SideDock stores clipboard history **locally and without encryption**; pause capture before copying passwords or confidential data. No clipboard history or OCR images are uploaded by SideDock.

See the [full README](https://github.com/saileshchikkam/SideDock#readme) and [Windows installation guide](https://github.com/saileshchikkam/SideDock/blob/main/docs/INSTALLATION.md). Licensed under [MIT](https://github.com/saileshchikkam/SideDock/blob/main/LICENSE).

