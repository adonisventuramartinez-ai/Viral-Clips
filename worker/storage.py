"""Storage del bucket 'clips': Supabase o Cloudflare R2 según STORAGE_DRIVER.

El bucket 'uploads' NO pasa por aquí: sigue en Supabase (branding, previews y subidas
del navegador). Así el cambio de egress queda limitado a los MP4/miniaturas de clips.

La interfaz es la misma para los dos drivers:
    upload(bucket, path, data, content_type)
    download(bucket, path) -> bytes
    signed_url(bucket, path, seconds, download=False) -> str | None
    remove(bucket, paths)
"""
import os

import config  # noqa: F401  (carga worker/.env)

CLIPS_BUCKET = "clips"
_client = None


def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def uses_r2(bucket=CLIPS_BUCKET):
    """Solo el bucket de clips se mueve a R2; el resto sigue igual."""
    # load_dotenv() ya puso .env en os.environ; si no hay nada, el default es Supabase.
    driver = os.environ.get("STORAGE_DRIVER") or "supabase"
    return driver.strip().lower() == "r2" and bucket == CLIPS_BUCKET


def _bucket(bucket):
    return _env("R2_CLIPS_BUCKET", CLIPS_BUCKET) if bucket == CLIPS_BUCKET else bucket


def client():
    """Cliente S3 de R2 (se crea una vez). Se puede sustituir en los tests."""
    global _client
    if _client is None:
        import boto3

        account = _env("R2_ACCOUNT_ID")
        endpoint = _env("R2_ENDPOINT") or (f"https://{account}.r2.cloudflarestorage.com" if account else "")
        if not endpoint:
            raise RuntimeError("Falta R2_ACCOUNT_ID (o R2_ENDPOINT) en worker/.env")
        _client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
            region_name=_env("R2_REGION", "auto"),
        )
    return _client


def _sb():
    import db  # import diferido: db.py importa este módulo

    return db.sb.storage


def supabase_ready():
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def r2_ready():
    endpoint = _env("R2_ENDPOINT") or (f"https://{_env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com" if _env("R2_ACCOUNT_ID") else "")
    return bool(endpoint and _env("R2_ACCESS_KEY_ID") and _env("R2_SECRET_ACCESS_KEY"))


def _warn(what, e):
    print(f"Aviso: storage {what} falló ({str(e)[:140]}); uso el otro.", flush=True)


def _r2_upload(bucket, path, data, content_type):
    return client().put_object(Bucket=_bucket(bucket), Key=path, Body=data, ContentType=content_type)


def _sb_upload(bucket, path, data, content_type):
    return _sb().from_(bucket).upload(path, data, {"content-type": content_type, "upsert": "true"})


def _r2_download(bucket, path):
    return client().get_object(Bucket=_bucket(bucket), Key=path)["Body"].read()


def _sb_download(bucket, path):
    return _sb().from_(bucket).download(path)


def _r2_sign(bucket, path, seconds, download):
    params = {"Bucket": _bucket(bucket), "Key": path}
    if download:
        name = path.rsplit("/", 1)[-1].replace('"', "")
        params["ResponseContentDisposition"] = f'attachment; filename="{name}"'
    u = client().generate_presigned_url("get_object", Params=params, ExpiresIn=int(seconds))
    return u or None


def _sb_sign(bucket, path, seconds):
    r = _sb().from_(bucket).create_signed_url(path, seconds)
    u = r.get("signedURL") or r.get("signed_url") or r.get("signedUrl")
    if u and not u.startswith("http"):
        u = f"{config.SUPABASE_URL.rstrip('/')}/storage/v1{u if u.startswith('/') else '/' + u}"
    return u or None


def _r2_remove(bucket, paths):
    return client().delete_objects(Bucket=_bucket(bucket), Delete={"Objects": [{"Key": p} for p in paths]})


def _sb_remove(bucket, paths):
    return _sb().from_(bucket).remove(paths)


def _two(bucket, r2_fn, sb_fn, *args, **kwargs):
    """Clips: prueba el driver elegido y, si falla, el otro. El resto sigue solo en Supabase."""
    if bucket != CLIPS_BUCKET:
        return sb_fn(bucket, *args, **kwargs)
    prefer_r2 = uses_r2(bucket)
    order = []
    if prefer_r2 and r2_ready():
        order.append(("R2", r2_fn))
    if supabase_ready():
        order.append(("Supabase", sb_fn))
    if not prefer_r2 and r2_ready():
        order.append(("R2", r2_fn))
    if not order:
        return r2_fn(bucket, *args, **kwargs) if prefer_r2 else sb_fn(bucket, *args, **kwargs)
    last = None
    for name, fn in order:
        try:
            out = fn(bucket, *args, **kwargs)
            if out is not None:      # una URL firmada vacía también cuenta como fallo
                return out
            last = None
        except Exception as e:  # noqa: BLE001
            last = e
            _warn(name, e)
    if last:
        raise last
    return None


def upload(bucket, path, data, content_type):
    return _two(bucket, _r2_upload, _sb_upload, path, data, content_type)


def download(bucket, path):
    out = _two(bucket, _r2_download, _sb_download, path)
    if out is None:
        raise RuntimeError(f"No se pudo descargar {path} de ningún storage")
    return out


def signed_url(bucket, path, seconds=3600, download=False):
    return _two(bucket,
                lambda b, p, s, d: _r2_sign(b, p, s, d),
                lambda b, p, s, d: _sb_sign(b, p, s),
                path, seconds, download)


def remove(bucket, paths):
    paths = [p for p in paths if p]
    if not paths:
        return None
    return _two(bucket, _r2_remove, _sb_remove, paths)
