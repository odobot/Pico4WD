import time
import network
import socket
from machine import Pin

# ========= WIFI CONFIG =========
SSID = "----------"
PASSWORD = "----------"

LED1 = Pin(16, Pin.OUT)

# (Optional) set your country code for Wi-Fi regs (uncomment if needed)
# import rp2
# rp2.country('KE')

# ========= MOTOR PIN MAP (your wiring) =========
# Each wheel has two pins: (IN1, IN2). Forward = (1,0), Backward = (0,1), Stop = (0,0)
PINS_FL = (18, 19)  # Front Left
PINS_FR = (9,  8)   # Front Right
PINS_RL = (21, 20)  # Rear Left
PINS_RR = (7,  6)   # Rear Right

# If any wheel spins the opposite direction, set its invert flag True
INVERT_FL = False
INVERT_FR = False
INVERT_RL = False
INVERT_RR = False

# ========= BUILD WHEEL OBJECTS =========
class Wheel:
    def __init__(self, in1_pin, in2_pin, invert=False):
        self.in1 = Pin(in1_pin, Pin.OUT, value=0)
        self.in2 = Pin(in2_pin, Pin.OUT, value=0)
        self.invert = invert

    def drive(self, direction):
        """
        direction:  1 = forward, -1 = backward, 0 = stop
        """
        if direction == 0:
            a, b = 0, 0
        elif direction == 1:       # forward
            a, b = 1, 0
        elif direction == -1:      # backward
            a, b = 0, 1
        else:
            a, b = 0, 0

        if self.invert:
            a, b = b, a

        self.in1.value(a)
        self.in2.value(b)

# Create the four wheels
W_FL = Wheel(*PINS_FL, invert=INVERT_FL)
W_FR = Wheel(*PINS_FR, invert=INVERT_FR)
W_RL = Wheel(*PINS_RL, invert=INVERT_RL)
W_RR = Wheel(*PINS_RR, invert=INVERT_RR)

# ========= HIGH-LEVEL MOVES =========
STATE = "STOP"

def all_stop():
    global STATE
    for w in (W_FL, W_FR, W_RL, W_RR):
        w.drive(0)
    STATE = "STOP"

def move_forward():
    global STATE
    W_FL.drive(1); W_FR.drive(1); W_RL.drive(1); W_RR.drive(1)
    STATE = "FORWARD"

def move_backward():
    global STATE
    W_FL.drive(-1); W_FR.drive(-1); W_RL.drive(-1); W_RR.drive(-1)
    STATE = "BACKWARD"

def turn_left(pivot=True):
    """
    pivot=True  -> spin in place: left wheels backward, right wheels forward
    pivot=False -> gentle turn: left wheels stop, right wheels forward
    """
    global STATE
    if pivot:
        W_FL.drive(-1); W_RL.drive(-1)
        W_FR.drive(1);  W_RR.drive(1)
    else:
        W_FL.drive(0);  W_RL.drive(0)
        W_FR.drive(1);  W_RR.drive(1)
    STATE = "LEFT"

def turn_right(pivot=True):
    global STATE
    if pivot:
        W_FL.drive(1);  W_RL.drive(1)
        W_FR.drive(-1); W_RR.drive(-1)
    else:
        W_FL.drive(1);  W_RL.drive(1)
        W_FR.drive(0);  W_RR.drive(0)
    STATE = "RIGHT"

# ========= WIFI CONNECT =========
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        # wait up to ~15 seconds
        for _ in range(60):
            if wlan.isconnected():
                break
            time.sleep(0.25)
    if not wlan.isconnected():
        raise RuntimeError("Wi-Fi connection failed")
    ip = wlan.ifconfig()[0]
    print("Connected, IP:", ip)
    return ip

