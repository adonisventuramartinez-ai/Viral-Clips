# Parte 1: base y seguridad

- **Groq con N cuentas:** `GROQ_KEYS=gsk_a,gsk_b,...`, `GROQ_API_KEY_2=...` o `worker/groq_keys.txt` (una por línea). Sin límite.
- **IA (llm.py):** el modelo grande de TODAS las cuentas va primero, luego el chico de todas; el trabajo se reparte entre cuentas.
  Un `LLM_ORDER` fijo ya no deja fuera cuentas nuevas ("groq" = todas).
- **Transcripción:** si una llave da 429 pasa a la siguiente (antes se rendía); trozos empalmados sin cortar palabras;
  prompt con elenco (`CAST_NAMES`) y jerga dominicana.
- **Análisis:** ventanas de 900 s con 90 s de solape (`ANALYSIS_OVERLAP`).
- **Login:** 5 intentos por IP cada 15 min, comparación en tiempo constante.
- **Limpieza:** borrada la copia vieja de la web dentro de `worker/`; sin `.env` ni cookies en el zip; `.gitignore` reforzado.
- Pruebas: `python test_llm.py`, `python test_parte1.py`, `test_calidad.py`, `test_live.py`.
