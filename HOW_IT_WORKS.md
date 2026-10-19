---
title: "AdaptPods: AirPods Head Control for Windows"
subtitle: "Prototype implementation and developer guide"
date: "October 18, 2026"
lang: en
---

## 1. What has been built

AdaptPods is a Python desktop application that receives head-orientation measurements and maps them to a mouse pointer. The intended use is hands-free computer interaction, with user-adjustable settings for people who want to control a pointer through head movement.

Implemented in this package:

- A loopback UDP receiver for OpenTrack-format orientation packets.
- A preview canvas that does not move the Windows pointer.
- A Windows pointer backend and optional left-click injection.
- Neutral calibration using multiple samples and circular angle averaging.
- Separate horizontal and vertical movement ranges and axis reversal.
- Time-dependent exponential smoothing and a center deadzone.
- Dwell clicking with a move-away requirement before another click.
- Windows global keys for pause, calibration, and stop.
- Automatic pause and invalidation of calibration after detected signal loss.
- A synthetic motion sender and 26 automated tests.

**This is a source prototype, not a verified end-to-end AirPods product.** Neither a Windows machine nor physical AirPods were available for validation during this implementation. No accuracy, latency, fatigue reduction, or user-benefit measurements are claimed.

## 2. System architecture

The components run in this order:

1. AirPods produce motion measurements.
2. A separately installed Windows driver and motion bridge obtain orientation.
3. The bridge sends a local UDP datagram containing yaw, pitch, and roll.
4. AdaptPods validates and calibrates those angles.
5. Its controller filters and maps yaw and pitch to screen coordinates.
6. Preview mode displays a dot. Desktop mode moves the Windows cursor.
7. If enabled, the dwell state machine emits one left click after a stable hold.

The application does not implement Apple's Bluetooth protocol, install a driver, or use Apple's macOS Core Motion API on Windows. The sensor bridge is an external dependency with its own hardware support and licensing. OpenTrack itself is not required: AdaptPods consumes the compatible packet format directly.

## 3. The Windows sensor dependency

