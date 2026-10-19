"""AdaptPods Windows prototype. Default mode previews; desktop control is opt-in."""
import argparse
import math
import socket
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
from core import Controller, Settings, decode_pose
from windows_input import WindowsMouse


class App:
    def __init__(self, root, port):
        self.root = root
        self.controller = Controller()
        self.mouse = WindowsMouse() if sys.platform == 'win32' else None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', port))
        self.sock.setblocking(False)
        self.latest = None
        self.received_at = None
        self.running = False
        self.collect_until = None
        self.samples = []
        self.previous_keys = set()
        self.desktop = tk.BooleanVar(value=False)
        self.clicks = tk.BooleanVar(value=False)
        self.flip_x = tk.BooleanVar(value=False)
        self.flip_y = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value=f'Waiting for motion on 127.0.0.1:{port}. Preview only.')
        self.metrics = tk.StringVar(value='No motion data')
        self.progress = tk.DoubleVar(value=0)
        root.title('AdaptPods | Windows head mouse prototype')
        root.geometry('760x680')
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='AdaptPods', font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='AirPods motion → personalized pointer control').pack(anchor='w')
        ttk.Label(frame, textvariable=self.status, wraplength=700).pack(anchor='w', pady=10)
        ttk.Label(frame, textvariable=self.metrics).pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=10)
        for text, command in [('1. Calibrate neutral', self.calibrate),
                              ('2. Start / Pause', self.toggle), ('Stop', self.stop)]:
            ttk.Button(row, text=text, command=command).pack(side='left', padx=3)
        ttk.Checkbutton(frame, text='Control Windows desktop (off = preview)',
                        variable=self.desktop, command=self.mode_changed).pack(anchor='w')
        ttk.Checkbutton(frame, text='Enable dwell left-click (move away to rearm)',
                        variable=self.clicks, command=self.mode_changed).pack(anchor='w')
        settings = ttk.LabelFrame(frame, text='Personal movement settings', padding=8)
        settings.pack(fill='x', pady=10)
        self.entries = {}
        for i, (label, key, value) in enumerate([
            ('Horizontal range each side (degrees)', 'yaw_range', '20'),
            ('Vertical range each side (degrees)', 'pitch_range', '15'),
            ('Smoothing time (seconds)', 'smoothing_seconds', '0.10'),
            ('Center deadzone (degrees)', 'deadzone_degrees', '1'),
            ('Dwell duration (seconds)', 'dwell_seconds', '1.2')]):
            ttk.Label(settings, text=label).grid(row=i, column=0, sticky='w')
            entry = ttk.Entry(settings, width=12)
            entry.insert(0, value)
            entry.grid(row=i, column=1, padx=12)
            self.entries[key] = entry
        ttk.Checkbutton(settings, text='Reverse horizontal', variable=self.flip_x).grid(row=0, column=2)
        ttk.Checkbutton(settings, text='Reverse vertical', variable=self.flip_y).grid(row=1, column=2)
        ttk.Button(settings, text='Apply settings', command=self.apply).grid(row=4, column=2)
        self.canvas = tk.Canvas(frame, width=680, height=210, bg='#102032', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.create_text(340, 30, text='PREVIEW — no desktop control unless enabled', fill='#e5eef8')
        self.dot = self.canvas.create_oval(330, 95, 350, 115, fill='#53e0b0', outline='')
        ttk.Progressbar(frame, variable=self.progress, maximum=1).pack(fill='x', pady=8)
        ttk.Label(frame, text='F8: Start/Pause • F9: Calibrate • Esc: Stop (global on Windows)\n'
                  'After a signal gap, calibrate again. Dwell clicks are disabled by default.').pack(anchor='w')
        root.bind('<Escape>', lambda _: self.stop())
        root.bind('<F8>', lambda _: self.toggle() if not self.mouse else None)
        root.bind('<F9>', lambda _: self.calibrate() if not self.mouse else None)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(16, self.tick)

    def mode_changed(self):
        self.stop()
        if self.desktop.get() and not self.mouse:
            self.desktop.set(False)
            self.status.set('Desktop mode requires Windows; preview remains available.')

    def stop(self):
        self.running = False
        self.collect_until = None
        self.controller.suspend()
        self.progress.set(0)
        self.status.set('Paused. Calibrate if your neutral position changed.')

    def apply(self):
        try:
            values = {k: float(v.get()) for k, v in self.entries.items()}
            settings = Settings(**values, invert_x=self.flip_x.get(), invert_y=self.flip_y.get())
        except ValueError as exc:
            messagebox.showerror('Invalid settings', str(exc))
            return
        self.stop()
        self.controller.settings = settings
        self.status.set('Settings applied. Start when ready.')

    def calibrate(self):
        self.stop()
        self.controller.neutral = None
        if self.received_at is None or time.monotonic() - self.received_at > .35:
            self.status.set('No fresh motion. Start the AirPods bridge or simulator first.')
            return
        self.samples = []
        self.collect_until = time.monotonic() + 1.5
        self.status.set('Calibrating for 1.5 seconds: hold a comfortable neutral position.')

    def toggle(self):
        if self.running:
            self.stop()
        elif self.controller.neutral is None or self.collect_until is not None:
            self.status.set('Calibrate with fresh motion before starting.')
        elif self.received_at is None or time.monotonic() - self.received_at > .35:
            self.status.set('No fresh motion; cannot start.')
        else:
            self.controller.suspend()
            self.running = True
            self.status.set('ACTIVE — desktop' if self.desktop.get() else 'ACTIVE — preview only')

    def tick(self):
        now = time.monotonic()
        if self.mouse:
            down = {vk for vk in (0x1B, 0x77, 0x78) if self.mouse.key_down(vk)}
            new = down - self.previous_keys
            self.previous_keys = down
            if 0x1B in down:
                self.stop()
            elif 0x78 in new:
                self.calibrate()
            elif 0x77 in new:
                self.toggle()
        newest = None
        # Bound per-frame work so input floods cannot starve stop controls.
        for _ in range(256):
            try:
                data, _ = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            try:
                newest = decode_pose(data)
            except ValueError:
                continue
        if newest is not None:
            self.latest = newest
            self.received_at = now
            self.metrics.set('Yaw %.2f°   Pitch %.2f°   Roll %.2f°' % newest)
            if self.collect_until is not None:
                self.samples.append(newest[:2])
        stale = self.received_at is None or now - self.received_at > .35
        if stale:
            if self.running or self.collect_until is not None:
                self.stop()
                self.controller.neutral = None
                self.status.set('Signal lost. Reconnect, then calibrate again.')
        elif self.collect_until is not None and now >= self.collect_until:
            self.collect_until = None
            if len(self.samples) < 10:
                self.status.set('Too few calibration samples. Try again.')
            else:
                means = []
                spreads = []
                for axis in zip(*self.samples):
                    rad = [math.radians(a) for a in axis]
                    resultant = math.hypot(sum(map(math.sin, rad)), sum(map(math.cos, rad))) / len(rad)
                    mean = math.degrees(math.atan2(sum(map(math.sin, rad)), sum(map(math.cos, rad))))
                    means.append(mean)
                    spreads.append(math.degrees(math.sqrt(-2 * math.log(max(1e-12, min(1, resultant))))))
                if max(spreads) > 3:
                    self.status.set('Too much movement during calibration. Try holding neutral again.')
                else:
                    self.controller.calibrate(*means)
                    self.status.set('Neutral calibrated. Select preview or desktop, then Start.')
        if newest is not None and self.running:
            try:
                bounds = self.mouse.bounds() if self.desktop.get() else (0, 0, self.canvas.winfo_width(), self.canvas.winfo_height())
                point = self.controller.update(*newest[:2], now, bounds)
                if point:
                    if self.desktop.get():
                        self.mouse.move(*point)
                    else:
                        x, y = point
                        self.canvas.coords(self.dot, x-10, y-10, x+10, y+10)
                    click, progress = self.controller.dwell(point, now, self.clicks.get())
                    self.progress.set(progress)
                    if click:
                        if self.desktop.get():
                            self.mouse.click()
                        else:
                            self.canvas.itemconfig(self.dot, fill='#f5c451')
                    elif progress == 0:
                        self.canvas.itemconfig(self.dot, fill='#53e0b0')
            except (OSError, RuntimeError, ValueError) as exc:
                self.stop()
                self.status.set('Stopped: ' + str(exc))
        self.root.after(16, self.tick)

    def close(self):
        self.stop()
        self.sock.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4242)
    args = parser.parse_args()
    root = tk.Tk()
    try:
        App(root, args.port)
    except OSError as exc:
        messagebox.showerror('Cannot open motion receiver', str(exc))
        root.destroy()
        return
    root.mainloop()

if __name__ == '__main__':
    main()
