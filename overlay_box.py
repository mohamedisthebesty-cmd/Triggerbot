import tkinter as tk
import win32gui, win32con, win32api
import socket
import threading

BOX_SIZE = 400
COLOR = "#00FFFF"  # Cyan

def make_overlay():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "black")
    root.geometry(f"{BOX_SIZE}x{BOX_SIZE}+{win32api.GetSystemMetrics(0)//2 - BOX_SIZE//2}+{win32api.GetSystemMetrics(1)//2 - BOX_SIZE//2}")
    root.configure(bg="black")

    canvas = tk.Canvas(root, width=BOX_SIZE, height=BOX_SIZE, bg="black", highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(1, 1, BOX_SIZE-1, BOX_SIZE-1, outline=COLOR, width=2)

    # Make click-through using Win32 API
    hwnd = win32gui.FindWindow(None, str(root.title()))
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)

    return root

def listen_for_toggle():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 65434))
    sock.listen(1)
    conn, _ = sock.accept()

    while True:
        data = conn.recv(1024).decode().strip()
        if data == "show":
            app.deiconify()
        elif data == "hide":
            app.withdraw()
        elif data == "exit":
            break

    conn.close()
    sock.close()
    app.quit()

app = make_overlay()
app.withdraw()  # Start hidden
threading.Thread(target=listen_for_toggle, daemon=True).start()
app.mainloop()
