from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv('POSTGRES_URL', 'postgresql://postgres:***@db:5432/vcoo')

# Supabase requires SSL connections; serverless benefits from connection pooling
_connect_args = {}
if 'supabase.co' in DATABASE_URL or os.getenv('VERCEL_ENV'):
    _connect_args['sslmode'] = 'require'

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args if _connect_args else {},
    pool_size=1,
    max_overflow=3,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
