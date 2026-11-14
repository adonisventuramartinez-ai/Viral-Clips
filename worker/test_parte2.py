"""Pruebas de la Parte 2 (perfiles por tipo y largo ideal). Ejecuta: python test_parte2.py"""
import os

os.environ["GROQ_API_KEY"] = "gsk_x"
os.environ["CAST_NAMES"] = "Maria, Pedro"

import analyze  # noqa: E402
import profiles  # noqa: E402

# 1) todos los tipos existen y tienen lo necesario
for t in profiles.TYPES:
    p = profiles.get(t)
    assert p["name"] == t and p["ideal"] >= 15 and p["guide"] and "bonus" in p, t
assert profiles.get("no-existe")["name"] == "auto"

# 2) largo ideal por tipo
assert profiles.resolve_secs(0, profiles.get("gta")) == 25
assert profiles.resolve_secs("auto", profiles.get("gta_rp")) == 40
assert profiles.resolve_secs(None, profiles.get("podcast")) == 75
assert profiles.resolve_secs(0, profiles.get("reality")) == 45
assert profiles.resolve_secs(60, profiles.get("gta")) == 60          # si eliges un número, se respeta
assert profiles.resolve_secs(500, profiles.get("gta")) == 120 and profiles.resolve_secs(3, profiles.get("gta")) == 15

# 3) el elenco entra en la guía de reality (y solo ahí)
assert "Maria" in profiles.get("reality")["guide"] and "Maria" not in profiles.get("podcast")["guide"]

# 4) GTA acción usa marcas de acción; GTA RP prioriza diálogo; GTA sabe el juego solo
assert profiles.get("gta")["action"] is True and profiles.get("gta_rp")["action"] is False
assert profiles.get("gta")["bonus"]["motion"] < profiles.get("juego")["bonus"]["motion"]      # la cámara se mueve siempre
assert profiles.get("gta")["game"] == "GTA 5" and profiles.get("gta_rp")["game"] == "GTA 5 RP"

# 5) palabras clave sin importar tildes ni mayúsculas
seg = [{"start": 0, "end": 30, "text": "Eso fue una TRAICION, dime a ver en mi cara"}]
m = {"start": 0, "end": 30}
hits = analyze.keyword_hits(m, seg, profiles.get("reality"))
assert {"traición", "dime a ver", "en mi cara"} <= set(hits), hits
assert analyze.keyword_hits(m, seg, profiles.get("podcast")) == []

# 6) el prompt se arma bien para cada tipo con el largo ideal
chunk = [{"start": 0, "end": 5, "text": "hola"}]
for t in profiles.TYPES:
    prof = profiles.get(t)
    secs = profiles.resolve_secs(0, prof)
    txt = analyze._build_prompt(chunk, 5, secs, prof, prof.get("game"))
    assert f"cerca de {secs} segundos" in txt, t
assert "GTA 5" in analyze._build_prompt(chunk, 5, 25, profiles.get("gta"), "GTA 5")

# 7) los clips respetan el largo del tipo (GTA corto, podcast largo)
c = analyze._clean({"start": 100, "end": 400, "score": 80}, 25, 1000)
assert c["end"] - c["start"] <= 25 * 1.4 + 1e-6
c = analyze._clean({"start": 100, "end": 400, "score": 80}, 75, 1000)
assert 75 * 0.6 <= c["end"] - c["start"] <= 75 * 1.4 + 1e-6

print("OK: pruebas de la Parte 2 (perfiles) pasaron")
