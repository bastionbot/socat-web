from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from subprocess import Popen, PIPE
import psutil
import os
import uuid
import time

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

active_tunnels = {}

class SocatTunnel:
    def __init__(self, name, src_ip, src_port, dst_ip, dst_port, protocol):
        self.id = str(uuid.uuid4())
        self.name = name
        self.protocol = protocol.lower()
        self.src_ip = src_ip
        self.src_port = src_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.process = None
        self.error = None

    def start(self):
        proto = f"{self.protocol}4"
        left = f"{proto}-LISTEN:{self.src_port},fork,reuseaddr,bind={self.src_ip}"
        right = f"{proto}:{self.dst_ip}:{self.dst_port}"
        try:
            self.process = Popen(["socat", left, right], stderr=PIPE)
            time.sleep(1)  # Allow socat time to fail if necessary
            if self.process.poll() is not None and self.process.returncode != 0:
                _, err = self.process.communicate()
                self.error = err.decode().strip()
                return False
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            return True
        return False

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tunnels = active_tunnels.values()
    return templates.TemplateResponse("index.html", {"request": request, "tunnels": tunnels, "process_tree": get_tunnel_tree()})

@app.get("/partials/tunnel_list", response_class=HTMLResponse)
async def tunnel_list_partial(request: Request):
    tunnels = active_tunnels.values()
    return templates.TemplateResponse("partials/tunnel_list.html", {"request": request, "tunnels": tunnels})

@app.get("/partials/process_tree", response_class=HTMLResponse)
async def process_tree_partial(request: Request):
    return templates.TemplateResponse("partials/process_tree.html", {"request": request, "process_tree": get_tunnel_tree()})

@app.post("/start")
async def start_tunnel(
    name: str = Form(...),
    src_ip: str = Form(...),
    src_port: str = Form(...),
    dst_ip: str = Form(...),
    dst_port: str = Form(...),
    protocol: str = Form(...)
):
    tunnel = SocatTunnel(name, src_ip, src_port, dst_ip, dst_port, protocol)
    if tunnel.start():
        active_tunnels[tunnel.id] = tunnel
    return RedirectResponse("/", status_code=303)

@app.post("/stop/{tunnel_id}")
async def stop_tunnel(tunnel_id: str):
    tunnel = active_tunnels.get(tunnel_id)
    if tunnel:
        tunnel.stop()
        del active_tunnels[tunnel_id]
    return RedirectResponse("/", status_code=303)

@app.post("/stop_pid/{pid}")
async def stop_by_pid(pid: int):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)

def get_tunnel_tree():
    tree = []
    child_pids = set()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'socat' in proc.info['cmdline'][0]:
                children = proc.children(recursive=True)
                child_pids.update(c.pid for c in children)
                tree.append({
                    "pid": proc.pid,
                    "cmd": " ".join(proc.info['cmdline']),
                    "children": [{"pid": c.pid, "cmd": " ".join(c.cmdline())} for c in children]
                })
        except Exception:
            continue
    return [entry for entry in tree if entry["pid"] not in child_pids]
