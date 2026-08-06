import os
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
import bcrypt
import jwt
import cloudinary
import cloudinary.uploader
import pandas as pd

import models
import schemas
from database import engine, get_db

SECRET_KEY = "LG_IMPORTADOS_SECRET_KEY_PROD_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

cloudinary.config( 
  cloud_name = "uozsov2p", 
  api_key = "759287856464937", 
  api_secret = "hiSNimBqxNAzCv1tdl3ua3IWkLc",
  secure = True
)


models.Base.metadata.create_all(bind=engine)

def aplicar_migraciones():
    from sqlalchemy import text
    from database import SessionLocal
    db = SessionLocal()
    try:
        # Intenta agregar la columna categoria si no existia en la tabla de PostgreSQL
        db.execute(text("ALTER TABLE productos ADD COLUMN IF NOT EXISTS categoria VARCHAR DEFAULT 'Otros';"))
        db.commit()
    except Exception as e:
        print(f"Nota migración: {e}")
    finally:
        db.close()

aplicar_migraciones()

app = FastAPI(title="Control de Stock - MKT")

def obtener_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        return plain_password == hashed_password
    except Exception:
        return False

def crear_token_acceso(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_usuario_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    exception_unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        nombre: str = payload.get("sub")
        if nombre is None:
            raise exception_unauthorized
    except jwt.PyJWTError:
        raise exception_unauthorized

    usuario = db.query(models.Usuario).filter(models.Usuario.nombre == nombre).first()
    if usuario is None:
        raise exception_unauthorized
    return usuario

def verificar_admin(usuario_actual: models.Usuario = Depends(obtener_usuario_actual)):
    if usuario_actual.rol != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de Administrador."
        )
    return usuario_actual

def garantizar_admin_maestro():
    db = Session(bind=engine)
    try:
        admin_nombre = "admin"
        admin_pass_raw = "admin123*"
        admin_existente = db.query(models.Usuario).filter(models.Usuario.nombre == admin_nombre).first()
        
        if not admin_existente:
            admin_maestro = models.Usuario(
                nombre=admin_nombre,
                email="admin@local.com",
                password=obtener_password_hash(admin_pass_raw),
                rol="ADMIN"
            )
            db.add(admin_maestro)
            db.commit()
        else:
            admin_existente.password = obtener_password_hash(admin_pass_raw)
            admin_existente.rol = "ADMIN"
            db.commit()
    except Exception as e:
        print(f"Error ajustando admin: {e}")
    finally:
        db.close()

garantizar_admin_maestro()

@app.get("/")
def leer_frontend():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        return FileResponse(ruta_html)
    return HTMLResponse("<h2>Error: No se encontró index.html</h2>")

