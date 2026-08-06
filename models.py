from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)
    password = Column(String, nullable=False)
    rol = Column(String, default="OPERADOR")

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, index=True, nullable=False)
    categoria = Column(String, default="Otros")
    descripcion = Column(Text, nullable=True)
    imagen_url = Column(String, nullable=True)
    categoria_id = Column(Integer, nullable=True)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=5)

    movimientos = relationship("MovimientoInventario", back_populates="producto")

class MovimientoInventario(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    tipo = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
    usuario = Column(String, nullable=False)
    notas = Column(Text, nullable=True)

    producto = relationship("Producto", back_populates="movimientos")
