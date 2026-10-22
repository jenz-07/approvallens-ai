from pathlib import Path
import re
from .config import settings
class Storage:
    def _key(self, key):
        if not re.fullmatch(r'[a-f0-9-]{36}', key): raise ValueError('Invalid object key')
        return key
    def put(self, key, data):
        key = self._key(key)
        if settings.storage_backend == 's3':
            self.client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)
        else:
            root = Path(settings.storage_dir); root.mkdir(parents=True, exist_ok=True, mode=0o700)
            p = root / key
            with p.open('xb') as f: f.write(data)
            p.chmod(0o600)
    def get(self, key):
        key = self._key(key)
        if settings.storage_backend == 's3': return self.client().get_object(Bucket=settings.s3_bucket, Key=key)['Body'].read()
        return (Path(settings.storage_dir) / key).read_bytes()
    def delete(self, key):
        key = self._key(key)
        if settings.storage_backend == 's3': self.client().delete_object(Bucket=settings.s3_bucket, Key=key)
        else: (Path(settings.storage_dir) / key).unlink(missing_ok=True)
    def client(self):
        import boto3
        from botocore.config import Config
        return boto3.client('s3', endpoint_url=settings.s3_endpoint, config=Config(signature_version='s3v4',s3={'addressing_style':'path'},connect_timeout=10,read_timeout=60))
storage = Storage()
