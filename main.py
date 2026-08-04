import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Control de Stock - Brindes MKT")

@app.get("/")
def leer_frontend():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        return FileResponse(ruta_html)
    return HTMLResponse("<h2>Error: No se encontró index.html en el servidor.</h2>")

# --- USUARIOS (CADASTRO Y LOGIN) ---

@app.post("/api/registro", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado.")
    
    nuevo_usuario = models.Usuario(
        nombre=usuario.nombre,
        email=usuario.email,
        password=usuario.password
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

@app.post("/api/login", response_model=schemas.UsuarioOut)
def login_usuario(creds: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == creds.email, models.Usuario.password == creds.password).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    return usuario

# --- PRODUCTOS ---

@app.get("/api/productos", response_model=List[schemas.ProductoOut])
def obtener_productos(db: Session = Depends(get_db)):
    productos = db.query(models.Producto).all()
    resultado = []
    for prod in productos:
        prod_out = schemas.ProductoOut.model_validate(prod)
        prod_out.alerta_stock_bajo = prod.stock_actual <= prod.stock_minimo
        resultado.append(prod_out)
    return resultado

@app.post("/api/productos", response_model=schemas.ProductoOut, status_code=status.HTTP_201_CREATED)
def crear_producto(producto: schemas.ProductoCreate, db: Session = Depends(get_db)):
    db_sku = db.query(models.Producto).filter(models.Producto.sku == producto.sku).first()
    if db_sku:
        raise HTTPException(status_code=400, detail="Ya existe un producto con este Código / SKU.")

    nuevo_producto = models.Producto(
        sku=producto.sku,
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        imagen_url=producto.imagen_url,
        categoria_id=producto.categoria_id,
        stock_actual=producto.stock_inicial,
        stock_minimo=producto.stock_minimo
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)

    prod_out = schemas.ProductoOut.model_validate(nuevo_producto)
    prod_out.alerta_stock_bajo = nuevo_producto.stock_actual <= nuevo_producto.stock_minimo
    return prod_out

@app.delete("/api/productos/{producto_id}", status_code=status.HTTP_200_OK)
def eliminar_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    
    db.query(models.MovimientoInventario).filter(models.MovimientoInventario.producto_id == producto_id).delete()
    db.delete(producto)
    db.commit()
    return {"mensaje": "Producto eliminado exitosamente"}

# --- MOVIMIENTOS ---

@app.get("/api/movimientos", response_model=List[schemas.MovimientoOut])
def obtener_movimientos(db: Session = Depends(get_db)):
    return db.query(models.MovimientoInventario).order_by(models.MovimientoInventario.fecha.desc()).limit(50).all()

@app.post("/api/movimientos", status_code=status.HTTP_201_CREATED)
def registrar_movimiento(movimiento: schemas.MovimientoCreate, db: Session = Depends(get_db)):
    producto = db.query(models.Producto).filter(models.Producto.id == movimiento.producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if movimiento.tipo == "SALIDA" and producto.stock_actual < movimiento.cantidad:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {producto.stock_actual}")

    if movimiento.tipo == "ENTRADA":
        producto.stock_actual += movimiento.cantidad
    elif movimiento.tipo == "SALIDA":
        producto.stock_actual -= movimiento.cantidad

    nuevo_mov = models.MovimientoInventario(
        producto_id=movimiento.producto_id,
        tipo=movimiento.tipo,
        cantidad=movimiento.cantidad,
        usuario=movimiento.usuario,
        notas=movimiento.notas
    )
    db.add(nuevo_mov)
    db.commit()
    return {"mensaje": "Movimiento registrado", "nuevo_stock": producto.stock_actual}
