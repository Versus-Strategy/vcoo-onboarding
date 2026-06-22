from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Read connection URL from environment (may or may not contain password)
DATABASE_URL = os.getenv('POSTGRES_URL', 'postgresql://postgres:***@db:5432/vcoo')

def _create_connection():
    """Create a psycopg2 connection, using keyword args to avoid
    psycopg2's DSN parser bugs with dots in usernames (needed for Supabase pooler)."""
    import psycopg2
    from urllib.parse import urlparse, unquote
    
    parsed = urlparse(DATABASE_URL)
    
    username = unquote(parsed.username) if parsed.username else 'postgres'
    paassword = unquote(parsed.password) if parsed.password else (os.getenv('PGPASSWORD') or '')
    host = parsed.hostname
    port_val = parsed.port or 5432
    dbname = parsed.path.lstrip('/') or 'postgres'
    
    kwargs = {
        'host': host,
        'port': port_val,
        'user': username,
        'password': paassword,
        'dbname': dbname,
        'connect_timeout': 10,
    }
    
    if host and ('supabase.co' in host or os.getenv('VERCEL_ENV')):
        kwargs['sslmode'] = 'require'
    
    return psycopg2.connect(**kwargs)

engine = create_engine(
    'postgresql://',
    creator=_create_connection,
    pool_size=1,
    max_overflow=3,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
