from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UsuarioBase(BaseModel):
    nombre: str

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioOut(UsuarioBase):
    id: int
    rol: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    nombre: str
    password: str

class ProductoBase(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    categoria_id: Optional[int] = None
    stock_minimo: int = 5

class ProductoCreate(ProductoBase):
    stock_inicial: int = 0

class ProductoUpdate(BaseModel):
    sku: str
    nombre: str
    imagen_url: Optional[str] = None
    stock_minimo: int

class ProductoOut(ProductoBase):
    id: int
    stock_actual: int
    alerta_stock_bajo: bool = False

    class Config:
        from_attributes = True

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
    fecha: datetime
    usuario: str
    notas: Optional[str] = None
    producto_sku: Optional[str] = None
    producto_nombre: Optional[str] = None
    producto_imagen: Optional[str] = None

    class Config:
        from_attributes = True
