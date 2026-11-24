"""Local studio: talk to the agent, see the 3D model, and change its parameters directly.

Runs on your own computer (it uses the Claude Code you are logged in to, and CadQuery).
Start it with  bash local/start.sh  and it opens http://127.0.0.1:8765 in the browser.

- Chat: every message goes to the agent (Claude Code, `claude -p`) with the rulebook
  (prompts/system.md) and the family agent instructions. The agent writes model.py and checks it.
- Parameters: the sliders change values in the agent's PARAMS and rebuild the model here, without
  asking the agent. The checker (rules measured directly) runs on every rebuild.
- Every turn is kept in ~/param-studio/sessions/<date-time>/ (model_t1.py, model_t2.py, chat.md).
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiment"))

PORT = int(os.environ.get("STUDIO_PORT", "8765"))
MODEL = os.environ.get("STUDIO_MODEL", "claude-sonnet-5-5")
TOOLS = "Read(./**),Edit(./**),Write(./**),Bash(python check.py:*)"
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")


def claude_path():
    for p in (shutil.which("claude"), os.path.expanduser("~/.local/bin/claude")):
        if p and os.path.exists(p):
            return p
    return None


class Session:
    def __init__(self):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = os.path.join(os.path.expanduser("~/param-studio/sessions"), stamp)
        os.makedirs(self.dir, exist_ok=True)
        shutil.copy(os.path.join(ROOT, "experiment", "agent", "check.py"), self.dir)
        rules = open(os.path.join(ROOT, "prompts", "system.md"), encoding="utf-8").read()
        head = open(os.path.join(ROOT, "experiment", "agent", "family_prompt.md"), encoding="utf-8").read()
        self.system = head + "\n\n" + rules
        self.session_id = None
        self.turn = 0
        self.history = []          # [{"who": "user"|"agent", "text": ...}]
        self.base = None           # the agent's PARAMS of the latest turn
        self.params = None         # what the sliders currently show
        self.lock = threading.Lock()

    def log(self):
        lines = ["# studio session", ""]
        for h in self.history:
            lines += [f"**{'사용자' if h['who'] == 'user' else '에이전트'}:** {h['text']}", ""]
        open(os.path.join(self.dir, "chat.md"), "w", encoding="utf-8").write("\n".join(lines))


S = None


def ask_agent(text):
    exe = claude_path()
    if not exe:
        return {"is_error": True, "result": "claude 명령을 찾지 못했습니다 (~/.local/bin/claude)."}
    cmd = [exe, "-p", text, "--output-format", "json", "--model", MODEL, "--max-turns", "10",
           "--system-prompt", S.system, "--allowedTools", TOOLS,
           "--disallowedTools", "WebFetch,WebSearch,Task,NotebookEdit"]
    if S.session_id:
        cmd += ["--resume", S.session_id]
    env = dict(os.environ, REPO_ROOT=ROOT)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    t0 = time.time()
    r = subprocess.run(cmd, cwd=S.dir, capture_output=True, text=True, env=env, timeout=1500)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        out = {"is_error": True, "result": (r.stderr or r.stdout or "응답 없음")[-600:]}
    if isinstance(out.get("result"), str):
        out["result"] = SECRET.sub("[token hidden]", out["result"])
    out["_seconds"] = round(time.time() - t0)
    return out


def build_payload(path, params):
    """Build the model at `params`, mesh it, run the checker. Returns a JSON-able dict."""
    from evaluate_one import as_shape, load
    from export_family_web import how_it_opens, material, mesh
    from rule_check import check_parts

    mod = load(path)
    t0 = time.time()
    parts = [(n, as_shape(s)) for n, s in mod.build(dict(params))]
    rc = check_parts(parts)
    opens = how_it_opens(parts)
    bbs = [s.BoundingBox() for _, s in parts]
    box = [min(b.xmin for b in bbs), min(b.ymin for b in bbs), min(b.zmin for b in bbs),
           max(b.xmax for b in bbs), max(b.ymax for b in bbs), max(b.zmax for b in bbs)]
    out = []
    for n, s in parts:
        v, i = mesh(s)
        part = {"n": n, "m": material(n), "v": v, "i": i}
        if n in opens:
            part["o"] = opens[n]
        out.append(part)
    return {"box": [round(x, 1) for x in box], "parts": out,
            "check": {"pass": bool(rc.get("pass")),
                      "failed": {k: rc["messages"].get(k, [])[:3] for k, v in rc["rules"].items() if not v}},
            "seconds": round(time.time() - t0, 1)}


def plain(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return str(v)


def state(extra=None):
    d = {"history": S.history, "turn": S.turn, "dir": S.dir,
         "params": {k: plain(v) for k, v in (S.params or {}).items() if k != "notes"},
         "base": {k: plain(v) for k, v in (S.base or {}).items() if k != "notes"},
         "notes": list((S.base or {}).get("notes") or [])}
    d.update(extra or {})
    return d


def current_model():
    return os.path.join(S.dir, f"model_t{S.turn}.py") if S.turn else None


def do_chat(text):
    with S.lock:
        S.history.append({"who": "user", "text": text})
        res = ask_agent(text)
        S.session_id = res.get("session_id", S.session_id)
        reply = res.get("result") or ""
        if res.get("is_error"):
            reply = "에이전트 오류: " + reply
        src = os.path.join(S.dir, "model.py")
        model = None
        if os.path.exists(src):
            S.turn += 1
            dst = current_model()
            shutil.copy(src, dst)
            try:
                from evaluate_one import load
                S.base = dict(load(dst).PARAMS)
                S.params = dict(S.base)
                model = build_payload(dst, S.params)
            except Exception as e:  # noqa: BLE001
                model = {"error": f"{type(e).__name__}: {e}"[:400]}
        S.history.append({"who": "agent", "text": reply, "seconds": res.get("_seconds"),
                          "turn": S.turn})
        S.log()
        return state({"model": model})


def do_params(changes):
    with S.lock:
        path = current_model()
        if not path:
            return state({"model": {"error": "아직 모델이 없습니다. 먼저 에이전트에게 요청하세요."}})
        params = dict(S.base)
        params.update(changes)
        try:
            model = build_payload(path, params)
            S.params = params
        except Exception as e:  # noqa: BLE001
            model = {"error": f"{type(e).__name__}: {e}"[:400]}
        return state({"model": model})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = open(os.path.join(ROOT, "local", "studio.html"), "rb").read()
            return self.send(200, html, "text/html; charset=utf-8")
        if self.path == "/api/state":
            payload = state()
            if current_model():
                try:
                    payload["model"] = build_payload(current_model(), S.params)
                except Exception as e:  # noqa: BLE001
                    payload["model"] = {"error": str(e)[:300]}
            return self.send(200, payload)
        self.send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/chat":
            text = (body.get("text") or "").strip()
            if not text:
                return self.send(400, {"error": "빈 메시지"})
            return self.send(200, do_chat(text))
        if self.path == "/api/params":
            return self.send(200, do_params(body.get("params") or {}))
        if self.path == "/api/reset":
            global S
            S = Session()
            return self.send(200, state())
        self.send(404, {"error": "not found"})


def main():
    global S
    S = Session()
    if not claude_path():
        print("경고: claude 명령을 찾지 못했습니다. 대화는 안 되고, 화면만 열립니다.")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"스튜디오가 열렸습니다: {url}")
    print(f"대화 기록 폴더: {S.dir}")
    print("끝내려면 이 터미널 창에서 Ctrl+C 를 누르세요.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
