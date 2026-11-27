#!/bin/sh
# Arranque del worker: baja el yt-dlp más nuevo (YouTube cambia casi cada semana) y sigue aunque no haya internet en ese momento.
pip install -q -U "yt-dlp[default]" >/dev/null 2>&1 && echo "yt-dlp: $(yt-dlp --version)" || echo "yt-dlp: no pude actualizar, uso el de la imagen ($(yt-dlp --version))"
exec python -u main.py