@app.post("/api/upload")
async def subir_imagen(file: UploadFile = File(...), admin: models.Usuario = Depends(verificar_admin)):
    try:
        respuesta = cloudinary.uploader.upload(file.file, folder="brindes_mkt")
        return {"imagen_url": respuesta.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")

# --- AUTENTICACIÓN ---

@app.post("/api/registro", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    nombre_limpio = usuario.nombre.strip()
    db_user = db.query(models.Usuario).filter(models.Usuario.nombre.ilike(nombre_limpio)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este nombre de usuario ya existe.")
    
    nuevo_usuario = models.Usuario(
        nombre=nombre_limpio,
        email=f"{nombre_limpio.lower()}@local.com",
        password=obtener_password_hash(usuario.password),
        rol="OPERADOR"
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

@app.post("/api/login")
def login_usuario(creds: schemas.LoginRequest, db: Session = Depends(get_db)):
    nombre_limpio = creds.nombre.strip()
    usuario = db.query(models.Usuario).filter(models.Usuario.nombre.ilike(nombre_limpio)).first()
    
    if not usuario or not verificar_password(creds.password, usuario.password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    
    access_token = crear_token_acceso(data={"sub": usuario.nombre, "rol": usuario.rol})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "rol": usuario.rol
        }
    }

# --- PRODUCTOS ---

@app.get("/api/productos", response_model=List[schemas.ProductoOut])
def obtener_productos(db: Session = Depends(get_db), usuario: models.Usuario = Depends(obtener_usuario_actual)):
    productos = db.query(models.Producto).all()
    resultado = []
    for prod in productos:
        prod_out = schemas.ProductoOut.model_validate(prod)
        prod_out.alerta_stock_bajo = prod.stock_actual <= prod.stock_minimo
        resultado.append(prod_out)
    return resultado

@app.post("/api/productos", response_model=schemas.ProductoOut, status_code=status.HTTP_201_CREATED)
def crear_producto(producto: schemas.ProductoCreate, db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    db_sku = db.query(models.Producto).filter(models.Producto.sku == producto.sku).first()
    if db_sku:
        raise HTTPException(status_code=400, detail="Ya existe un producto con este Código / SKU.")

    nuevo_producto = models.Producto(
        sku=producto.sku,
        nombre=producto.nombre,
        categoria=producto.categoria or "Otros",
        descripcion=producto.descripcion,
        imagen_url=producto.imagen_url,
        stock_actual=producto.stock_inicial,
        stock_minimo=producto.stock_minimo
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)

    prod_out = schemas.ProductoOut.model_validate(nuevo_producto)
    prod_out.alerta_stock_bajo = nuevo_producto.stock_actual <= nuevo_producto.stock_minimo
    return prod_out

@app.put("/api/productos/{producto_id}", response_model=schemas.ProductoOut)
def editar_producto(producto_id: int, datos: schemas.ProductoUpdate, db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    prod = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    
    prod.sku = datos.sku
    prod.nombre = datos.nombre
    prod.categoria = datos.categoria or "Otros"
    if datos.imagen_url is not None and datos.imagen_url != "":
        prod.imagen_url = datos.imagen_url
    prod.stock_minimo = datos.stock_minimo
    db.commit()
    db.refresh(prod)
    
    prod_out = schemas.ProductoOut.model_validate(prod)
    prod_out.alerta_stock_bajo = prod.stock_actual <= prod.stock_minimo
    return prod_out

@app.delete("/api/productos/{producto_id}", status_code=status.HTTP_200_OK)
def eliminar_producto(producto_id: int, db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    
    db.query(models.MovimientoInventario).filter(models.MovimientoInventario.producto_id == producto_id).delete()
    db.delete(producto)
    db.commit()
    return {"mensaje": "Producto eliminado exitosamente"}

# --- MOVIMIENTOS ---

@app.get("/api/movimientos", response_model=List[schemas.MovimientoOut])
def obtener_movimientos(db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    movimientos = db.query(models.MovimientoInventario).order_by(models.MovimientoInventario.fecha.desc()).limit(100).all()
    resultado = []
    for mov in movimientos:
        mov_dict = schemas.MovimientoOut.model_validate(mov)
        if mov.producto:
            mov_dict.producto_sku = mov.producto.sku
            mov_dict.producto_nombre = mov.producto.nombre
            mov_dict.producto_imagen = mov.producto.imagen_url
        else:
            mov_dict.producto_nombre = "Producto Eliminado"
            mov_dict.producto_sku = "N/A"
        resultado.append(mov_dict)
    return resultado

@app.post("/api/movimientos", status_code=status.HTTP_201_CREATED)
def registrar_movimiento(movimiento: schemas.MovimientoCreate, db: Session = Depends(get_db), usuario: models.Usuario = Depends(obtener_usuario_actual)):
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
        usuario=usuario.nombre,
        notas=movimiento.notas
    )
    db.add(nuevo_mov)
    db.commit()
    return {"mensaje": "Movimiento registrado", "nuevo_stock": producto.stock_actual}

@app.put("/api/movimientos/{movimiento_id}")
def editar_movimiento(movimiento_id: int, datos: schemas.MovimientoUpdate, db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    mov = db.query(models.MovimientoInventario).filter(models.MovimientoInventario.id == movimiento_id).first()
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado.")
    
    if datos.notas is not None:
        mov.notas = datos.notas
    
    if datos.cantidad is not None and datos.cantidad != mov.cantidad:
        prod = db.query(models.Producto).filter(models.Producto.id == mov.producto_id).first()
        if prod:
            diferencia = datos.cantidad - mov.cantidad
            if mov.tipo == "ENTRADA":
                prod.stock_actual += diferencia
            elif mov.tipo == "SALIDA":
                prod.stock_actual -= diferencia
            mov.cantidad = datos.cantidad

    db.commit()
    return {"mensaje": "Movimiento actualizado correctamente"}

# --- EXPORTAR EXCEL ---

@app.get("/api/reportes/excel")
def descargar_reporte_excel(db: Session = Depends(get_db), usuario: models.Usuario = Depends(obtener_usuario_actual)):
    productos = db.query(models.Producto).all()
    
    data = []
    for p in productos:
        data.append({
            "Código / SKU": p.sku,
            "Producto": p.nombre,
            "Categoría": p.categoria or "Otros",
            "Stock Actual": p.stock_actual,
            "Stock Mínimo": p.stock_minimo,
            "Estado Stock": "ALERTA - BAJO" if p.stock_actual <= p.stock_minimo else "NORMAL",
            "URL Imagen": p.imagen_url or "Sin foto"
        })
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Stock MKT')
    output.seek(0)
    
    headers = {'Content-Disposition': 'attachment; filename="Inventario_Stock_MKT.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
