from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    trust_score = Column(Float, default=1.0)
    tier = Column(String, default="REGULAR")

    orders = relationship("Order", back_populates="client")
    claims = relationship("Claim", back_populates="client")

class Product(Base):
    __tablename__ = "products"

    sku = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    is_returnable = Column(Boolean, default=True)  # Guardrail

    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    delivery_date = Column(DateTime, nullable=True)
    status = Column(String, default="delivered")

    client = relationship("Client", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    claims = relationship("Claim", back_populates="order")

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    description = Column(Text, nullable=False)
    is_damaged = Column(Boolean, default=False)
    ai_confidence_score = Column(Float, default=0.0)
    requires_hitl = Column(Boolean, default=False)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="claims")
    client = relationship("Client", back_populates="claims")