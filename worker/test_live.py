"""Pruebas de la Parte 2 (modo en vivo). No gasta IA ni necesita internet ni Supabase: usa un video de prueba y piezas falsas.
Ejecuta: python test_live.py   (necesita ffmpeg)"""
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ.setdefault("GROQ_API_KEY", "gsk_x")
sys.modules.setdefault("requests", types.SimpleNamespace(post=None, RequestException=OSError))
sys.modules.setdefault("yt_dlp", types.SimpleNamespace())

import energy  # noqa: E402
import livechat  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="testlive_"))


def make_video(path, dur=30, burst=(20, 22), flash=(20, 21)):
    """Video de prueba con un tono suave, un pico de volumen y un destello blanco repentino."""
    vf = f"eq=brightness='if(between(t,{flash[0]},{flash[1]}),1,0)':eval=frame"
    af = f"volume='if(between(t,{burst[0]},{burst[1]}),12,0.15)':eval=frame"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"testsrc2=s=320x240:r=25:d={dur}",
                        "-f", "lavfi", "-i", f"sine=frequency=300:sample_rate=16000:duration={dur}",
                        "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------- 1) chat en vivo
def test_chat():
    # picos de mensajes: normal ~1 msg/s con un pico de 40 mensajes entre 300 y 310 s
    times = [float(t) for t in range(0, 600, 2)] + [300 + i * 0.25 for i in range(40)]
    hot = energy.hot_from_times(times, 0, 600)
    assert hot and all(298 <= t <= 312 for t in hot), sorted(hot)[:5]
    assert energy.hot_from_times([1.0, 2.0], 0, 600) == set()                    # casi sin chat: no inventa picos
    assert energy.hot_from_times(list(range(0, 600, 2)), 0, 600) == set()       # chat parejo: ningún pico

    # hora real -> segundo de la grabación, con dos sesiones (reconexión) y un hueco en medio
    c = livechat.LiveChat("x", log=lambda *_: None)
    B = 1_700_000_000.0                    # una hora real de ejemplo (epoch)
    c.session_start(0.0, wall=B)
    c.session_end(wall=B + 100)            # sesión 1: 100 s
    c.session_start(100.0, wall=B + 130)   # hueco de 30 s sin grabar
    for w in (10.0, 50.0, 105.0, 135.0, 160.0):
        c.add((B + w) * 1e6)               # microsegundos, como los da chat-downloader
    got = sorted(round(t) for t in c.timeline_times())
    assert got == [10, 50, 105, 130], got   # el mensaje de 1105 cae en el hueco y se descarta
    assert c.count() == 5
    c2 = livechat.LiveChat("x", log=lambda *_: None)    # sin la librería no revienta
    c2.start()
    assert c2.error is None or "chat-downloader" in c2.error


# ---------------------------------------------------------------- 2) señales de volumen y acción
def test_signals():
    v = TMP / "sig.mp4"
    make_video(v)
    lv = energy.audio_levels(v)
    assert len(lv) >= 29, len(lv)
    loud = energy.loud_from_levels(lv)
    assert loud and all(18 <= t <= 23 for t in loud), sorted(loud)
    sc = energy.scene_levels(v)
    assert len(sc) >= 29, len(sc)
    motion = energy.motion_from_levels(sc)
    assert motion and all(18 <= t <= 23 for t in motion), sorted(motion)


# ---------------------------------------------------------------- 3) canales automáticos (solo la parte pura)
def test_watcher_urls():
    stub = types.SimpleNamespace(now=lambda: "t")
    sys.modules["db"] = stub
    import watcher
    assert watcher.live_url_for("https://www.youtube.com/@canal") == "https://www.youtube.com/@canal/live"
    assert watcher.live_url_for("https://www.youtube.com/@canal/") == "https://www.youtube.com/@canal/live"
    assert watcher.live_url_for("https://www.youtube.com/watch?v=abc") == "https://www.youtube.com/watch?v=abc"
    assert watcher.live_url_for("https://www.youtube.com/@canal/live") == "https://www.youtube.com/@canal/live"
    assert watcher.live_url_for("https://www.twitch.tv/canal") == "https://www.twitch.tv/canal"

    # tick: arranca solo el directo nuevo; no repite el mismo ni arranca si ya hay uno grabando
    calls = {"created": [], "updates": []}
    chs = [{"id": "c1", "name": "A", "url": "https://x/a", "last_video_id": "old"},
           {"id": "c2", "name": "B", "url": "https://x/b", "last_video_id": None}]
    stub.active_channels = lambda: chs
    stub.live_active = lambda: False
    stub.update_channel = lambda cid, **f: calls["updates"].append((cid, f))
    stub.create_live_source = lambda ch, found: calls["created"].append((ch["id"], found["id"])) or "sid"
    watcher.probe = lambda url: {"id": "old", "url": url, "title": "t"} if url.endswith("/a") else {"id": "new", "url": url, "title": "t"}
    assert watcher.tick(force=True) == 1
    assert calls["created"] == [("c2", "new")], calls          # c1 ya se grabó (mismo id): se salta
    stub.live_active = lambda: True
    assert watcher.tick(force=True) == 0                        # ya hay un directo: no crea otro


