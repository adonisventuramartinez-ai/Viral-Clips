FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# yt-dlp necesita un runtime de JavaScript (Deno) para resolver YouTube
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# yt-dlp se actualiza en CADA reconstrucción: INICIAR-WORKER pasa la fecha/hora en YTDLP_BUST, así Docker
# no reutiliza una versión vieja guardada en caché (YouTube cambia casi cada semana).
ARG YTDLP_BUST=0
RUN echo "actualizando yt-dlp ($YTDLP_BUST)" \
 && pip install --no-cache-dir -U "yt-dlp[default]" \
 && yt-dlp --version

COPY . .

CMD ["python", "-u", "main.py"]