# ========= HTTP RESPONSES =========
HTML = """\
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pico 4WD</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;margin:0;padding:24px;background:#0b1220;color:#e6eaf2}
  h1{font-size:22px;margin:0 0 12px}
  .card{background:#111a2e;border:1px solid #203156;border-radius:16px;padding:12px;margin:0 0 16px;max-width:520px}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  .pad{display:grid;grid-template-columns:repeat(3,110px);grid-auto-rows:70px;gap:10px;justify-content:center;align-items:center;max-width:520px}
  button{height:100%;width:100%;font-size:16px;border:0;border-radius:12px;background:#1c2a48;color:#e6eaf2;cursor:pointer}
  button:hover{filter:brightness(1.15)}
  .ok{background:#1f6feb}.danger{background:#d1495b}.muted{background:#30384c}.warn{background:#e39a1f}
  .wide{grid-column:1 / span 3}
</style>
</head>
<body>
  <h1>CEMASTEA 4WD Control</h1>
  <div class="card">Status: <span id="status" class="mono">...</span></div>

  <div class="pad">
    <div></div>
    <button class="ok" onclick="cmd('/forward')">Forward</button>
    <div></div>

    <button class="warn" onclick="cmd('/left')">Left</button>
    <button class="muted" onclick="cmd('/stop')">Stop</button>
    <button class="warn" onclick="cmd('/right')">Right</button>

    <div></div>
    <button class="danger" onclick="cmd('/backward')">Backward</button>
    <div></div>
  </div>

<script>
async function cmd(path){
  try{
    const r = await fetch(path, {cache:'no-store'});
    const j = await r.json();
    document.getElementById('status').textContent = j.state || JSON.stringify(j);
  }catch(e){
    document.getElementById('status').textContent = 'ERR';
  }
}
async function refresh(){
  try{
    const r = await fetch('/status', {cache:'no-store'});
    const j = await r.json();
    document.getElementById('status').textContent = j.state;
  }catch(e){
    document.getElementById('status').textContent = 'ERR';
  }
}
refresh();
setInterval(refresh, 1200);
</script>
</body>
</html>
"""

def http_response(body_bytes, content_type="text/html; charset=utf-8", status="200 OK"):
    hdr = (
        "HTTP/1.1 " + status + "\r\n"
        "Content-Type: " + content_type + "\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    return hdr.encode() + body_bytes

def json_body(d):
    import json
    return json.dumps(d).encode()

# ========= ROUTER =========
def handle_path(path: str):
    # Strip query string
    if "?" in path:
        path = path.split("?", 1)[0]

    if path == "/" or path == "/index.html":
        return http_response(HTML.encode("utf-8"))
    elif path == "/forward":
        move_forward()
        return http_response(json_body({"state": STATE}), "application/json")
    elif path == "/backward":
        move_backward()
        return http_response(json_body({"state": STATE}), "application/json")
    elif path == "/left":
        turn_left(pivot=True)    # set pivot=False for gentle turn
        return http_response(json_body({"state": STATE}), "application/json")
    elif path == "/right":
        turn_right(pivot=True)
        return http_response(json_body({"state": STATE}), "application/json")
    elif path == "/stop":
        all_stop()
        return http_response(json_body({"state": STATE}), "application/json")
    elif path == "/status":
        return http_response(json_body({"state": STATE}), "application/json")
    else:
        return http_response(b'{"error":"not found"}', "application/json", "404 Not Found")

# ========= TINY HTTP SERVER =========
def serve_forever(port=80):
    addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    print("HTTP server on port", port)
    while True:
        try:
            cl, remote = s.accept()
            cl.settimeout(3)
            req = cl.readline()
            if not req:
                cl.close()
                continue
            try:
                _, path, _ = req.decode().split(" ", 2)
            except:
                cl.close()
                continue
            # drain headers
            while True:
                h = cl.readline()
                if not h or h == b"\r\n":
                    break
            resp = handle_path(path)
            cl.send(resp)
        except Exception:
            pass
        finally:
            try:
                cl.close()
            except:
                pass

# ========= MAIN =========
def main():
    LED1.on()
    all_stop()  # safety on boot
    ip = wifi_connect()
    print("Open this in your browser: http://%s/" % ip)
    serve_forever(port=80)
    

if __name__ == "__main__":
    main()

