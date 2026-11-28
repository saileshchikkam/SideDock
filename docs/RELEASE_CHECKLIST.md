# SideDock Windows release acceptance checklist

## Post-launch reliability audit for the existing v1.0.2 release

On 28 November 2026 the maintainer reported failures to reveal SideDock after Windows
sign-in, Win+D and rapid application switching. The earlier maintainer acceptance
statement does **not** certify these reported cases. A targeted hotfix is being
validated in [PR #4](https://github.com/saileshchikkam/SideDock/pull/4).

The [detailed acceptance matrix](V1_0_2_RELIABILITY_ACCEPTANCE.md) has automated
and hardware-dependent gates. **GitHub Actions cannot perform an actual Windows
reboot and desktop sign-in on the maintainer's PC.** Record such tests as unverified
unless results are supplied. Do not claim broad platform certification.

The installer refresh reuses the existing `v1.0.2` tag and filenames; published
installer hashes must match the specific build. Older v1.0.0 and v1.0.1
releases stay available only as historical versions.

## v1.0.2 — published stable release (2026-11-28)

- [x] [Stabilization PR #3](https://github.com/saileshchikkam/SideDock/pull/3) merged to `main` at commit `f900c7ce686d7054b12b08f2bee5dc5b8566287f`.
- [x] Exact merged-main [Windows CI run 46122217681](https://github.com/saileshchikkam/SideDock/actions/runs/46122217681) passed: 53 automated unit tests (one offscreen-only skip), the separately executed **native Windows topmost/no-focus regression**, source and packaged offline OCR, executable and installer smoke checks.
- [x] Isolated v1.0.1 → v1.0.2 upgrade regression passed, verifying disposable history, notes, settings, saved files, startup registry and uninstall data preservation.
- [x] [Publication workflow 46122492238](https://github.com/saileshchikkam/SideDock/actions/runs/46122492238) succeeded and created the [public stable v1.0.2 GitHub Release](https://github.com/saileshchikkam/SideDock/releases/tag/v1.0.2). GitHub marks it latest, not draft or prerelease.
- [x] Release includes `SideDock-Setup-1.0.2.exe` and `SHA256SUMS.txt`; the exact installer SHA-256 matches the successful main build and publishing run: `f44e9d1cb3905e765f56a3ce307bc5d15ce60ca9cc855f78b1e2301521a46501`.
- [x] Project README and installation guide point to v1.0.2; [GitHub profile README PR #1](https://github.com/saileshchikkam/saileshchikkam/pull/1) was merged with matching download buttons.
- [x] **Maintainer-reported desktop acceptance:** on 2026-11-28 the maintainer stated that they checked everything and authorized public release. This is **self-reported acceptance**; interactive desktop gestures were not independently executed through GitHub Actions or this audit. Individual OS builds, Snap/Alt+Tab captures, mixed-DPI monitor configurations and soak logs were not furnished for independent certification. Continue to collect these as ongoing compatibility evidence.
- [x] Preserve older v1.0.0 and v1.0.1 releases as historical downloads. Only v1.0.2 is linked as **current/latest**; the v1.0.1 installer remains an input to upgrade regression testing.

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
