"""Run real Uvicorn HTTP smoke checks without sending requests to an AI provider."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]

def check(demo):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, DEMO_MODE=str(demo).lower(), GEMINI_API_KEY="")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}/api/"
    def request(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(base+path, data=body, headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    try:
        for attempt in range(60):
            if process.poll() is not None:
                raise RuntimeError("Uvicorn exited before readiness")
            try:
                status, health = request("health")
                break
            except (OSError, TimeoutError):
                time.sleep(0.2)
        else:
            raise RuntimeError("Uvicorn startup timed out")
        assert status == 200 and health["demoMode"] is demo
        assert health["aiConfigured"] is False
        status, result = request("recommend", {"budget":1500000})
        assert status == 200 and len(result["cities"]) == 3
        status, result = request("generate-itinerary", {"cityName":result["cities"][0]["cityName"],"budget":1500000})
        if demo:
            assert status == 200 and result["source"] == "demo" and "DAY 3" in result["text"]
        else:
            assert status == 503 and "GEMINI_API_KEY" in result["detail"]
        print(f"PASS real HTTP: demo={demo}, health=200, recommend=200, itinerary={status}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

if __name__ == "__main__":
    check(False)
    check(True)
