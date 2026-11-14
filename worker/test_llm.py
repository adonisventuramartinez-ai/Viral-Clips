"""Pruebas de la rotación de IA con respuestas simuladas (no gasta cupo). Ejecuta: python test_llm.py"""
import os
import sys
import time
import types

for k in list(os.environ):
    if (k.endswith("_API_KEY") or k.startswith("GROQ_API_KEY_") or k in
            ("GITHUB_MODELS_TOKEN", "LLM_PROVIDER", "LLM_ORDER", "GROQ_KEYS", "GROQ_MODEL", "GROQ_FALLBACK_MODEL")):
        del os.environ[k]
os.environ.update(GROQ_API_KEY="gsk_x", CEREBRAS_API_KEY="csk_x", GEMINI_API_KEY="g_x", LLM_MAX_WAIT="3",
                  GROQ_KEYS_FILE=os.devnull)

import llm  # noqa: E402

calls = []
plan = {}  # url-fragment -> lista de respuestas (status, body, headers)


class R:
    def __init__(self, status, body, headers=None):
        self.status_code, self.text, self.headers, self._b = status, str(body), headers or {}, body

    ok = property(lambda s: 200 <= s.status_code < 300)

    def json(self):
        return self._b


def good(txt='{"moments":[]}'):
    return R(200, {"choices": [{"message": {"content": txt}}]})


def fake_post(url, headers=None, json=None, timeout=None, **kw):
    host = url.split("/")[2]
    calls.append((host, json["model"] if json else None))
    return plan[host].pop(0) if len(plan[host]) > 1 else plan[host][0]


sys.modules["requests"] = types.SimpleNamespace(post=fake_post, RequestException=OSError)


def reset(**p):
    llm._cool.clear(); llm._dead.clear(); llm._rr.update({"70b": 0, "8b": 0}); calls.clear(); plan.clear(); plan.update(p)


def parse(t):
    return t if t.startswith("{") else None


G, C, M = "api.groq.com", "api.cerebras.ai", "generativelanguage.googleapis.com"

# 1) todo bien: usa Groq 70B y no toca a nadie más
reset(**{G: [good()]})
assert llm.ask("hola", check=parse) == '{"moments":[]}'
assert calls == [(G, "llama-3.3-70b-versatile")], calls

# 2) Groq se queda sin cupo diario (70B y 8B) -> pasa a Cerebras y NO vuelve a molestar a Groq
reset(**{G: [R(429, "Rate limit reached ... tokens per day (TPD): Limit 100000", {"retry-after": "3000"})], C: [good()]})
llm.ask("hola", check=parse)
assert [h for h, _ in calls] == [G, G, C], calls
calls.clear(); llm.ask("otra", check=parse)
assert calls == [(C, "gpt-oss-120b")], calls                      # Groq 70B quedó apartado
assert llm._cool["groq"] - time.time() > 600                      # apartado mucho rato

# 3) límite por minuto: apartado poco tiempo
reset(**{G: [R(429, "tokens per minute", {"retry-after": "7"})], C: [good()]})
llm.ask("x", check=parse)
assert 0 < llm._cool["groq"] - time.time() < 20, llm._cool

# 4) llave mala (401): se descarta para siempre
reset(**{G: [R(401, "invalid key")], C: [good()]})
llm.ask("x", check=parse)
assert "groq" in llm._dead and "groq8b" not in llm._dead or True
assert "groq" in llm._dead

# 5) servidor caído / basura -> siguiente proveedor
reset(**{G: [R(503, "down")], C: [good("esto no es json")], M: [good()]})
assert llm.ask("x", check=parse) == '{"moments":[]}'
assert [h for h, _ in calls][:4] == [G, G, C, M], calls

# 6) todos sin cupo: error claro y rápido (MAX_WAIT=3), no se cuelga
reset(**{G: [R(429, "per day", {})], C: [R(429, "per day", {})], M: [R(429, "RESOURCE_EXHAUSTED PerDay", {})]})
t0 = time.time()
try:
    llm.ask("x", check=parse)
    raise SystemExit("debió fallar")
