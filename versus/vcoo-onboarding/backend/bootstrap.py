from .db import SessionLocal

# Dev helper to bootstrap DB tables

def bootstrap():
    db = SessionLocal()
    db.close()

if __name__ == '__main__':
    bootstrap()
