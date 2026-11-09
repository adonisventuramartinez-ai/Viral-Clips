from pathlib import Path

import config


def parse_ts(s):
    """'1:30:00' -> 5400.0 ; vacío -> None"""
    if not s:
        return None
    sec = 0.0
    for p in str(s).strip().split(":"):
        sec = sec * 60 + float(p)
    return sec


# Cada intento prueba una forma distinta de pedirle el video a YouTube. Si el primero devuelve
# "Requested format is not available", se pasa al siguiente en vez de fallar.
_VARIANTS = [
    {},
    {"extractor_args": {"youtube": {"player_client": ["web_safari", "mweb"]}}},
    {"extractor_args": {"youtube": {"player_client": ["tv", "web_embedded"]}}},
]


def download(url: str, workdir: Path, quality: str, range_from, range_to):
    """Descarga el video (o solo el tramo pedido). Devuelve (ruta, título, offset_seg)."""
    import yt_dlp
    from yt_dlp.utils import DownloadError, download_range_func

    # "2160p" (Máxima 4K), "1440p", "1080p", "720p". Si el video no llega a esa calidad, baja solo a la mejor que haya.
    digits = "".join(ch for ch in str(quality) if ch.isdigit())
    height = int(digits) if digits else 1080
    base = {
        "quiet": True,
        "noplaylist": True,
        # con respaldos: la calidad pedida -> la mejor que haya -> cualquier formato
        "format": f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / "source.%(ext)s"),
        # si falta el componente que resuelve el reto de JavaScript de YouTube, lo baja solo
        "remote_components": ["ejs:github"],
    }
    if config.COOKIES_FILE:
        base["cookiefile"] = config.COOKIES_FILE

    start, end = parse_ts(range_from), parse_ts(range_to)
    last_err = None

    for extra in _VARIANTS:
        opts = {**base, **extra}
        try:
            with yt_dlp.YoutubeDL({**opts, "skip_download": True}) as y:
                info = y.extract_info(url, download=False)
            title = info.get("title") or url
            duration = info.get("duration")

            dl = dict(opts)
            offset = 0.0
            if start is not None or end is not None:
                s0 = start or 0.0
                e0 = end or duration or 36000.0
                dl["download_ranges"] = download_range_func(None, [(s0, e0)])
                dl["force_keyframes_at_cuts"] = True
                offset = s0

            for old in workdir.glob("source.*"):   # limpia restos de un intento anterior
                old.unlink(missing_ok=True)
            with yt_dlp.YoutubeDL(dl) as y:
                y.download([url])

            files = sorted(workdir.glob("source.*"))
            if not files:
                raise RuntimeError("yt-dlp no produjo ningún archivo")
            return files[0], title, offset
        except DownloadError as e:
            last_err = e
            msg = str(e)
            if "format is not available" in msg or "Requested format" in msg or "HTTP Error 403" in msg:
                print(f"  yt-dlp: {msg[:90]}… pruebo otra forma de pedirlo.", flush=True)
                continue
            raise   # otro tipo de error (bot, privado, borrado…): se muestra tal cual

    raise RuntimeError(
        "YouTube no entregó ningún formato descargable. Reconstruye el worker (cierra y abre INICIAR-WORKER.bat) "
        "para actualizar yt-dlp, y si sigue igual prueba con cookies.txt (COOKIES_FILE). Detalle: " + str(last_err)[:250]
    )
