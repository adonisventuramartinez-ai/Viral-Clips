"""El bucket de clips debe seguir funcionando si falla el storage elegido."""
import os

import storage
from test_storage import FakeS3


class BadS3:
    def put_object(self, **kw):
        raise RuntimeError("R2 caído")

    def get_object(self, **kw):
        raise RuntimeError("R2 caído")

    def generate_presigned_url(self, method, **kw):
        raise RuntimeError("R2 caído")

    def delete_objects(self, **kw):
        raise RuntimeError("R2 caído")


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def upload(self, path, data, opts):
        self.objects[path] = data
        return {"path": path}

    def download(self, path):
        return self.objects[path]

    def create_signed_url(self, path, secs):
        return {"signedURL": f"https://sb.test/{path}?e={secs}"}

    def remove(self, paths):
        for p in paths:
            self.objects.pop(p, None)
        return None


class FakeSB:
    def __init__(self):
        self.bucket = FakeBucket()

    def from_(self, bucket):
        return self.bucket


class BadSB:
    def from_(self, bucket):
        return self


def upload(self, *a, **kw):
    raise RuntimeError("Supabase caído")


def download(self, *a, **kw):
    raise RuntimeError("Supabase caído")


def create_signed_url(self, *a, **kw):
    raise RuntimeError("Supabase caído")


def remove(self, *a, **kw):
    raise RuntimeError("Supabase caído")


_BAD_SB = BadSB()
for _name, _fn in (("upload", upload), ("download", download),
                   ("create_signed_url", create_signed_url), ("remove", remove)):
    setattr(BadSB, _name, _fn)

_ENV_KEYS = ("STORAGE_DRIVER", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_CLIPS_BUCKET")


def _setup(driver):
    prev = {k: os.environ.get(k) for k in _ENV_KEYS}
    os.environ.update({"STORAGE_DRIVER": driver, "R2_ENDPOINT": "https://t3.storage.dev",
                       "R2_ACCESS_KEY_ID": "tid_test", "R2_SECRET_ACCESS_KEY": "tsec_test",
                       "R2_CLIPS_BUCKET": "clips"})
    storage.config.SUPABASE_URL = "https://x.supabase.co"
    storage.config.SUPABASE_KEY = "k"
    return prev


def _restore(prev):
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_r2_caido_usa_supabase():
    prev = _setup("r2")
    old_client, old_sb = storage._client, storage._sb
    fake = FakeSB()
    try:
        storage._client = BadS3()
        storage._sb = lambda: fake
        storage.upload("clips", "u/a.mp4", b"v", "video/mp4")
        assert storage.download("clips", "u/a.mp4") == b"v"
        assert "sb.test" in (storage.signed_url("clips", "u/a.mp4", 60) or "")
        storage.remove("clips", ["u/a.mp4"])
        assert "u/a.mp4" not in fake.bucket.objects
    finally:
        storage._client, storage._sb = old_client, old_sb
        _restore(prev)


def test_supabase_caido_usa_r2():
    prev = _setup("supabase")
    old_client, old_sb = storage._client, storage._sb
    fake = FakeS3()
    try:
        storage._client = fake
        storage._sb = lambda: _BAD_SB
        storage.upload("clips", "u/b.mp4", b"v", "video/mp4")
        assert fake.objects[("clips", "u/b.mp4")] == b"v"
        assert storage.download("clips", "u/b.mp4") == b"v"
        assert "r2.test" in (storage.signed_url("clips", "u/b.mp4", 60) or "")
        storage.remove("clips", ["u/b.mp4"])
        assert ("clips", "u/b.mp4") not in fake.objects
    finally:
        storage._client, storage._sb = old_client, old_sb
        _restore(prev)


if __name__ == "__main__":
    test_r2_caido_usa_supabase()
    test_supabase_caido_usa_r2()
    print("FALLBACK OK")
