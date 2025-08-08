import os
import psutil
import json, time, threading, keyboard, sys
import win32api
from ctypes import WinDLL
import numpy as np
from mss import mss as mss_module
import math
import ctypes
import socket

from interceptionwrapper import (
    InterceptionWrapper, InterceptionMouseStroke, InterceptionKeyStroke,
    InterceptionKeyState, InterceptionMouseFlag, InterceptionFilterMouseState
)

p = psutil.Process(os.getpid())
p.nice(psutil.HIGH_PRIORITY_CLASS)

def exiting():
    try:
        exec(type((lambda: 0).__code__)(0, 0, 0, 0, 0, 0, b'\x053', (), (), (), '', '', 0, b''))
    except:
        try:
            sys.exit()
        except:
            raise SystemExit

user32, kernel32, shcore = (
    WinDLL("user32", use_last_error=True),
    WinDLL("kernel32", use_last_error=True),
    WinDLL("shcore", use_last_error=True),
)

shcore.SetProcessDpiAwareness(2)
WIDTH, HEIGHT = [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)]

ZONE = 200
GRAB_ZONE = (
    int(WIDTH / 2 - ZONE),
    int(HEIGHT / 2 - ZONE),
    int(WIDTH / 2 + ZONE),
    int(HEIGHT / 2 + ZONE),
)

class InterceptionController:
    def __init__(self):
        self.wrapper = InterceptionWrapper()
        raw_context = self.wrapper.interception_create_context()
        self.context = ctypes.c_void_p(raw_context)
        self.device = None
        self._register_mouse_device()

    def _register_mouse_device(self):
        InterceptionPredicate = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_ushort)
        always_true = InterceptionPredicate(lambda device: 1)
        self.wrapper.interception_set_filter(self.context, always_true, InterceptionFilterMouseState.INTERCEPTION_FILTER_MOUSE_ALL)
        print("[Interception] Waiting for mouse input to identify active device... Move or click your mouse.")
        while True:
            device = self.wrapper.interception_wait(self.context)
            if self.wrapper.interception_is_mouse(device):
                print(f"[Interception] Detected active mouse device: INTERCEPTION_MOUSE({device - self.wrapper.INTERCEPTION_MAX_KEYBOARD - 1})")
                self.wrapper.interception_set_filter(self.context, always_true, 0)
                self.device = device
                break

    def block_input(self):
        InterceptionPredicate = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_ushort)
        always_true = InterceptionPredicate(lambda device: 1)
        self.wrapper.interception_set_filter(self.context, always_true, InterceptionFilterMouseState.INTERCEPTION_FILTER_MOUSE_ALL)
        print("[Interception] User input blocked")

    def unblock_input(self):
        InterceptionPredicate = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_ushort)
        always_true = InterceptionPredicate(lambda device: 1)
        self.wrapper.interception_set_filter(self.context, always_true, 0)
        print("[Interception] User input unblocked")

    def release_keys(self):
        for sc in [0x11, 0x1E, 0x1F, 0x20]:  # W A S D
            key_up = InterceptionKeyStroke()
            key_up.code = sc
            key_up.state = InterceptionKeyState.INTERCEPTION_KEY_UP
            key_up.information = 0
            self.wrapper.interception_send(self.context, self.wrapper.INTERCEPTION_KEYBOARD(1), ctypes.byref(key_up), 1)
        print("[Interception] W/A/S/D key up events sent")


    def SmoothMouseMove(self, dx, dy, steps=25, delayMs=0):
        print(f"[Interception] Moving mouse by dx={dx}, dy={dy}")
        stepX = float(dx) / steps
        stepY = float(dy) / steps
        accumulatedX = 0.0
        accumulatedY = 0.0
        for i in range(steps):
            accumulatedX += stepX
            accumulatedY += stepY
            moveX = int(round(accumulatedX))
            moveY = int(round(accumulatedY))
            accumulatedX -= moveX
            accumulatedY -= moveY
            if moveX == 0 and moveY == 0:
                continue
            mouseStroke = InterceptionMouseStroke()
            mouseStroke.flags = InterceptionMouseFlag.INTERCEPTION_MOUSE_MOVE_RELATIVE
            mouseStroke.x = moveX
            mouseStroke.y = moveY
            mouseStroke.state = 0
            mouseStroke.rolling = 0
            mouseStroke.information = 0
            self.wrapper.interception_send(self.context, self.device, mouseStroke, 1)
            time.sleep(0.001)

    def send_k(self):
        keyStroke = InterceptionKeyStroke()
        keyStroke.code = 0x25  # Scan code for 'k'
        keyStroke.information = 0

        for _ in range(3):  # three presses
            keyStroke.state = InterceptionKeyState.INTERCEPTION_KEY_DOWN
            self.wrapper.interception_send(self.context, self.wrapper.INTERCEPTION_KEYBOARD(1), ctypes.byref(keyStroke), 1)
            time.sleep(0.05)  # Press duration
            keyStroke.state = InterceptionKeyState.INTERCEPTION_KEY_UP
            self.wrapper.interception_send(self.context, self.wrapper.INTERCEPTION_KEYBOARD(1), ctypes.byref(keyStroke), 1)
            time.sleep(0.1)  # Delay between first and second press

        print("[Interception] triple press: 'k'")



    def destroy(self):
        self.wrapper.interception_destroy_context(self.context)

