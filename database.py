import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Detectar URL de PostgreSQL desde las Variables de Entorno de Railway
DATABASE_URL = os.getenv("DATABASE_URL")

# Si la URL viene de Railway (postgresql://), SQLAlchemy exige formato 'postgresql://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Si no hay variable (desarrollo local), usar SQLite como respaldo
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./sql_app.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
