from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class UsuarioCreate(BaseModel):
    nombre: str
    email: str
    password: str

class UsuarioOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    email: str
    password: str

class ProductoBase(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    categoria_id: Optional[int] = None
    stock_minimo: int = 0

class ProductoCreate(ProductoBase):
    stock_inicial: int = 0

class ProductoUpdate(ProductoBase):
    pass

class ProductoOut(ProductoBase):
    id: int
    stock_actual: int
    alerta_stock_bajo: bool = False

    model_config = ConfigDict(from_attributes=True)

class MovimientoCreate(BaseModel):
    producto_id: int
    tipo: str
    cantidad: int
    usuario: str
    notas: Optional[str] = None

class MovimientoUpdate(BaseModel):
    cantidad: Optional[int] = None
    usuario: Optional[str] = None
    notas: Optional[str] = None

class MovimientoOut(BaseModel):
    id: int
    producto_id: int
    tipo: str
    cantidad: int
    usuario: str
    notas: Optional[str] = None
    fecha: datetime
    # Información del producto vinculado
    producto_sku: Optional[str] = None
    producto_nombre: Optional[str] = None
    producto_imagen: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
