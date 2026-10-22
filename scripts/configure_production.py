"""Create unique deployment credentials. Never prints secrets; never overwrites config."""
import argparse,re,secrets,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--domain',required=True);p.add_argument('--email',required=True);args=p.parse_args()
if not re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}',args.domain):raise SystemExit('Use a DNS hostname, without scheme or path')
if not re.fullmatch(r'[^\s@=]+@[^\s@=]+\.[^\s@=]+',args.email):raise SystemExit('Provide a certificate contact email')
root=Path(__file__).resolve().parents[1];target=root/'.env.production'
db=secrets.token_hex(32);redis=secrets.token_hex(32)
text=f'''ENVIRONMENT=production
DEMO_ENABLED=false
DOMAIN={args.domain.lower()}
CADDY_EMAIL={args.email}
POSTGRES_PASSWORD={db}
REDIS_PASSWORD={redis}
DATABASE_URL=postgresql+psycopg://approval:{db}@db/approval
REDIS_URL=redis://:{redis}@redis:6379/0
STORAGE_DIR=/data/private
STORAGE_BACKEND=filesystem
ALLOWED_ORIGIN=https://{args.domain.lower()}
AI_ENABLED=false
MAX_FILE_MB=15
MAX_PAGES=30
MAX_DOCUMENT_VERSIONS=200
SESSION_HOURS=8
RETENTION_DAYS=365
'''
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(text)
print('Created .env.production. Keep it private and back it up securely.')
