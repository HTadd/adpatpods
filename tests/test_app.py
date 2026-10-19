"""Headless integration checks exercise real receiver and application tick logic."""
import socket
import time
import unittest
from app import App
from core import Controller
from simulator import packet

class Value:
    def __init__(self,value=None): self.value=value
    def set(self,value): self.value=value
    def get(self): return self.value
class Root:
    def after(self,*args): pass
class Canvas:
    def winfo_width(self): return 101
    def winfo_height(self): return 101
    def coords(self,*args): self.last=args
    def itemconfig(self,*args,**kwargs): pass

class AppTests(unittest.TestCase):
    def setUp(self):
        a=self.a=App.__new__(App)
        a.root=Root(); a.mouse=None; a.controller=Controller()
        a.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        a.sock.bind(('127.0.0.1',0)); a.sock.setblocking(False)
        a.latest=None; a.received_at=None; a.running=False; a.collect_until=None
        a.samples=[]; a.previous_keys=set(); a.desktop=Value(False); a.clicks=Value(False)
        a.status=Value(''); a.metrics=Value(''); a.progress=Value(0)
        a.canvas=Canvas(); a.dot=1
        self.sender=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    def tearDown(self): self.a.sock.close(); self.sender.close()
    def send(self,data): self.sender.sendto(data,self.a.sock.getsockname())
    def test_preview_receives_and_maps(self):
        a=self.a; a.controller.calibrate(0,0); a.running=True
        self.send(packet(20,0)); a.tick()
        self.assertEqual(a.canvas.last,(1,90,40,110,60))
        self.assertTrue(a.running)
    def test_signal_loss_requires_recalibration(self):
        a=self.a; a.controller.calibrate(0,0); a.running=True
        a.received_at=time.monotonic()-1; a.tick()
        self.assertFalse(a.running); self.assertIsNone(a.controller.neutral)
    def test_invalid_packet_does_not_refresh_signal(self):
        self.send(b'wrong'); self.a.tick(); self.assertIsNone(self.a.received_at)
    def test_no_start_without_calibration(self):
        self.a.received_at=time.monotonic(); self.a.toggle()
        self.assertFalse(self.a.running)
    def test_calibration_rejects_sparse_data(self):
        a=self.a; a.received_at=time.monotonic(); a.calibrate()
        a.collect_until=time.monotonic()-.01; a.tick()
        self.assertIsNone(a.controller.neutral)
    def test_calibration_circular_mean(self):
        a=self.a; a.received_at=time.monotonic(); a.calibrate()
        a.samples=[(179,0),(-179,0)]*10
        a.collect_until=time.monotonic()-.01; a.tick()
        self.assertAlmostEqual(abs(a.controller.neutral[0]),180)
    def test_calibration_rejects_movement(self):
        a=self.a; a.received_at=time.monotonic(); a.calibrate()
        a.samples=[(20,0),(-20,0)]*10
        a.collect_until=time.monotonic()-.01; a.tick()
        self.assertIsNone(a.controller.neutral)

if __name__=='__main__': unittest.main()
