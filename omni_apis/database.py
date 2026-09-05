from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

Base = declarative_base()

class APIKey(Base):
    __tablename__ = 'api_keys'
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True)
    owner = Column(String)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

engine = create_engine('sqlite:///omni_proxy_metrics.db')
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def log_usage(key: str, tokens: int):
    with SessionLocal() as db:
        record = db.query(APIKey).filter(APIKey.key == key).first()
        if not record:
            record = APIKey(key=key, tokens_used=0)
            db.add(record)
        record.tokens_used += tokens
        db.commit()
