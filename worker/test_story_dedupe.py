"""En La Casa dos historias distintas pueden compartir el mismo minuto: no las mates por solaparse."""
import analyze

SEGS = [
    {"start": 40.0, "end": 60.0, "text": "¿Por qué no hablaste? Mira cómo salió del edificio rojo."},
    {"start": 60.0, "end": 80.0, "text": "Confiesa su crush y suelta un puñetazo en la mesa."},
    {"start": 80.0, "end": 112.0, "text": "Amenaza de trompa, la pelea se intensifica y se escapa corriendo."},
]
OLD = {"start": 47.5, "end": 110.26, "title": "¿Por qué no hablaste?", "text": " ".join(s["text"] for s in SEGS[:1])}


def test_otra_historia_no_es_duplicado():
    other = {"start": 55.0, "end": 105.0, "title": "Confiesa su crush y suelta un puñetazo"}
    assert not analyze._same_story(other, OLD, SEGS)


def test_misma_historia_si_es_duplicado():
    same = {"start": 45.0, "end": 60.0, "title": "¿Por qué no hablaste? El conflicto en La Casa"}
    assert analyze._same_story(same, OLD, SEGS)


def test_momento_separado_nunca_es_duplicado():
    apart = {"start": 200.0, "end": 250.0, "title": "Otro tema"}
    assert not analyze._same_story(apart, OLD, SEGS)


def test_review_deja_pasar_dos_historias_del_mismo_minuto():
    old_ask, old_snap, old_boost = analyze._ask_llm, analyze._snap_all, analyze._boost
    candidates = [
        {"start": 50.0, "end": 70.0, "score": 95, "title": "P1 acusa a todos de callarse y huir"},
        {"start": 60.0, "end": 105.0, "score": 89, "title": "P1 confiesa su crush y suelta un puñetazo"},
    ]
    try:
        analyze._ask_llm = lambda *a, **k: list(candidates)
        analyze._snap_all = lambda c, *a, **k: c
        analyze._boost = lambda *a, **k: None
        new, rejected = analyze.review_window(SEGS, 60, [OLD], 120, min_score=55, max_new=3,
                                              profile={"dedupe": False})
        titles = [m["title"] for m in new]
        assert len(new) == 2, (titles, rejected)
        assert all(m["title"] in titles for m in candidates)
    finally:
        analyze._ask_llm, analyze._snap_all, analyze._boost = old_ask, old_snap, old_boost


if __name__ == "__main__":
    test_otra_historia_no_es_duplicado()
    test_misma_historia_si_es_duplicado()
    test_momento_separado_nunca_es_duplicado()
    test_review_deja_pasar_dos_historias_del_mismo_minuto()
    print("HISTORIAS OK")
