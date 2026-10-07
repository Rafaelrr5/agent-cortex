"""Abre a aba Modelos e Contas do dashboard do Hermes; sobe o dashboard se preciso."""
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser

if sys.stdout is None:
    sys.stdout = sys.stderr = open(os.devnull, "w")

PORT = 9119
URL = f"http://127.0.0.1:{PORT}/modelos-contas?profile=default"


def hermes_exe():
    found = shutil.which("hermes")
    if found:
        return found
    if os.name == "nt":
        guess = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "hermes-agent", "venv", "Scripts", "hermes.exe")
        if os.path.exists(guess):
            return guess
    sys.exit("hermes nao encontrado no PATH")


def up():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


if not up():
    log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.log"), "ab")
    flags = 0x08000000 | 0x00000008 if os.name == "nt" else 0  # CREATE_NO_WINDOW | DETACHED_PROCESS
    subprocess.Popen([hermes_exe(), "dashboard", "--no-open", "--skip-build", "--port", str(PORT)],
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags,
                     start_new_session=os.name != "nt")
    for _ in range(90):
        if up():
            time.sleep(1.5)
            break
        time.sleep(1)
webbrowser.open(URL)
