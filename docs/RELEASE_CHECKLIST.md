# SideDock Windows release acceptance checklist

## v1.0.2 candidate gates

- [ ] Review the stabilization pull request and its Windows build, source and packaged OCR checks, installer smoke test and SHA-256.
- [ ] Reproduce the original failure with the reported apps and layouts. Retest the same steps with the candidate on an interactive Windows desktop.
- [ ] Verify focus stays with the active app during edge reveal after Snap, Alt+Tab and taskbar switching. Exercise left and right edges, multiple monitors, DPI changes and fullscreen.
- [ ] Upgrade an isolated v1.0.1 installation with sample history, favorites, notes and settings. Verify clipboard and Quick-Paste behavior, startup, single-instance handling and data retention on uninstall.
- [ ] Complete a long-running desktop soak and review `SideDockData/sidedock.log` for heartbeat gaps, startup/shutdown and native errors.
- [ ] Publish only after the candidate passes these gates. Keep the v1.0.1 GitHub Release available.

## v1.0.1 public release evidence

## Automated evidence

- [x] **41/41 Python unit tests passed** on Windows CI, including DPI capture alignment, embedded workspaces, OCR, storage and installer contract tests.
- [x] Source Qt and offline OCR smoke tests passed.
- [x] Fast-start PyInstaller **onedir** Windows app built and verified.
- [x] Installed binary's OCR engine, English language model and Qt startup smoke checks passed.
- [x] Per-user setup installed successfully with **Start with Windows selected**, registered the expected HKCU Run entry, and removed it on uninstall.
- [x] SHA-256 checksums generated and the **single-installer** artifact uploaded.
- [x] Installer startup smoke test on the runner measured **0.39 seconds** (not a full Windows login-time test).
- [ ] Full native Windows desktop interaction on both Windows 10 and Windows 11 and additional security review remain desirable before claiming comprehensive platform certification.
- [x] Maintainer has reported satisfactory core functionality on a Windows laptop, with startup apps appearing a few minutes after sign-in.

Evidence: [Windows Actions run 45997308087](https://github.com/saileshchikkam/SideDock/actions/runs/45997308087), commit `9a3e2b6`; [public v1.0.1 Release](https://github.com/saileshchikkam/SideDock/releases/tag/v1.0.1). The artifact includes only one installer EXE, wrapped automatically in a GitHub Actions ZIP. Automated checks do **not** simulate a user's actual complete reboot, foreground hooks or multi-monitor desktop session.

## Real Windows desktop acceptance

Use a non-sensitive test profile and disposable files. Start with the candidate executable extracted from its artifact.

| Test | Expected result | Result |
| --- | --- | --- |
| Launch portable EXE | Dock appears at chosen screen edge; no Python required | Pending |
| Install SideDock setup | Per-user install, Start Menu shortcut and optional desktop shortcut, without elevation; autostart checked by default | Pending |
| Startup opt-out | Uncheck Start with Windows on install; verify no Run entry; tray toggle works afterward | Pending |
| Fast startup | Installed onedir app loads with no onefile extraction; startup smoke measures duration | Pending |
| Sign-in and restart | Sign out/in and reboot; app appears without opening shortcut, noting Windows may stagger startup apps | Pending |
| Uninstall SideDock setup | Program removed; saved SideDockData history/notes remain intact | Pending |
| Second instance | No second clipboard watcher/dock | Pending |
| Hover and collapse | No flicker while stationary at edge | Pending |
| Resize at min/max size | Header, card controls and scrolling remain usable | Pending |
| Left/right positioning | Dock snaps correctly, including footer controls | Pending |
| Multiple monitors | Drag to another monitor; no hidden dock leakage onto adjacent screen | Pending |
| Monitor disconnect | Dock remains reachable on remaining screen | Pending |
| DPI and resolution | Test 100% and 150%/200% scaling; no clipping | Pending |
| Exact text and URL | Leading/trailing spaces and line breaks preserved | Pending |
| Screenshots | Snipping Tool capture and clipboard copy display correctly | Pending |
| Files and folders | Drag/copy, preview and drag out; originals remain intact | Pending |
| Auto-paste | Correct target in Notepad and browser; no unintended input after focus switch | Pending |
| Search then paste | Focus restoration succeeds safely or leaves copied item on clipboard | Pending |
| Quick-Paste | Ctrl+V after rapid copies pastes newest and shows only previous items once; dedicated shortcut opens history; timeout works | Maintainer confirmed rapid-copy behavior on Windows; other environments untested |
| Hotkey conflict | Numbered hotkeys inactive after popup closes; disable toggle works; SideDock shortcuts default ON on first use | Pending full cross-application testing |
| Favorite and clear | Starred items survive; original files remain untouched | Pending |
| Capture pause | Automatic capture stops and resumes; manual drops remain available | Pending |
| Restart | History, selected monitor, theme and startup preference persist | Pending |
| Startup | Enable, reboot/log in, verify one instance; disable and repeat | Pending |
| Theme | Deep Dark, Dark and Windows theme remain readable | Pending |
| Manual note | Type and save a note inside the main dock (no external window), restart, search, favorite and paste | Pending |
| OCR | Selection preview and saved screenshot crop match at 100%, 125%, 150%, 200% DPI; multiple monitors; bundled engine; editable in-dock result | Pending |
| Local cleanup | Only unused SideDock-managed copies are removed after confirmation | Pending |
| Settings | Shortcut options and storage tools accessible at minimum dock height | Pending |
| Hover feedback | Star/remove buttons and tooltips work with mouse and keyboard focus | Pending |
| Storage | New oversized files or limits skip import without data loss | Pending |
| Exit | Tray exit releases hooks and instance lock | Pending |

Test at least one Windows 10 and one Windows 11 environment before claiming both are fully validated. Record exact OS build, display scaling, commit, artifact checksum, and any failures.

## Release decision

- [ ] All critical native acceptance tests completed.
- [ ] No known blocking clipboard, focus, startup or data-loss regressions.
- [x] Maintainer selected MIT License; LICENSE file committed to the release branch.
- [x] Privacy and unsigned executable limitations documented in the public README and security guide.
- [x] Maintainer explicitly approved PR #1 merge to `main` (November 26, 2026).
- [ ] Final main build passes.
- [ ] Installer tested on real Windows 10 and Windows 11 desktops.
- [ ] Maintainer creates the version tag and publishes the matching executable and checksum to GitHub Releases.
- [ ] Verify published assets and their hashes after publication.

Do not publish the candidate as a stable release before completing the gates.
