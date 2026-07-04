from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DATABASE_URL = os.getenv('POSTGRES_URL', 'sqlite:///./test.db')

# SQLAlchemy 2.0 maneja URLs con dots en username sin problema.
# connect_args={'sslmode': 'require'} para Supabase.
connect_args = {}
if 'supabase.co' in DATABASE_URL or os.getenv('VERCEL_ENV'):
    connect_args['sslmode'] = 'require'

engine = create_engine(
    DATABASE_URL,
    pool_size=1,
    max_overflow=3,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
