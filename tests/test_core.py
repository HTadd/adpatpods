import ctypes
import math
import socket
import struct
import unittest
from core import Controller, Settings, angle_delta, decode_pose
from simulator import packet
from windows_input import INPUT

class MotionTests(unittest.TestCase):
    def test_decode(self):
        self.assertEqual(decode_pose(packet(5, -2, 3)), (5, -2, 3))
    def test_reject_bad_length(self):
        for size in (0, 47, 49, 100):
            with self.assertRaises(ValueError): decode_pose(bytes(size))
    def test_reject_nonfinite_and_range(self):
        for value in (math.nan, math.inf, -math.inf, 361):
            with self.assertRaises(ValueError): decode_pose(packet(value, 0))
    def test_wrap(self):
        self.assertEqual(angle_delta(-179, 179), 2)
    def test_uncalibrated(self):
        self.assertIsNone(Controller().update(0, 0, 1, (0,0,100,100)))
    def test_center(self):
        c = Controller(); c.calibrate(12, 4)
        self.assertEqual(c.update(12, 4, 1, (0,0,1921,1081)), (960,540))
    def test_extremes_and_virtual_desktop(self):
        c = Controller(); c.calibrate(0,0)
        self.assertEqual(c.update(50,-50,1,(-1920,0,3840,1080)), (1919,0))
    def test_inversion(self):
        c=Controller(Settings(invert_x=True, invert_y=True)); c.calibrate(0,0)
        self.assertEqual(c.update(50,-50,1,(0,0,100,100)), (0,99))
    def test_deadzone(self):
        c=Controller(); c.calibrate(0,0)
        self.assertEqual(c.update(.5,-.9,1,(0,0,101,101)), (50,50))
    def test_smoothing(self):
        c=Controller(); c.calibrate(0,0)
        c.update(0,0,1,(0,0,1001,1001))
        x,_=c.update(20,0,1.02,(0,0,1001,1001))
        self.assertGreater(x,500); self.assertLess(x,1000)
    def test_gap_resets_filter(self):
        c=Controller(); c.calibrate(0,0)
        c.update(0,0,1,(0,0,101,101))
        self.assertEqual(c.update(20,0,2,(0,0,101,101))[0],100)
    def test_monotonic_time(self):
        c=Controller(); c.calibrate(0,0); c.update(0,0,2,(0,0,101,101))
        with self.assertRaises(ValueError): c.update(0,0,1,(0,0,101,101))
    def test_dwell_once_and_rearm(self):
        c=Controller()
        self.assertFalse(c.dwell((20,20),0,True)[0])
        self.assertTrue(c.dwell((20,20),1.3,True)[0])
        self.assertFalse(c.dwell((20,20),5,True)[0])
        self.assertFalse(c.dwell((80,20),6,True)[0])
        self.assertTrue(c.dwell((80,20),7.3,True)[0])
    def test_dwell_movement_resets(self):
        c=Controller(); c.dwell((0,0),0,True)
        self.assertEqual(c.dwell((20,0),1,True),(False,0))
        self.assertFalse(c.dwell((20,0),1.5,True)[0])
    def test_suspend_resets_dwell(self):
        c=Controller(); c.dwell((0,0),0,True); c.suspend()
        self.assertFalse(c.dwell((0,0),5,True)[0])
    def test_disabled_click(self):
        c=Controller(); c.dwell((0,0),0,True)
        self.assertEqual(c.dwell((0,0),5,False),(False,0))
    def test_settings(self):
        for values in ({'yaw_range':0},{'pitch_range':math.nan},{'deadzone_degrees':20},
                       {'dwell_seconds':-1},{'rearm_distance':10}):
            with self.assertRaises(ValueError): Settings(**values)
    def test_windows_input_abi(self):
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)
    def test_loopback_udp(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
            receiver.bind(('127.0.0.1',0)); receiver.settimeout(1)
            sender.sendto(packet(13,-8),receiver.getsockname())
            self.assertEqual(decode_pose(receiver.recv(100)),(13,-8,0))

if __name__ == '__main__': unittest.main()
