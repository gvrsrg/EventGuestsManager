import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:qqq@localhost:5432/postgres"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "true").lower() == "true"

def init_db():
    if AUTO_CREATE_DB:
        SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session