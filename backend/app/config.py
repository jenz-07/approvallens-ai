from pydantic_settings import BaseSettings
from pydantic import model_validator

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://approval:approval@db/approval'
    redis_url: str = 'redis://redis:6379/0'
    environment: str = 'development'
    demo_enabled: bool = False
    storage_dir: str = '/data/private'
    storage_backend: str = 'filesystem'
    s3_bucket: str = ''
    s3_endpoint: str | None = None
    allowed_origin: str = 'http://localhost:3000'
    max_file_mb: int = 15
    max_pages: int = 30
    max_document_versions: int = 200
    max_image_pixels: int = 25000000
    session_hours: int = 8
    retention_days: int = 365
    ai_enabled: bool = False
    @model_validator(mode='after')
    def secure(self):
        if self.database_url.startswith(('postgres://','postgresql://')):
            self.database_url='postgresql+psycopg://'+self.database_url.split('://',1)[1]
        if self.environment not in ('development','production','test'): raise ValueError('Unknown environment')
        if self.storage_backend not in ('filesystem','s3'): raise ValueError('Unknown storage backend')
        if self.storage_backend=='s3' and not self.s3_bucket: raise ValueError('S3_BUCKET required for S3 storage')
        if self.environment == 'production' and (self.demo_enabled or not self.allowed_origin.startswith('https://')):
            raise ValueError('Production requires HTTPS and demo disabled')
        if self.environment=='production' and ('approval:approval@' in self.database_url or 'local-development-change-me' in self.database_url): raise ValueError('Use independent production database credentials')
        if self.ai_enabled:
            raise ValueError('No model provider configured. Keep AI_ENABLED=false or implement the provider interface.')
        return self
settings = Settings()
