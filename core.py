"""Platform-independent orientation-to-pointer controller. Degrees and monotonic seconds."""
from dataclasses import dataclass
import math
import struct


def decode_pose(data):
    if len(data) != 48:
        raise ValueError('Expected 48-byte OpenTrack packet')
    values = struct.unpack('<6d', data)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite pose')
    yaw, pitch, roll = values[3:]
    if any(abs(v) > 360 for v in (yaw, pitch, roll)):
        raise ValueError('Rotation out of range')
    return yaw, pitch, roll


def angle_delta(value, origin):
    return (value - origin + 180) % 360 - 180


@dataclass
class Settings:
    yaw_range: float = 20.0  # each side of neutral
    pitch_range: float = 15.0
    smoothing_seconds: float = 0.10
    deadzone_degrees: float = 1.0
    stale_seconds: float = 0.35
    dwell_seconds: float = 1.2
    dwell_radius: float = 14.0
    rearm_distance: float = 40.0
    invert_x: bool = False
    invert_y: bool = False

    def __post_init__(self):
        for name in ('yaw_range', 'pitch_range', 'smoothing_seconds',
                     'stale_seconds', 'dwell_seconds', 'dwell_radius', 'rearm_distance'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(name + ' must be positive and finite')
        if not 0 <= self.deadzone_degrees < min(self.yaw_range, self.pitch_range):
            raise ValueError('Deadzone must be smaller than movement range')
        if self.rearm_distance <= self.dwell_radius:
            raise ValueError('Rearm distance must exceed dwell radius')


class Controller:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.neutral = None
        self.filtered = None
        self.last_time = None
        self.reset_dwell()

    def reset_dwell(self):
        self.anchor = None
        self.anchor_time = None
        self.clicked_at = None

    def calibrate(self, yaw, pitch):
        if not all(math.isfinite(v) for v in (yaw, pitch)):
            raise ValueError('Invalid neutral pose')
        self.neutral = (yaw, pitch)
        self.filtered = None
        self.last_time = None
        self.reset_dwell()

    def suspend(self):
        self.filtered = None
        self.last_time = None
        self.reset_dwell()

    def map_axis(self, delta, extent):
        dz = self.settings.deadzone_degrees
        if abs(delta) <= dz:
            return 0.5
        scaled = math.copysign((abs(delta) - dz) / (extent - dz), delta)
        return max(0.0, min(1.0, 0.5 + 0.5 * scaled))

    def update(self, yaw, pitch, now, bounds):
        if self.neutral is None:
            return None
        if not all(math.isfinite(v) for v in (yaw, pitch, now)):
            raise ValueError('Invalid sample')
        s = self.settings
        delta = [angle_delta(yaw, self.neutral[0]), angle_delta(pitch, self.neutral[1])]
        dt = None if self.last_time is None else now - self.last_time
        if dt is not None and dt <= 0:
            raise ValueError('Samples must advance in time')
        if self.filtered is None or dt is None or dt > s.stale_seconds:
            self.filtered = delta
            self.reset_dwell()
        else:
            alpha = 1 - math.exp(-dt / s.smoothing_seconds)
            self.filtered = [a + alpha * angle_delta(b, a) for a, b in zip(self.filtered, delta)]
        self.last_time = now
        x = self.map_axis(self.filtered[0], s.yaw_range)
        y = self.map_axis(self.filtered[1], s.pitch_range)
        if s.invert_x:
            x = 1 - x
        if s.invert_y:
            y = 1 - y
        left, top, width, height = bounds
        return round(left + x * (width - 1)), round(top + y * (height - 1))

    def dwell(self, point, now, enabled):
        if not enabled:
            self.reset_dwell()
            return False, 0.0
        s = self.settings
        if self.clicked_at is not None:
            if math.dist(point, self.clicked_at) < s.rearm_distance:
                return False, 0.0
            self.clicked_at = None
            self.anchor = None
        if self.anchor is None or math.dist(point, self.anchor) > s.dwell_radius:
            self.anchor, self.anchor_time = point, now
            return False, 0.0
        progress = min(1.0, max(0.0, (now - self.anchor_time) / s.dwell_seconds))
        if progress >= 1:
            self.clicked_at = point
            return True, 1.0
        return False, progress
