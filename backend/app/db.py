from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings
engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True, **({'connect_args': {'check_same_thread': False}} if settings.database_url.startswith('sqlite') else {}))
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_fk(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
def get_db():
    with SessionLocal() as db:
        yield db
