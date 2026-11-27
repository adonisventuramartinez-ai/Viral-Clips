"""Pruebas del adaptador de storage (R2 para clips, Supabase para uploads)."""
import io
import os

import storage


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.types = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[(Bucket, Key)] = Body
        self.types[Key] = ContentType

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def generate_presigned_url(self, method, Params=None, ExpiresIn=None):
        assert method == "get_object"
        return f"https://r2.test/{Params['Bucket']}/{Params['Key']}?exp={ExpiresIn}"

    def delete_objects(self, Bucket, Delete):
        for obj in Delete["Objects"]:
            self.objects.pop((Bucket, obj["Key"]), None)


def test_clips_van_a_r2_y_uploads_no():
    previous_client = storage._client
    previous = {k: os.environ.get(k) for k in ("STORAGE_DRIVER", "R2_CLIPS_BUCKET")}
    fake = FakeS3()
    storage._client = fake
    os.environ["STORAGE_DRIVER"] = "r2"
    os.environ["R2_CLIPS_BUCKET"] = "clips"
    try:
        assert storage.uses_r2("clips")
        assert not storage.uses_r2("uploads"), "uploads debe seguir en Supabase"

        storage.upload("clips", "user/clip.mp4", b"video", "video/mp4")
        assert fake.objects[("clips", "user/clip.mp4")] == b"video"
        assert fake.types["user/clip.mp4"] == "video/mp4"
        assert storage.download("clips", "user/clip.mp4") == b"video"

        url = storage.signed_url("clips", "user/clip.mp4", 120)
        assert "clips/user/clip.mp4" in url and "exp=120" in url, url

        storage.remove("clips", ["user/clip.mp4"])
        assert ("clips", "user/clip.mp4") not in fake.objects
    finally:
        storage._client = previous_client
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_driver_por_defecto_es_supabase():
    previous = os.environ.get("STORAGE_DRIVER")
    os.environ.pop("STORAGE_DRIVER", None)
    try:
        assert not storage.uses_r2("clips")
    finally:
        if previous is not None:
            os.environ["STORAGE_DRIVER"] = previous


if __name__ == "__main__":
    test_clips_van_a_r2_y_uploads_no()
    test_driver_por_defecto_es_supabase()
    print("STORAGE OK")