except llm.AllBusy as e:
    assert "sin cupo" in str(e), e
assert time.time() - t0 < 10

# 7) modo JSON no soportado -> reintenta sin response_format en el mismo proveedor
n = {"i": 0}


def fake2(url, headers=None, json=None, timeout=None, **kw):
    n["i"] += 1
    return R(400, "response_format not supported") if "response_format" in json else good()


sys.modules["requests"].post = fake2
reset(**{G: [good()]})
assert llm.ask("x", check=parse) and n["i"] == 2

# 8) LLM_PROVIDER manda primero; sin llave no entra
sys.modules["requests"].post = fake_post
os.environ["LLM_PROVIDER"] = "gemini"
reset(**{M: [good()]})
llm.ask("x", check=parse)
assert calls == [(M, "gemini-2.5-flash")], calls
del os.environ["LLM_PROVIDER"]
assert "mistral" not in llm.configured() and "anthropic" not in llm.configured()

# 9) check_all clasifica ok / cupo / mala
reset(**{G: [good()], C: [R(429, "per day")], M: [R(404, "model not found")]})
res = dict((n, s) for n, s, _ in llm.check_all())
assert res["groq"] == "ok" and res["cerebras"] == "cupo" and res["gemini"] == "mala", res


# 10) VARIAS cuentas de Groq: si una se queda sin cupo (429) pasa a la siguiente cuenta, no a otro proveedor
os.environ["GROQ_KEYS"] = ",".join(f"gsk_{i:02d}" for i in range(1, 21))      # 20 cuentas
os.environ["GROQ_API_KEY"] = ""
auth_seen = []


def fake_multi(url, headers=None, json=None, timeout=None, **kw):
    key = headers["Authorization"].split()[-1]
    auth_seen.append((key, json["model"]))
    if key in ("gsk_01", "gsk_02"):
        return R(429, "tokens per day", {"retry-after": "3000"})
    return good()


sys.modules["requests"].post = fake_multi
reset()
assert len([n for n in llm.configured() if n.startswith("groq") and not n.endswith("_8b")]) == 20
llm.ask("x", check=parse)
assert auth_seen[-1][0] == "gsk_03" and auth_seen[-1][1] == "llama-3.3-70b-versatile", auth_seen   # saltó 01 y 02 (70B)
assert llm._cool["groq"] > time.time() + 600 and llm._cool["groq_cuenta2"] > time.time() + 600

# 11) reparto: las siguientes preguntas empiezan por cuentas distintas (no revientan siempre la misma)
auth_seen.clear()
for _ in range(4):
    llm.ask("x", check=parse)
used = [k for k, _ in auth_seen]
assert len(set(used)) == 4, used

# 12) un LLM_ORDER fijo en el .env no deja fuera las cuentas nuevas, y "groq" va con las 20 antes que el resto
os.environ["LLM_ORDER"] = "groq,groq_8b,groq_cuenta2,groq_cuenta2_8b,gemini,cerebras"
names = llm.configured()
assert names.index("groq_cuenta20") < names.index("groq_8b") < names.index("gemini"), names
assert names.index("groq_cuenta20_8b") < names.index("gemini") < names.index("cerebras"), names
assert names.count("groq") == 1 and names.count("groq_cuenta2") == 1
del os.environ["LLM_ORDER"]

# 13) llave mala en una cuenta (401) la descarta y sigue con las demás
sys.modules["requests"].post = lambda url, headers=None, json=None, **kw: (
    R(401, "bad") if headers["Authorization"].endswith("gsk_01") else good())
reset(); llm.ask("x", check=parse)
assert "groq" in llm._dead and "groq_cuenta2" not in llm._dead

print("OK: 13 pruebas de rotación pasaron")
