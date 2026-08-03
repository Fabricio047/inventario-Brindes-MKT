from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductoCreate(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: Optional[int] = None
    imagen_url: Optional[str] = None
    stock_inicial: int = Field(default=0, ge=0)
    stock_minimo: int = Field(default=0, ge=0)


class ProductoOut(BaseModel):
    id: int
    sku: str
    nombre: str
    descripcion: Optional[str]
    categoria_id: Optional[int]
    stock_actual: int
    stock_minimo: int
    alerta_stock_bajo: bool = False
    fecha_creacion: datetime
    imagen_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MovimientoCreate(BaseModel):
    producto_id: int
    tipo_movimiento: Literal["ENTRADA", "SALIDA"]
    cantidad: int = Field(gt=0, description="La cantidad debe ser mayor a 0")
    usuario: str = Field(min_length=1, description="Nombre de quien registra")
    motivo: Optional[str] = None


class MovimientoOut(BaseModel):
    id: int
    producto_id: int
    tipo_movimiento: str
    cantidad: int
    usuario: str  # 👈 NUEVO CAMPO
    motivo: Optional[str]
    fecha_movimiento: datetime

    model_config = ConfigDict(from_attributes=True)