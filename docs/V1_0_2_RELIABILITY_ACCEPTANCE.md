# SideDock v1.0.2 — Startup and Desktop Recovery Acceptance

This is the final reliability acceptance matrix for the **existing v1.0.2** release.
Use disposable text/files, Windows 10 and Windows 11 x64, and record OS build,
device, scaling, monitor arrangement, exact installer SHA-256 and the source commit.
Do not record credentials or clipboard contents in public issues.

## Severity and gates

**P0** = blocks public installer update (cannot start, dock inaccessible, focus theft,
loss of saved data, native paste regression). **P1** = repeated disruption, startup
delay beyond expected Windows logon scheduling, incorrect monitor positioning.
**P2** = presentation/diagnostic issue.

Check each case only after actual execution. CI results are not a substitute for
a post-logon, interactive Windows desktop test. `SideDockData/sidedock.log`
records only operational metadata, not note or clipboard contents.

## Automated regression coverage

| ID | Priority | Scenario | Expected result | Evidence |
| --- | --- | --- | --- | --- |
| A01 | P0 | Qt offscreen hideEvent, no further enterEvent | Independent watchdog re-shows the dock and re-arms edge polling within ~1.5 s | `test_watchdog_restores_hidden_dock_after_show_desktop` |
| A02 | P0 | Fullscreen foreground or region-OCR overlay | Watchdog must **not** reveal the dock over protected work | `test_fullscreen_or_overlay_must_not_be_reopened_by_watchdog` |
| A03 | P0 | Edge watcher stopped during Qt hide | Visibility watchdog restarts edge watcher | `test_watchdog_rearms_polling_after_qt_hide_event` |
| A04 | P0 | Foreground Explorer desktop / WorkerW | Permit hover even when shell window covers entire monitor | `test_explorer_desktop_is_not_mistaken_for_fullscreen_application` |
| A05 | P0 | Window imitates shell class but belongs to another PID | Do **not** bypass fullscreen guard | Same test, PID mismatch |
| A06 | P0 | Native Win32 show, nonactivating flag | `SW_SHOWNOACTIVATE` used; no keyboard focus acquisition | `test_restore_native_window_without_activating_it` |
| A07 | P0 | Second launcher invocation | Reuse existing dock, do not create a duplicate | `test_second_launch_wakes_existing_dock_not_a_new_instance` |
| A08 | P0 | Native Win32 tool-window hidden | Recover visible edge without changing foreground HWND | `test_native_hidden_window_recovers_without_focus_change` |
| A09 | P0 | Native Win32 tool-window minimized | Restore visible edge without changing foreground HWND | `test_native_minimized_window_recovers_without_focus_change` |
| A10 | P0 | Native topmost demotion | Reassert topmost with `SWP_NOACTIVATE` | Existing native focus regression |
| A11 | P0 | Left/right monitor geometry, DPI changes | Visible six-pixel strip and correct opacity | Existing stability tests |
| A12 | P0 | Installer startup registry | Per-user Run entry matches installed EXE and default startup option | Installer smoke test |
| A13 | P0 | Installer v1.0.1 → v1.0.2 upgrade | History, notes, favorites, settings and file copies preserved | Upgrade CI fixture |
| A14 | P0 | OCR, clipboard, quick-paste, files | Existing unit and source/packaged smoke regressions remain green | Windows CI test suite |

## Real Windows acceptance: execute on actual interactive desktops

Mark result **PASS / FAIL / N/A** per device with a short evidence note. None
of the scenarios below are certified by unattended GitHub Actions.