# ---------------------------------------------------------------- 4) directo completo con reconexión y "Clip ahora"
def test_live_flow():
    src_video = TMP / "stream.mp4"
    dur_v = 16 if os.environ.get("LIVE_TEST_PACED") else 20
    make_video(src_video, dur=dur_v, burst=(10, 12), flash=(10, 11))

    rec = {"finish_cmd": [], "clips": [], "progress": [], "status": [], "saved_tr": 0, "review": [], "renders": [],
           "resolves": 0, "sleeps": 0}

    class FakeDB:
        sb = None
        polls = 0

        def heartbeat(self, info=None): pass
        def touch_job(self, jid): pass
        def get_source(self, sid): return {"id": sid, "url": "https://fake/live", "options": {"content_type": "juego", "game": "Counter"},
                                           "layout": "crop", "custom_crop": None, "user_id": None}
        def set_source(self, sid, **f):
            if "status" in f: rec["status"].append(f["status"])
        def stop_requested(self, sid): return False
        def save_transcript(self, sid, segs): rec["saved_tr"] += len(segs)
        def save_rejected(self, sid, rej): pass
        def upload_clip(self, path, f): pass
        def save_clip(self, sid, uid, m, path, size, words): rec["clips"].append((m["title"], m.get("hook"), m["abs_start"], m["abs_end"]))
        def set_progress(self, sid, **p): rec["progress"].append(p)
        def finish_job(self, jid, ok=True): rec["finished"] = ok
        def finish_command(self, cid, ok=True, message=None, clip_id=None): rec["finish_cmd"].append((cid, ok, message, bool(clip_id)))
        def pending_commands(self, sid):
            self.polls += 1
            if self.polls == 3 and not rec["finish_cmd"]:
                return [{"id": "cmd1", "seconds": 15}]
            return [{"id": "cmd1", "seconds": 15}] if self.polls > 3 and not rec["finish_cmd"] else []

    fake_db = FakeDB()
    sys.modules["db"] = fake_db
    sys.modules["brand"] = types.SimpleNamespace(load=lambda w: {})

    def fake_render(win, words, start, end, out, work, **kw):
        rec["renders"].append((round(start, 1), round(end, 1), kw.get("hook")))
        Path(out).write_bytes(b"x" * 100)
    sys.modules["render"] = types.SimpleNamespace(render_clip=fake_render)

    def fake_transcribe(f, work):
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                   capture_output=True, text=True).stdout.strip())
        words = [{"w": f"palabra{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(int(dur * 2) - 2)]
        words[-1]["w"] = "final."
        return [{"start": 0.0, "end": dur - 0.5, "text": f"Texto del trozo {f.name}."}], words
    sys.modules["transcribe"] = types.SimpleNamespace(transcribe=fake_transcribe)

    def fake_review(segments, secs, existing, duration, **kw):
        rec["review"].append({"profile": kw["profile"]["name"], "game": kw["game"], "max_new": kw["max_new"],
                              "min_score": kw["min_score"], "hot": sorted({m for s in segments for m in (s.get("hot") or "")}),
                              "n_words": len(kw["words"]), "duration": duration})
        end = duration - 2
        m = {"start": end - 8, "end": end, "score": 80, "title": f"Momento {len(rec['review'])}", "hook": "GANCHO",
             "reason": "", "description": "", "hashtags": []}
        return [m], []
    sys.modules["analyze"] = types.SimpleNamespace(review_window=fake_review,
                                                   title_for=lambda text, fallback="x": {"title": "Clip manual", "hook": "MIRA", "description": "d", "hashtags": ["#a"]})

    import config
    config.WORK_DIR = TMP / "work"
    config.SEGMENT_SECONDS = 5
    config.POLL_SECONDS = 0.2
    config.LIVE_CHAT = True
    config.LIVE_RECONNECTS = 3
    import importlib
    import live
    importlib.reload(live)
    live.NOT_LIVE_RECHECK = 1

    class FakeChat:
        def __init__(self, url): self.s = []
        def session_start(self, t): self.s.append(("start", round(t)))
        def session_end(self): self.s.append(("end",))
        def start(self): pass
        def stop(self): rec["chat_stopped"] = True
        def count(self): return 123
        def hot(self, lo, hi): return {t for t in range(lo, hi) if 10 <= t % 20 <= 12}   # chat "caliente" en esos segundos
    live.LiveChat = FakeChat

    def fake_resolve(url, quality):
        rec["resolves"] += 1
        if rec["resolves"] <= 2:      # primera conexión y primera reconexión: el directo sigue
            return [(str(src_video), {})], ["-map", "0:v:0", "-map", "0:a:0?"], "Directo de prueba"
        raise live.NotLive("terminó")
    live._resolve = fake_resolve
    if os.environ.get("LIVE_TEST_PACED"):       # el stream sale a velocidad real (como un directo de verdad)
        orig = live._start_ffmpeg
        def paced(inputs, maps, seg_dir, logf, session=1):
            inputs = [(s_, h_) for s_, h_ in inputs]
            cmd = ["ffmpeg", "-y", "-loglevel", "warning", "-re", "-i", inputs[0][0]] + maps + [
                "-c", "copy", "-f", "segment", "-segment_time", str(config.SEGMENT_SECONDS), "-segment_format", "mpegts",
                "-reset_timestamps", "1", str(seg_dir / f"s{session:02d}_seg_%05d.ts")]
            return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=logf)
        live._start_ffmpeg = paced
        rec["paced"] = True

    job = {"id": "job1", "source_id": "sid1", "payload": {"clip_seconds": 20, "review_minutes": 1, "max_new": 2, "min_score": 50,
                                                          "progress_bar": True}}
    config.REVIEW_MINUTES = 1
    t0 = time.time()
    live.process_live(job)
    took = time.time() - t0

    assert rec["resolves"] == 4, rec["resolves"]            # conexión + reconexión + 2 comprobaciones de "ya terminó"
    assert rec["finished"] is True and rec["status"][-1] == "done", rec["status"]
    last = rec["progress"][-1]
    assert last["reconnects"] == 1 and last["chat_msgs"] == 123, last
    assert last["transcribed_sec"] >= (28 if rec.get("paced") else 38), last              # 2 sesiones de 20 s: la grabación sigue después de reconectar
    assert rec["review"], "no hubo ninguna revisión"
    r0 = rec["review"][0]
    assert r0["profile"] == "juego" and r0["game"] == "Counter" and r0["max_new"] == 2 and r0["min_score"] == 50, r0
    assert any(m in r0["hot"] for m in "🔊🎮💬"), r0          # llegaron pistas a la IA
    assert "💬" in "".join("".join(r["hot"]) for r in rec["review"]), rec["review"]
    assert rec["finish_cmd"] and rec["finish_cmd"][0][:2] == ("cmd1", True) and rec["finish_cmd"][0][3], rec["finish_cmd"]
    assert any(c[0] == "Clip manual" for c in rec["clips"]), rec["clips"]
    clip_manual = next(c for c in rec["clips"] if c[0] == "Clip manual")
    assert 10 <= clip_manual[3] - clip_manual[2] <= 25, clip_manual   # unos 15 s (ajustado a inicio de frase)
    assert rec.get("chat_stopped"), "el chat debe detenerse al final"
    assert not (config.WORK_DIR / "sid1").exists(), "debe limpiar la carpeta de trabajo"
    print(f"  (directo simulado: {took:.0f} s, {len(rec['clips'])} clips, {len(rec['review'])} revisiones)")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ✓ {name}")
    print("OK: pruebas de la Parte 2 pasaron")
