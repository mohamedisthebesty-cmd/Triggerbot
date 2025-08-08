import os
import tkinter as tk
from ttkbootstrap import Style
from ttkbootstrap.widgets import Button
import subprocess
import socket
import threading
import time
import sys

# === 1. Get absolute paths ===
base_path = os.path.dirname(os.path.abspath(__file__))
combo_path = os.path.join(base_path, "combo.py")
overlaybox_path = os.path.join(base_path, "overlay_box.py")

# === 2. Start overlay_box.py and combo.py ===
combo_proc = subprocess.Popen([sys.executable, combo_path])
overlaybox_proc = subprocess.Popen([sys.executable, overlaybox_path])

# === 3. Wait for triggerbot socket to be ready ===
def wait_for_socket():
    while True:
        try:
            s = socket.create_connection(('localhost', 65433))
            return s
        except:
            time.sleep(0.2)

sock = wait_for_socket()

# === 3. GUI Setup ===
app = tk.Tk()
app.title("Triggerbot Controller")
app.geometry("240x180")
app.attributes("-topmost", True)
app.resizable(False, False)

style = Style("superhero")
state = {"enabled": False}

# === 4. Helpers ===
def update_button():
    if state["enabled"]:
        button.config(text="ON", bootstyle="success-outline")
        status_label.config(text="Status: ACTIVE", foreground="lime")
    else:
        button.config(text="OFF", bootstyle="danger-outline")
        status_label.config(text="Status: INACTIVE", foreground="red")

def toggle():
    try:
        sock.send(b"toggle")
        time.sleep(0.1)
        response = sock.recv(1024).decode()
        state["enabled"] = response == "on"
        update_button()
    except:
        pass

def check_status():
    try:
        sock.send(b"status")
        response = sock.recv(1024).decode()
        state["enabled"] = response == "on"
        update_button()
    except:
        pass
    app.after(1000, check_status)

def shutdown():
    try:
        sock.send(b"exit")
        sock.close()
    except:
        pass

    try:
        combo_proc.terminate()
        overlaybox_proc.terminate()
    except:
        pass

    try:
        combo_proc.terminate()
    except:
        pass

    app.destroy()

# === 5. Widgets ===
button = Button(app,
                text="OFF",
                bootstyle="danger-outline",
                width=10,
                padding=20,
                command=toggle)
button.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

status_label = tk.Label(app, text="Status: UNKNOWN", font=("Segoe UI", 10))
status_label.pack(side="bottom", pady=10)

# === 6. Main ===
app.protocol("WM_DELETE_WINDOW", shutdown)
app.after(1000, check_status)
app.mainloop()