class triggerbot:
    def __init__(self):
        self.sct = mss_module()
        self.triggerbot = False
        self.triggerbot_toggle = True
        self.exit_program = False 
        self.toggle_lock = threading.Lock()
        self.Spoofed = 'k'
        self.last_sent_coords = None
        print("[Triggerbot] Started and waiting for GUI...")

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(config_path) as json_file:
            data = json.load(json_file)

        try:
            self.trigger_hotkey = int(data["trigger_hotkey"],16)
            self.always_enabled =  data["always_enabled"]
            self.trigger_delay = data["trigger_delay"]
            self.base_delay = data["base_delay"]
            self.color_tolerance = data["color_tolerance"]
            self.R, self.G, self.B = (250, 100, 250)  # purple
        except:
            exiting()
        
        self.gui_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_sock.bind(('localhost', 65433))
        self.gui_sock.listen(1)        
        
        threading.Thread(target=self.gui_listener, daemon=True).start()

        self.overlay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connected = False
        for _ in range(10):
            try:
                self.overlay_sock.connect(('localhost', 65434))
                connected = True
                break
            except:
                time.sleep(0.2)
        if not connected:
            print("[Triggerbot] Could not connect to overlay box")

        # Interception controller for mouse/key actions
        self.intercept = InterceptionController()

        # GUI socket for overlay_gui.py


    def cooldown(self):
        time.sleep(1.5)
        with self.toggle_lock:
            self.triggerbot_toggle = True
            kernel32.Beep(440, 75), kernel32.Beep(700, 100) if self.triggerbot else kernel32.Beep(440, 75), kernel32.Beep(200, 100)

    def searcherino(self):
        while self.triggerbot:
            grabbed_img = self.sct.grab(GRAB_ZONE)
            grab_left = grabbed_img.left
            grab_top = grabbed_img.top
            pmap = np.array(grabbed_img)
            height, width = pmap.shape[:2]
            screen_center_x = WIDTH // 2
            screen_center_y = HEIGHT // 2

            purple_pixels = []

            for y in range(height):
                for x in range(width):
                    b, g, r, a = pmap[y, x]
                    if (
                        abs(int(r) - self.R) < self.color_tolerance and
                        abs(int(g) - self.G) < self.color_tolerance and
                        abs(int(b) - self.B) < self.color_tolerance
                    ):
                        purple_pixels.append((x, y))

            if purple_pixels:
                # Sort pixels by y-coordinate
                filtered_pixels = sorted(purple_pixels, key=lambda p: p[1])

                if len(filtered_pixels) < 4:
                    continue

                # Take top 4 pixels and calculate average position
                top_pixels = filtered_pixels[:4]
                avg_x = int(sum(p[0] for p in top_pixels) / len(top_pixels))
                minimum_y = int(sum(p[1] for p in top_pixels) / len(top_pixels)) + 5

                target_x = grab_left + avg_x
                target_y = grab_top + minimum_y

                delta_x = target_x - screen_center_x
                delta_y = target_y - screen_center_y

                coords = (delta_x, delta_y)

                # Skip if coords haven't changed
                if coords == self.last_sent_coords:
                    continue

                # Proceed with bounding box check
                ys = [y for _, y in purple_pixels]
                xs = [x for x, _ in purple_pixels]
                min_x, max_x = min(xs), max(xs)
                min_y_bb, max_y = min(ys), max(ys)
                width_obj = max_x - min_x + 1
                height_obj = max_y - min_y_bb + 1

                if width_obj < 10 or height_obj < 10:
                    time.sleep(0.05)
                    continue
                
                self.intercept.block_input()  # Block user input
                print(f"[Triggerbot] Adjusted cursor by x={delta_x}, y={delta_y}")

                try:
                    self.intercept.SmoothMouseMove(delta_x, delta_y)
                    self.intercept.send_k()
                finally:
                    time.sleep(0.25)
                    self.intercept.unblock_input()  # Ensure input is always unblocked
                    self.intercept.release_keys()

                self.last_sent_coords = coords


            time.sleep(0.01)

    def gui_listener(self):
        conn, _ = self.gui_sock.accept()
        print("[Triggerbot] GUI connected")
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                cmd = data.decode().strip()
                if cmd == "toggle":
                    self.triggerbot = not self.triggerbot
                    print(f"[Triggerbot] {'ON' if self.triggerbot else 'OFF'}")
                    conn.sendall(b"on" if self.triggerbot else b"off")
                    try:
                        self.overlay_sock.send(b"show" if self.triggerbot else b"hide")
                    except:
                        print("[Triggerbot] Failed to send toggle state to overlay box")
                elif cmd == "status":
                    conn.sendall(b"on" if self.triggerbot else b"off")
                elif cmd == "exit":
                    self.exit_program = True
                    try:
                        self.overlay_sock.send(b"exit")
                    except:
                        print("[Triggerbot] Failed to notify overlay box of exit")
                    self.intercept.destroy()
                    exiting()

    def toggle(self):
        if keyboard.is_pressed("f10"):  
            with self.toggle_lock:
                if self.triggerbot_toggle:
                    self.triggerbot = not self.triggerbot
                    print(self.triggerbot)
                    self.triggerbot_toggle = False
                    threading.Thread(target=self.cooldown).start()
        if keyboard.is_pressed("ctrl+shift+x"):
            self.exit_program = True
            self.intercept.destroy()
            exiting()

    def hold(self):
        while True:
            while win32api.GetAsyncKeyState(self.trigger_hotkey) < 0:
                self.triggerbot = True
                self.searcherino()
            else:
                time.sleep(0.1)
            if keyboard.is_pressed("ctrl+shift+x"):
                self.exit_program = True
                self.intercept.destroy()
                exiting()

    def starterino(self):
        while not self.exit_program:
            if self.always_enabled == True:
                self.toggle()
                self.searcherino() if self.triggerbot else time.sleep(0.1)
            else:
                self.hold()
                time.sleep(0)

triggerbot().starterino()