"""IA con rotación automática (soporta múltiples llaves de Groq separadas por comas)."""
import os
import re
import time

import config  # noqa: F401  (carga worker/.env)

MAX_WAIT = int(os.environ.get("LLM_MAX_WAIT", "180") or 180)

_DAILY = re.compile(r"per day|daily|per_day|perday|\btpd\b|\brpd\b|per-day", re.I)

_cool = {}
_dead = {}
_last = None


class AllBusy(RuntimeError):
    """Ningún proveedor de IA puede responder ahora."""


class _Fail(Exception):
    def __init__(self, kind, msg, wait=0):
        super().__init__(msg)
        self.kind, self.msg, self.wait = kind, msg, wait


def _env(name, default=""):
    return (os.environ.get(name) or default).strip().strip("\"'").strip()


def _providers():
    """Lista de proveedores. Las llaves de Groq se leen separadas por comas."""
    groq_keys = config.groq_keys()

    table = {
        "cerebras": dict(kind="openai", url="https://api.cerebras.ai/v1", key=_env("CEREBRAS_API_KEY"),
                         model=_env("CEREBRAS_MODEL", "gpt-oss-120b"), json=True, max_tokens=6000),
        "gemini": dict(kind="openai", url="https://generativelanguage.googleapis.com/v1beta/openai",
                       key=_env("GEMINI_API_KEY"), model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
                       json=True, max_tokens=8000),
        "mistral": dict(kind="openai", url="https://api.mistral.ai/v1", key=_env("MISTRAL_API_KEY"),
                        model=_env("MISTRAL_MODEL", "mistral-small-latest"), json=True, max_tokens=4000),
        "openrouter": dict(kind="openai", url="https://openrouter.ai/api/v1", key=_env("OPENROUTER_API_KEY"),
                           model=_env("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                           json=False, max_tokens=4000),
        "github": dict(kind="openai", url="https://models.github.ai/inference", key=_env("GITHUB_MODELS_TOKEN"),
                       model=_env("GITHUB_MODEL", "openai/gpt-4.1-mini"), json=False, max_tokens=3000),
        "anthropic": dict(kind="anthropic", url="", key=_env("ANTHROPIC_API_KEY"),
                          model=_env("CLAUDE_MODEL", "claude-sonnet-5-5"), json=False, max_tokens=4000),
    }

    # Agregamos dinámicamente cada cuenta de Groq
    for i, key in enumerate(groq_keys):
        name = "groq" if i == 0 else f"groq_cuenta{i+1}"
        table[name] = dict(
            kind="openai", url="https://api.groq.com/openai/v1", key=key,
            model=_env("GROQ_MODEL", "llama-3.3-70b-versatile"), json=True, max_tokens=3000
        )
        # Añadimos el modelo de 8B para cada cuenta
        table[f"{name}_8b"] = dict(
            kind="openai", url="https://api.groq.com/openai/v1", key=key,
            model=_env("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant"), json=True, max_tokens=3000
        )

    # Todas las cuentas de Groq van en bloque: primero el modelo grande de CADA cuenta y después el chico de cada una.
    g70 = ["groq" if i == 0 else f"groq_cuenta{i+1}" for i in range(len(groq_keys))]
    block = g70 + [f"{n}_8b" for n in g70]
    rest = ["cerebras", "gemini", "mistral", "openrouter", "github", "anthropic"]
    default_order = block + [n for n in rest if n != "github"]

    raw = [n.strip().lower() for n in _env("LLM_ORDER").split(",") if n.strip()]
    if not raw:
        order = default_order
    else:
        # Un LLM_ORDER fijo no deja fuera las cuentas nuevas: el primer nombre de Groq que aparezca
        # se reemplaza por el bloque completo (las 20 cuentas) y los demás nombres de Groq se ignoran.
        order, placed = [], False
        for n in raw:
            if n == "groq" or n.startswith("groq_") or n == "groq8b":
                if not placed:
                    order.extend(block)
                    placed = True
            else:
                order.append(n)

    first = _env("LLM_PROVIDER").lower()
    if first in ("groq", "groq_all"):
        order = block + [n for n in order if n not in block]
    elif first in order:
        order.remove(first)
        order.insert(0, first)

    out = []
    for n in order:
        if n in table and table[n]["key"]:
            out.append({"name": n, **table[n]})
    return out


def configured():
    return [p["name"] for p in _providers()]


# ---------------------------------------------------------------- errores

def _retry_after(headers):
    try:
        return float((headers or {}).get("retry-after"))
    except (TypeError, ValueError):
        return None


def _from_http(status, text, headers):
    low = (text or "").lower()
    if status in (401, 403):
        return _Fail("auth", f"llave rechazada ({status})")
    if status in (402, 429):
        ra = _retry_after(headers)
        if _DAILY.search(low) or (ra is not None and ra > 600) or status == 402:
            wait = ra if (ra and ra > 600) else 3600
            return _Fail("quota", "se acabó el cupo del día", min(wait, 6 * 3600))
        return _Fail("quota", "límite por minuto", min((ra or 60) + 1, 600))
    if status in (400, 404, 422):
        return _Fail("config", f"petición rechazada ({status}): {(text or '')[:120]}", 900)
    return _Fail("transient", f"error {status}", 120)


# ---------------------------------------------------------------- llamadas

def _call_openai(p, prompt, max_tokens=None, ping=False):
    import requests

    def post(use_json):
        body = {
            "model": p["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens or p["max_tokens"],
        }
        if use_json:
            body["response_format"] = {"type": "json_object"}
        try:
            return requests.post(p["url"] + "/chat/completions",
                                 headers={"Authorization": f"Bearer {p['key']}"},
                                 json=body, timeout=120)
        except requests.RequestException as e:
            raise _Fail("transient", f"sin conexión ({type(e).__name__})", 120)

    use_json = p["json"] and not ping
    r = post(use_json)
    if r.status_code == 400 and use_json and "response_format" in r.text.lower():
        r = post(False)
    if not r.ok:
        raise _from_http(r.status_code, r.text, r.headers)
    try:
        text = r.json()["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise _Fail("bad", "respuesta con formato raro", 30)
    if not text.strip() and not ping:
        raise _Fail("bad", "respuesta vacía", 30)
    return text


def _call_anthropic(p, prompt, max_tokens=None, ping=False):
    import anthropic

    client = anthropic.Anthropic(api_key=p["key"], max_retries=0, timeout=120)
    try:
        msg = client.messages.create(model=p["model"], max_tokens=max_tokens or p["max_tokens"],
                                     messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status is None:
            raise _Fail("transient", f"sin conexión ({type(e).__name__})", 120)
        raise _from_http(status, str(e), getattr(getattr(e, "response", None), "headers", {}))
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call(p, prompt, max_tokens=None, ping=False):
    fn = _call_anthropic if p["kind"] == "anthropic" else _call_openai
    return fn(p, prompt, max_tokens=max_tokens, ping=ping)


# ---------------------------------------------------------------- rotación

def _ready(name):
    return name not in _dead and _cool.get(name, 0) <= time.time()


def _mark(p, f):
    name = p["name"]
    if f.kind == "auth":
        _dead[name] = f.msg
        print(f"  IA: {name} descartado: {f.msg}. Revisa esa llave en worker/.env.", flush=True)
    else:
        _cool[name] = time.time() + f.wait
        mins = max(1, round(f.wait / 60)) if f.wait >= 60 else None
        cuando = f"vuelvo a probarlo en {mins} min" if mins else f"vuelvo a probarlo en {int(f.wait)} s"
        print(f"  IA: {name} → {f.msg} ({cuando}). Paso al siguiente.", flush=True)


def _next_ready_in():
    pend = [t - time.time() for n, t in _cool.items() if n not in _dead and n in configured()]
    return max(0.0, min(pend)) if pend else None


def _note_used(p):
    global _last
    if _last != p["name"]:
        print(f"  IA: usando {p['name']} ({p['model']})", flush=True)
        _last = p["name"]


_rr = {"70b": 0, "8b": 0}


def _is_groq(name):
    return name == "groq" or name.startswith("groq_")


def _spread(avail):
    """Reparte la carga entre las cuentas de Groq: cada pregunta empieza por una cuenta distinta,
    así ninguna se agota antes que las demás. El resto del orden no cambia."""
    out = list(avail)
    for tag in ("70b", "8b"):
        idx = [i for i, p in enumerate(out) if _is_groq(p["name"]) and p["name"].endswith("_8b") == (tag == "8b")]
        if len(idx) > 1:
            group = [out[i] for i in idx]
            k = _rr[tag] % len(group)
            for i, p in zip(idx, group[k:] + group[:k]):
                out[i] = p
    return out


def ask(prompt, check=None):
    provs = _providers()
    if not provs:
        raise AllBusy("No hay ninguna llave de IA en worker/.env.")
    deadline = time.time() + MAX_WAIT
    while True:
        avail = [p for p in provs if _ready(p["name"])]
        if not avail:
            wait = _next_ready_in()
            if wait is None:
                raise AllBusy("Todas las llaves de IA fueron rechazadas: " + "; ".join(f"{k}: {v}" for k, v in _dead.items()))
            if time.time() + wait > deadline:
                mins = max(1, round(wait / 60))
                raise AllBusy(f"Todos los proveedores de IA están sin cupo. El primero vuelve en ~{mins} min.")
            print(f"  IA: todos sin cupo, espero {int(wait) + 1} s…", flush=True)
            time.sleep(wait + 1)
            continue
        for p in _spread(avail):
            try:
                text = _call(p, prompt)
                value = check(text) if check else text
                if value is None:
                    raise _Fail("bad", "respuesta que no se pudo leer", 30)
                _note_used(p)
                if _is_groq(p["name"]):
                    _rr["8b" if p["name"].endswith("_8b") else "70b"] += 1
                return value
            except _Fail as f:
                _mark(p, f)


def check_all():
    out = []
    for p in _providers():
        try:
            _call(p, "Responde solo: ok", max_tokens=300, ping=True)
            out.append((p["name"], "ok", p["model"]))
        except _Fail as f:
            _mark(p, f)
            if f.kind == "quota":
                out.append((p["name"], "cupo", f.msg))
            else:
                out.append((p["name"], "mala", f"{f.msg} (modelo {p['model']})"))
    return out