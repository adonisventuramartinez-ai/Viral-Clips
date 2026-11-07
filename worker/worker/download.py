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


def download(url: str, workdir: Path, quality: str, range_from, range_to):
    """Descarga el video (o solo el tramo pedido). Devuelve (ruta, título, offset_seg)."""
    import yt_dlp
    from yt_dlp.utils import download_range_func

    # "2160p" (Máxima 4K), "1440p", "1080p", "720p". Si el video no llega a esa calidad, baja solo a la mejor que haya.
    digits = "".join(ch for ch in str(quality) if ch.isdigit())
    height = int(digits) if digits else 1080
    base = {
        "quiet": True,
        "noplaylist": True,
        "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / "source.%(ext)s"),
    }
    if config.COOKIES_FILE:
        base["cookiefile"] = config.COOKIES_FILE

    with yt_dlp.YoutubeDL({**base, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    title = info.get("title") or url
    duration = info.get("duration")

    start, end = parse_ts(range_from), parse_ts(range_to)
    opts = dict(base)
    offset = 0.0
    if start is not None or end is not None:
        start = start or 0.0
        end = end or duration or 36000.0
        opts["download_ranges"] = download_range_func(None, [(start, end)])
        opts["force_keyframes_at_cuts"] = True
        offset = start

    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])

    files = sorted(workdir.glob("source.*"))
    if not files:
        raise RuntimeError("yt-dlp no produjo ningún archivo")
    return files[0], title, offset
