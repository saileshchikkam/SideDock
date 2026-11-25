# SideDock v1.0.0 release candidate — acceptance checklist

## Automated evidence

- [x] Original 12 Python unit tests passed on Windows; additional OCR, storage and theme tests added for the new candidate.
- [x] Source Qt smoke test passed.
- [x] Windows portable executable built successfully.
- [x] Packaged binary smoke test passed.
- [x] SHA-256 checksum generated and artifact uploaded.
- [ ] Per-user Windows installer passes its CI install, exact-binary and uninstall smoke tests.

Evidence: [GitHub Actions run 45027136525](https://github.com/saileshchikkam/SideDock/actions/runs/45027136525), commit `2a12c4b`. These checks do not exercise global hooks or actual interactive Windows desktop behavior.

## Real Windows desktop acceptance

Use a non-sensitive test profile and disposable files. Start with the candidate executable extracted from its artifact.

| Test | Expected result | Result |
| --- | --- | --- |
| Launch portable EXE | Dock appears at chosen screen edge; no Python required | Pending |
| Install SideDock setup | Per-user install, Start Menu shortcut and optional desktop shortcut, without elevation | Pending |
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
| Quick-Paste | Remaining slots and eight-second timeout; switching presets works | Pending |
| Hotkey conflict | Numbered hotkeys inactive after popup closes; disable toggle works | Pending |
| Favorite and clear | Starred items survive; original files remain untouched | Pending |
| Capture pause | Automatic capture stops and resumes; manual drops remain available | Pending |
| Restart | History, selected monitor, theme and startup preference persist | Pending |
| Startup | Enable, reboot/log in, verify one instance; disable and repeat | Pending |
| Theme | Deep Dark, Dark and Windows theme remain readable | Pending |
| Manual note | Create a note, restart, search, favorite and paste without unexpected Quick-Paste | Pending |
| OCR | Verify missing-Tesseract warning and local text recognition when Tesseract is installed | Pending |
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
- [ ] Privacy and unsigned executable limitations acknowledged.
- [ ] Maintainer reviews and approves merge to main.
- [ ] Final main build passes.
- [ ] Installer tested on real Windows 10 and Windows 11 desktops.
- [ ] Maintainer creates the version tag and publishes the matching executable and checksum to GitHub Releases.
- [ ] Verify published assets and their hashes after publication.

Do not publish the candidate as a stable release before completing the gates.
