"""Private artifact storage. Local storage is an explicit offline-test adapter."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import uuid
from pipeline.runtime import exclusive_lock


class PublicationConflict(RuntimeError):
    pass


def valid_key(key):
    if (not isinstance(key, str) or not key or "\\" in key
        or key.startswith("/") or any(part in {"", ".", ".."} for part in key.split("/"))):
        raise ValueError("Invalid object key")
    return str(PurePosixPath(key))


class LocalStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        target = self.root / valid_key(key)
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Object key escapes storage")
        return target

    def read(self, key):
        path = self.path(key)
        if not path.exists(): return None, None
        value = path.read_bytes()
        return value, hashlib.sha256(value).hexdigest()

    def put_file(self, key, source):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_lock(self.root / ".publication.lock"):
            if path.exists(): return
            temporary = path.with_name(path.name + uuid.uuid4().hex + ".tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, path)

    def download(self, key, destination):
        shutil.copyfile(self.path(key), destination)

    def write(self, key, value, *, expected=None, conditional=False):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_lock(self.root / ".publication.lock"):
            if conditional and self.read(key)[1] != expected:
                raise PublicationConflict("A newer release was promoted first")
            temporary = path.with_name(path.name + uuid.uuid4().hex + ".tmp")
            temporary.write_bytes(value)
            os.replace(temporary, path)


class S3Store:
    def __init__(self, bucket, prefix="new-x1"):
        import boto3
        from botocore.config import Config
        self.client = boto3.client("s3", config=Config(connect_timeout=10, read_timeout=120,
            retries={"max_attempts": 3, "mode": "standard"}))
        self.bucket = bucket
        self.prefix = valid_key(prefix)

    def key(self, key): return self.prefix + "/" + valid_key(key)

    def read(self, key):
        from botocore.exceptions import ClientError
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=self.key(key))
            with result["Body"] as body:
                return body.read(), result["ETag"]
        except ClientError as error:
            if error.response["Error"]["Code"] in {"NoSuchKey", "404"}: return None, None
            raise

    def put_file(self, key, source):
        from botocore.exceptions import ClientError
        try:
            with Path(source).open("rb") as body:
                self.client.put_object(Bucket=self.bucket, Key=self.key(key), Body=body,
                    ServerSideEncryption="AES256", IfNoneMatch="*")
        except ClientError as error:
            if error.response["Error"]["Code"] not in {"PreconditionFailed", "412"}: raise

    def download(self, key, destination):
        self.client.download_file(self.bucket, self.key(key), str(destination))

    def write(self, key, value, *, expected=None, conditional=False):
        from botocore.exceptions import ClientError
        options = ({"IfMatch": expected} if expected else {"IfNoneMatch": "*"}) if conditional else {}
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key(key), Body=value,
                ContentType="application/json", ServerSideEncryption="AES256", **options)
        except ClientError as error:
            if error.response["Error"]["Code"] in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
                raise PublicationConflict("A newer release was promoted first") from error
            raise


def configured_store():
    if os.getenv("RELEASE_STORE_DIR"):
        if os.getenv("APP_ENV", "production") not in {"development", "test"}:
            raise ValueError("Local release storage is allowed only for explicit development/test")
        return LocalStore(os.environ["RELEASE_STORE_DIR"])
    bucket = os.getenv("RELEASE_BUCKET")
    if not bucket: raise ValueError("Private RELEASE_BUCKET must be configured")
    return S3Store(bucket, os.getenv("RELEASE_PREFIX", "new-x1"))


def json_bytes(payload):
    return json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
