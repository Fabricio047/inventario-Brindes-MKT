from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    imagen_url = Column(String, nullable=True)
    categoria_id = Column(Integer, nullable=True)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=0)

    movimientos = relationship("MovimientoInventario", back_populates="producto")

class MovimientoInventario(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    tipo = Column(String, nullable=False)  # ENTRADA o SALIDA
    cantidad = Column(Integer, nullable=False)
    usuario = Column(String, nullable=False)
    notas = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    producto = relationship("Producto", back_populates="movimientos")

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
