from datetime import datetime
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles

import models
import schemas
from database import Base, engine, get_db

# Crear tablas automáticamente
Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Sistema de Inventario Brindes MKT")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. Obtener lista de productos
@app.get("/api/productos", response_model=List[schemas.ProductoOut])
def listar_productos(buscar: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Producto)
    if buscar:
        query = query.filter(
            (models.Producto.nombre.ilike(f"%{buscar}%"))
            | (models.Producto.sku.ilike(f"%{buscar}%"))
        )
    productos = query.order_by(models.Producto.nombre.asc()).all()

    resultado = []
    for p in productos:
        prod_dict = schemas.ProductoOut.model_validate(p)
        prod_dict.alerta_stock_bajo = p.stock_actual <= p.stock_minimo
        resultado.append(prod_dict)
    return resultado


# 2. Crear un nuevo producto
@app.post(
    "/api/productos",
    response_model=schemas.ProductoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_producto(producto: schemas.ProductoCreate, db: Session = Depends(get_db)):
    db_sku = (
        db.query(models.Producto).filter(models.Producto.sku == producto.sku).first()
    )
    if db_sku:
        raise HTTPException(
            status_code=400, detail="Ya existe un producto con este SKU."
        )

    nuevo_producto = models.Producto(
        sku=producto.sku,
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        imagen_url=producto.imagen_url,
        categoria_id=producto.categoria_id,
        stock_actual=producto.stock_inicial,
        stock_minimo=producto.stock_minimo,
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)

    prod_out = schemas.ProductoOut.model_validate(nuevo_producto)
    prod_out.alerta_stock_bajo = (
        nuevo_producto.stock_actual <= nuevo_producto.stock_minimo
    )
    return prod_out


# 3. Registrar Entrada o Salida con USUARIO
@app.post(
    "/api/movimientos",
    response_model=schemas.MovimientoOut,
    status_code=status.HTTP_201_CREATED,
)
def registrar_movimiento(
    movimiento: schemas.MovimientoCreate, db: Session = Depends(get_db)
):
    producto = (
        db.query(models.Producto)
        .filter(models.Producto.id == movimiento.producto_id)
        .first()
    )

    if not producto:
        raise HTTPException(
            status_code=404, detail="El producto especificado no existe."
        )

    if (
        movimiento.tipo_movimiento == "SALIDA"
        and producto.stock_actual < movimiento.cantidad
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Stock actual: {producto.stock_actual}",
        )

    # Actualizar stock
    if movimiento.tipo_movimiento == "ENTRADA":
        producto.stock_actual += movimiento.cantidad
    elif movimiento.tipo_movimiento == "SALIDA":
        producto.stock_actual -= movimiento.cantidad

    nuevo_movimiento = models.MovimientoInventario(
        producto_id=movimiento.producto_id,
        tipo_movimiento=movimiento.tipo_movimiento,
        cantidad=movimiento.cantidad,
        usuario=movimiento.usuario,  # 👈 Aquí guarda quién hizo el cambio
        motivo=movimiento.motivo,
    )

    db.add(nuevo_movimiento)
    db.commit()
    db.refresh(nuevo_movimiento)
    return nuevo_movimiento


# 4. Consultar Historial de Movimientos
@app.get("/api/movimientos", response_model=List[schemas.MovimientoOut])
def listar_movimientos(db: Session = Depends(get_db)):
    return (
        db.query(models.MovimientoInventario)
        .order_by(models.MovimientoInventario.fecha_movimiento.desc())
        .all()
    )


# 5. Eliminar un producto
@app.delete("/api/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = (
        db.query(models.Producto)
        .filter(models.Producto.id == producto_id)
        .first()
    )

    if not producto:
        raise HTTPException(
            status_code=404, detail="El producto especificado no existe."
        )

    # Eliminar sus movimientos previos y luego el producto
    db.query(models.MovimientoInventario).filter(
        models.MovimientoInventario.producto_id == producto_id
    ).delete()

    db.delete(producto)
    db.commit()
    return None

# Permitir que FastAPI sirva archivos locales como imágenes
app.mount("/static", StaticFiles(directory="."), name="static")

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def leer_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()