The inspected upstream project is [FIocker/aap-head-tracker](https://github.com/FIocker/aap-head-tracker), commit `767bbd37b93979084bdcc3e4dc9b9f13c72f82ce`. Its README reports testing with AirPods Max 2 model A3454 / firmware 8E258, Windows 11, and MagicAAP. It targets a 64-bit PC and requires the .NET 9 SDK to build. Other models are described as experimental candidates, not verified compatible devices. These are maintainer-reported results, not tests performed for AdaptPods.

The bridge depends on the third-party [MagicAAP driver](https://magicpods.app/). Its maintainer's current instructions determine installation requirements. This package neither includes nor installs it. Driver signing and system configuration can affect feasibility. Do not treat ordinary Bluetooth audio connectivity as proof of motion access. No instructions for changing Windows security configuration are automated here.

Upstream source is GPL-3.0-only. This package communicates with it as a separate process and does not bundle upstream code or binaries. Preserve attribution and review the applicable license before redistributing any upstream components.

**Your exact AirPods model, firmware, Bluetooth adapter, and Windows installation: Insufficient data to verify compatibility.** The first hardware milestone is obtaining valid changing yaw/pitch values while turning your head.

## 4. Installation and first run

### A. Exercise the app with synthetic motion

Install Python 3.10 or newer on Windows, including Tcl/Tk and the Python launcher. Extract the project ZIP. Open a terminal in the `AdaptPods` folder and run:

```powershell
py -3 app.py
```

In another terminal in the same folder:

```powershell
py -3 simulator.py
```

Equivalent launchers are `Start-Windows.cmd` and `Start-Simulator.cmd`. No third-party Python dependencies are used.

The simulator sends four seconds of neutral orientation, then smooth periodic angles. Click **Calibrate neutral** and wait for completion. Click **Start / Pause** to move the preview dot. If calibration occurs while the synthetic signal is moving, the neutral position may be offset; restart the simulator to repeat its neutral interval.

Leave desktop control and dwell clicking unchecked for this first test. Synthetic motion establishes only that the receiver/controller path works. It is not evidence of live sensor operation.

### B. Connect the external Windows bridge

First stop the simulator; it must not run alongside a real bridge. Install the driver separately using its maintainer's instructions. Pair and wear the AirPods. Install the .NET 9 SDK and Git if needed. In a separate folder:

```powershell
git clone https://github.com/FIocker/aap-head-tracker.git
cd aap-head-tracker
git checkout 767bbd37b93979084bdcc3e4dc9b9f13c72f82ce
dotnet build
dotnet run -- list
```

Start AdaptPods first so its local receiver is ready. Then start the bridge:

```powershell
dotnet run -- bridge --host 127.0.0.1 --port 4242
```

The upstream default targets its documented tested device. For another model, consult upstream's current protocol options. This guide does not claim that changing an option will make an unsupported model work. Do not run another receiver on the same UDP port. If the driver is busy, follow upstream guidance about competing consumers.

When AdaptPods shows changing yaw/pitch values, sit comfortably, face your preferred neutral direction, and calibrate. Check axis directions in preview. Use **Reverse horizontal** or **Reverse vertical** and Apply if needed. Select **Control Windows desktop**, then Start again. Checking this option intentionally pauses the controller first.

Only after pointing works, enable **dwell left-click**, then Start again. Escape stops desktop control; F8 toggles Start/Pause; F9 starts calibration. A person who cannot use these keys should have assistance for initial testing: the current emergency-key design has not been validated as an independent accessible stop method.

### C. Stop and disconnect

Pause or stop AdaptPods first. Stop the upstream bridge with Ctrl+C. Close the simulator if it is running. Closing AdaptPods releases its socket. The app does not manage sensor start/stop commands; the external bridge owns that lifecycle.

## 5. Packet interface and validation

The receiver binds only to `127.0.0.1`, default port `4242`. A datagram must be exactly 48 bytes, represented by Python's `struct` format `<6d`: six little-endian double-precision values.

| Field | Unit | AdaptPods use |
|---|---|---|
| x, y, z | Bridge translation fields | Validated as finite, otherwise ignored |
| yaw | Degrees | Horizontal control |
| pitch | Degrees | Vertical control |
| roll | Degrees | Display only |

Packets with incorrect length, nonfinite values, or rotations outside ±360 degrees are discarded. All valid buffered packets are drained up to a per-frame limit of 256, and the newest is used. The limit prevents continuous packet traffic from indefinitely starving GUI stop controls.

The protocol carries no sequence number, sensor timestamp, authentication, or device identity. Freshness is measured from local receipt time, not from the age of the original sensor measurement. Loopback limits network exposure but does not authenticate other local processes. Two simultaneous senders can produce inconsistent control and must be avoided.

## 6. Calibration and pointer mapping

Calibration lasts 1.5 seconds, requires at least 10 received samples, and rejects movement if either axis has a circular standard deviation over 3 degrees. These are prototype settings, not clinically validated thresholds.

The neutral angle is computed with `atan2(mean(sin(angle)), mean(cos(angle)))`. Circular averaging avoids an incorrect neutral near zero when samples straddle +180 and −180 degrees.

For each new sample:

1. Subtract neutral with wraparound into the interval [−180, 180).
2. Smooth the angular difference using `alpha = 1 - exp(-dt / tau)`.
3. Map angles inside the deadzone to the screen center.
4. Map the remaining range linearly to the corresponding screen half.
5. Clamp the normalized coordinate to [0, 1].
6. Reverse either axis if configured, then convert to pixels.

Default horizontal range is 20 degrees each side of neutral; vertical range is 15 degrees each side. Smoothing time constant is 0.10 seconds and the center deadzone is 1 degree. These values are starting points for testing. Smaller movement ranges make the pointer more sensitive. Larger smoothing constants slow its response and can increase lag.

This is **absolute angular pointing**: the same head orientation maps to the same screen location. Head orientation is not eye gaze. Translation, leaning, and eye movement are not treated as pointing measurements. The mapping assumes a stable seated relationship to the screen. Neutral does not automatically drift or recenter during operation.

Desktop bounds cover Windows' virtual desktop, including monitors with negative coordinates. Mapping across a rectangular virtual desktop can include gaps between monitors; nonrectangular layouts need hardware testing. DPI awareness is requested before window creation.

## 7. Dwell clicking

Dwell is off by default. When enabled, the controller creates an anchor at the current mapped pointer position. Staying within 14 pixels of that anchor for the default 1.2 seconds requests one click. Moving beyond the radius starts a new dwell interval.

After a click, the controller suppresses further clicks until the mapped pointer moves at least 40 pixels away from the clicked position. This prevents continuous clicking while the head remains still. The progress bar shows the current dwell fraction.

Dwell uses commanded pointer positions, not queried positions after physical mouse movement or application cursor warping. Mixing physical mouse use with active head control needs evaluation. There is no implemented right click, double click, drag lock, scroll mode, target snapping, or nod recognition. No claim is made that stillness reliably represents click intent for every user.

## 8. Windows input and pause behavior

The Windows backend uses `SetCursorPos` to move the pointer and `SendInput` to submit paired left-button down/up events. It declares the complete `INPUT` union so the Windows structure layout includes its keyboard and hardware variants. Tests check the expected structure size for the current pointer width.

`GetAsyncKeyState` is polled for Escape, F8, and F9 while the GUI loop runs. Input errors pause control. A partial click submission triggers a best-effort button release before reporting failure.

No valid packet for more than 0.35 seconds pauses an active session or calibration and clears the neutral pose. Reconnection requires calibration and explicit Start. The controller also resets filtering and dwell state across a sample gap. A stalled GUI cannot service stop keys until its loop resumes; this is a prototype polling design, not a separate watchdog service.

Windows restricts input across some privilege boundaries and desktops. Elevated applications, UAC prompts, lock screens, secure desktops, exclusive games, Remote Desktop, and mixed-DPI displays are not verified. The app does not request administrator privileges or bypass Windows restrictions.

## 9. Files and development workflow

| File | Responsibility |
|---|---|
| `app.py` | Tk UI, receiver, calibration collection, state transitions |
| `core.py` | Packet validation, filtering, pointer mapping, dwell logic |
| `windows_input.py` | Windows APIs and native input structures |
| `simulator.py` | Synthetic loopback motion sender |
| `tests/test_core.py` | Controller, packet, ABI-size, and UDP tests |
| `tests/test_app.py` | Headless receiver/application integration tests |
| `Start-Windows.cmd` | Launch Python app on Windows |
| `Start-Simulator.cmd` | Launch synthetic sender on Windows |

Run tests from this folder:

```powershell
py -3 -m unittest discover -s tests -v
```

Use a different UDP port only if both sender and receiver are configured to match:

```powershell
py -3 app.py --port 4243
py -3 simulator.py --port 4243
```

Settings are session-only and are not saved to disk. The app makes no cloud requests and has no telemetry or logging subsystem. It does not record audio or camera images. The behavior of the independently installed driver/bridge is outside this application's implementation.

## 10. Verification record and acceptance plan

**Performed:** Python 3.12.14 on Linux; 26 automated tests passed; Python source compilation passed; Tkinter import passed. Tests cover malformed/nonfinite packets, local UDP delivery, angular wraparound, center/extreme mapping, inversion, smoothing, calibration rejection, circular neutral averaging, dwell rearming, stale-signal handling, and expected native structure size. Headless GUI-logic tests use lightweight widget stand-ins and real UDP sockets.

**Not performed:** rendered GUI inspection, execution of user32 calls on Windows, live driver access, physical AirPods tracking, actual desktop clicks, Bluetooth reconnection tests, or participant trials. Passing logic tests does not verify those layers.

Complete these acceptance checks on the target PC before describing the app as functional with AirPods:

1. Record Windows version, AirPods model/firmware, adapter, and driver/bridge versions.
2. Confirm motion values change in the expected direction; confirm only one sender runs.
3. Calibrate in preview and reach each screen edge without exceeding comfortable movement.
4. Verify Pause, Escape, recalibration, and stop after disconnecting the AirPods.
5. Enable desktop mode and test on an ordinary non-elevated application.
6. Test one dwell click, no repeated stationary click, and rearming after moving away.
7. Test monitor boundaries and reconnect behavior.
8. Measure target selection time, target misses, accidental clicks, and user-rated comfort in a defined task. Label sample sizes and conditions. Do not report simulated results as participant results.

If motion cannot be obtained from the exact AirPods model, the receiver and simulator remain usable development components, but the live hardware milestone is unresolved. An iPhone or Mac forwarding bridge is a possible future integration, not included in this release.

## 11. Sources

Sources inspected during implementation; upstream behavior may change after the recorded commit.

- [AAP Head Tracker source and README](https://github.com/FIocker/aap-head-tracker), inspected commit `767bbd37b93979084bdcc3e4dc9b9f13c72f82ce`: bridge requirements, reported hardware testing, UDP sender interface, licensing.
- [MagicPods / MagicAAP](https://magicpods.app/): external driver provider linked by the bridge.
- [Microsoft SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput): synthetic input and privilege restrictions.
- [Microsoft INPUT structure](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input): native structure layout.
- [Microsoft SetCursorPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcursorpos): cursor positioning API.
- [Microsoft GetAsyncKeyState](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate): key-state polling.
- [Apple CMHeadphoneMotionManager](https://developer.apple.com/documentation/coremotion/cmheadphonemotionmanager): context for the separate Apple-platform API; not used by this Windows implementation.
- [Existing AirpodHeadmouse project](https://github.com/willwade/AirpodHeadmouse/): prior art for AirPods-based pointer control.
