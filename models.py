from datetime import datetime
from database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(200))

    productos = relationship("Producto", back_populates="categoria")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    descripcion = Column(Text)
    imagen_url = Column(String, nullable=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id", ondelete="SET NULL"))
    stock_actual = Column(Integer, default=0, nullable=False)
    stock_minimo = Column(Integer, default=0, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    categoria = relationship("Categoria", back_populates="productos")
    movimientos = relationship("MovimientoInventario", back_populates="producto")


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(
        Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False
    )
    tipo_movimiento = Column(String(10), nullable=False)  # 'ENTRADA' o 'SALIDA'
    cantidad = Column(Integer, nullable=False)
    usuario = Column(
        String(50), nullable=False, default="Anonimo"
    )  # 👈 NUEVO CAMPO
    motivo = Column(String(255))
    fecha_movimiento = Column(DateTime, default=datetime.utcnow)

    producto = relationship("Producto", back_populates="movimientos")