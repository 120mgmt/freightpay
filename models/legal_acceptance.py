from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from utils.database import Base


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document = Column(String(50), nullable=False)
    accepted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="legal_acceptances")
