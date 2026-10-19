# AdaptPods — Windows head mouse prototype

**Status: implemented prototype; live Windows/AirPods operation is not verified.**

AdaptPods converts head-orientation packets into a personalized pointer position. It includes a Windows desktop mode, a preview canvas, neutral-position calibration, adjustable movement ranges, time-based smoothing, optional dwell left-clicking, global Windows stop/pause controls, a synthetic motion sender, and automated tests.

Read **HOW_IT_WORKS.html** for the full technical write-up, installation instructions, validation status, and remaining work.

## Download

On this GitHub repository page:

1. Click the green **Code** button.
2. Select **Download ZIP**.
3. Right-click the downloaded ZIP in Windows File Explorer and select **Extract All**.
4. Open the extracted project folder. Run the launchers from the extracted folder, not from inside the ZIP.
5. Open `HOW_IT_WORKS.md` on GitHub for the full setup guide, or open `HOW_IT_WORKS.html` locally in a browser.

The download contains Python source and launchers, not a prebuilt Windows executable. Python is required. The external AirPods driver and bridge are installed separately; they are not included in this download.

## Quick start without AirPods

1. Extract this folder on your Windows PC.
2. Install Python 3.10 or newer with Tcl/Tk and the Python launcher. The official Windows installer provides these components as options: https://www.python.org/downloads/windows/
3. Double-click `Start-Windows.cmd`.
4. Double-click `Start-Simulator.cmd` in another window. This sends **synthetic data**, not AirPods measurements.
5. Select **Calibrate neutral**, hold until calibration finishes, then select **Start / Pause**. Watch the preview dot. The simulator begins moving after four seconds.
6. To test actual Windows pointer movement, check **Control Windows desktop**, then Start again. F8 pauses; F9 recalibrates; Escape stops. Dwell clicks are off unless explicitly enabled.

No pip packages are required. A Python installation without Tk will need its Tk component installed. This package is source code, not a compiled `.exe`.

## Real AirPods input

This prototype relies on a separate experimental Windows motion bridge and its driver. Pairing AirPods over ordinary Bluetooth alone is insufficient for this integration. See the technical write-up before installing anything.

## Tests

From this folder:

```text
py -3 -m unittest discover -s tests -v
```

26 automated tests passed in the Linux development environment. This does not establish Windows API operation, physical AirPods compatibility, accessibility benefit, or measured end-to-end latency.