| ID | Priority | Procedure | Pass criteria | Result |
| --- | --- | --- | --- | --- |
| W01 | P0 | Fresh install with default Start with Windows checked, sign out/in | A single SideDock instance and edge strip appear automatically, no shortcut launch | PENDING |
| W02 | P0 | Shut down (not only restart), power on and sign in | Edge strip is reachable without desktop double-click; capture enabled | PENDING |
| W03 | P0 | Restart Windows, sign in with Explorer still loading | App becomes accessible after taskbar/desktop initialization; no fatal dialog | PENDING |
| W04 | P1 | Measure sign-in-to-edge time on 3 boots | Log times, Windows startup scheduling and first usable edge; investigate unexpected delays | PENDING |
| W05 | P0 | Disable Start with Windows in tray, restart | App **does not** autostart; user preference honored | PENDING |
| W06 | P0 | Re-enable Start with Windows in tray, restart | HKCU Run value resolves to current installer path and SideDock autostarts | PENDING |
| W07 | P0 | Disable startup in Windows Task Manager | OS opt-out honored; app does not bypass Windows policy | PENDING |
| W08 | P0 | Double-click SideDock shortcut while it is already running | Existing dock becomes accessible, no second tray icon or lock popup | PENDING |
| W09 | P0 | Press Win+D while dock collapsed, then move to edge | Edge reappears in approximately one watchdog interval; no focus steal | PENDING |
| W10 | P0 | Repeat Win+D 10 times with rapid focus changes | No permanent hidden dock, no duplicate instances, no crash | PENDING |
| W11 | P0 | Press Win+M, switch to desktop, then hover | Previously minimized dock recovers and slides open | PENDING |
| W12 | P0 | Open/close browser tabs and windows rapidly 20 times | Dock remains accessible from desktop and browser | PENDING |
| W13 | P0 | Alt+Tab between Notepad, browser and Explorer 20 times | Dock opens from its edge, underlying active window keeps keyboard focus | PENDING |
| W14 | P0 | Win+Tab between virtual desktops | Dock is reachable without unexpected foreground activation | PENDING |
| W15 | P0 | Maximize then restore browser with hidden taskbar | Edge detection works; no permanent blocked state | PENDING |
| W16 | P0 | Enter exclusive/borderless fullscreen video/game | Watchdog does not intrude over fullscreen | PENDING |
| W17 | P0 | Exit fullscreen directly to Windows desktop | Dock recovers without needing a second launch | PENDING |
| W18 | P1 | Toggle taskbar auto-hide and taskbar position | Dock edge and vertical bounds remain reachable | PENDING |
| W19 | P0 | Left-edge then right-edge selection, pin/unpin | Both modes work after window switching | PENDING |
| W20 | P1 | Move dock near top/bottom limits | No offscreen controls or invisible 6px strip | PENDING |
| W21 | P0 | Use 100%, 125%, 150%, 200% scaling | Hit region matches visible strip; no OCR cropping regression | PENDING |
| W22 | P1 | Disconnect/reconnect external display | Dock moves to a valid monitor; no inaccessible offscreen position | PENDING |
| W23 | P1 | Switch monitor resolutions and rearrange monitors | Dock geometry and topmost restore correctly | PENDING |
| W24 | P0 | Lock/unlock Windows (Win+L) | No intrusion while locked; dock returns after unlock | PENDING |
| W25 | P0 | Sleep/resume laptop | Single instance survives; edge reappears when desktop usable | PENDING |
| W26 | P0 | OCR region selection, then cancel, 10 times | No stale overlay or automatic edge reveal during selection | PENDING |
| W27 | P0 | Copy A → B → C rapidly, Ctrl+V in Notepad | C pastes normally, only B/A offered once; native Ctrl+V unaffected | PENDING |
| W28 | P0 | Copy one item, Ctrl+V | No unexpected recent-copy popup | PENDING |
| W29 | P0 | Copy screenshots/images/files and drag in/out | Local cards correct; originals not deleted | PENDING |
| W30 | P0 | Save/reuse notes and favorites, restart | No loss of saved information | PENDING |
| W31 | P0 | Upgrade installed v1.0.1 with populated history | v1.0.2 app works; data, settings and autorun retained | PENDING |
| W32 | P0 | Uninstall v1.0.2 from Settings | App files and owned Run entry removed; user data intentionally retained | PENDING |
| W33 | P1 | Leave app running 2+ hours with normal multitasking | No persistent hidden state, runaway CPU, or unhandled error in bounded local log | PENDING |
| W34 | P1 | Run after unplugging network | Clipboard, notes and OCR work locally without cloud dependence | PENDING |
| W35 | P0 | Download official EXE and inspect Defender scan | Unmodified installer, exact SHA-256 match, no instruction to disable protection | PENDING |

## Re-publishing within *the same* v1.0.2 release

The public launch URL is already shared. The release should have **exactly one**
current `SideDock-Setup-1.0.2.exe` and one `SHA256SUMS.txt`, no duplicate
`v1.0.2` release or `v1.0.3` tag. Preserve v1.0.0/v1.0.1 for historical
downloads and the upgrade regression.

Before replacement:
1. Confirm green **current PR head** Windows CI (full tests, native focus
   tests, source and bundled OCR, installer, in-place upgrade).
2. Execute and record real desktop W01–W17, W24–W31, and W35 on the devices
   available. Record any untested environments as unverified.
3. Use a successful **main-branch** build as the only public installer source.
4. Update `SHA256SUMS.txt` and release notes for the new binary; never quote
   the old checksum as verification for a rebuilt EXE.
5. Replace both release assets **in place** with the same filenames, confirm
   the release is still Latest (not draft/prerelease), two assets exist, and
   the downloaded asset's digest matches CI.
6. Existing customers may already have the earlier v1.0.2 binary. Clearly
   disclose that v1.0.2 was refreshed and a redownload is needed. Browser
   caches may briefly contain the earlier bytes even though the URL is stable.

**Caution:** GitHub Actions cannot test actual boot order, startup-app policy,
Snap gestures on a user's desktop, or every monitor configuration. Never label
those tests passed without recorded interactive evidence.
