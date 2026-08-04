import os
import io
import shutil
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

# Configuración de Claves JWT y Hasher
SECRET_KEY = "LG_IMPORTADOS_SECRET_KEY_PROD_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# Configurar Cloudinary con tus claves oficiales
cloudinary.config( 
  cloud_name = "uozsov2p", 
  api_key = "759287856464937", 
  api_secret = "hiSNimBqxNAzCv1tdl3ua3IWkLc",
  secure = True
)

# Crear tablas
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Control de Stock - Brindes MKT")

# --- FUNCIONES DE SEGURIDAD ---

def obtener_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Verificar con bcrypt
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        # Comparación fallback por si la clave antigua quedó en texto plano
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
        detail="Sesión inválida o expirada. Por favor inicie sesión de nuevo.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise exception_unauthorized
    except jwt.PyJWTError:
        raise exception_unauthorized

    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario is None:
        raise exception_unauthorized
    return usuario

def verificar_admin(usuario_actual: models.Usuario = Depends(obtener_usuario_actual)):
    if usuario_actual.rol != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de Administrador."
        )
    return usuario_actual

# Crear / Actualizar Admin por defecto al iniciar
def garantizar_admin_maestro():
    db = Session(bind=engine)
    try:
        admin_email = "admin@lgimportados.com"
        admin_pass_raw = "admin123*"
        admin_existente = db.query(models.Usuario).filter(models.Usuario.email == admin_email).first()
        
        if not admin_existente:
            admin_maestro = models.Usuario(
                nombre="ADMINISTRADOR",
                email=admin_email,
                password=obtener_password_hash(admin_pass_raw),
                rol="ADMIN"
            )
            db.add(admin_maestro)
            db.commit()
        else:
            # Asegurar que la contraseña esté correctamente hasheada y con rol ADMIN
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
    return HTMLResponse("<h2>Error: No se encontró index.html en el servidor.</h2>")

# Endpoint para subir imágenes directamente a Cloudinary (Protegido Admin)
@app.post("/api/upload")
async def subir_imagen(file: UploadFile = File(...), admin: models.Usuario = Depends(verificar_admin)):
    try:
        respuesta = cloudinary.uploader.upload(file.file, folder="brindes_mkt")
        return {"imagen_url": respuesta.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")

# --- USUARIOS Y LOGIN CON JWT ---

@app.post("/api/registro", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado.")
    
    nuevo_usuario = models.Usuario(
        nombre=usuario.nombre,
        email=usuario.email,
        password=obtener_password_hash(usuario.password),
        rol="OPERADOR"
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

@app.post("/api/login")
def login_usuario(creds: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == creds.email).first()
    if not usuario or not verificar_password(creds.password, usuario.password):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    
    access_token = crear_token_acceso(data={"sub": usuario.email, "rol": usuario.rol})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "email": usuario.email,
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

@app.put("/api/productos/{producto_id}", response_model=schemas.ProductoOut)
def editar_producto(producto_id: int, datos: schemas.ProductoUpdate, db: Session = Depends(get_db), admin: models.Usuario = Depends(verificar_admin)):
    prod = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    
    prod.sku = datos.sku
    prod.nombre = datos.nombre
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
    movimientos = db.query(models.MovimientoInventario).order_by(models.MovimientoInventario.fecha.desc()).limit(50).all()
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
    
    if datos.usuario: mov.usuario = datos.usuario
    if datos.notas is not None: mov.notas = datos.notas
    if datos.cantidad is not None and datos.cantidad != mov.cantidad:
        diff = datos.cantidad - mov.cantidad
        prod = db.query(models.Producto).filter(models.Producto.id == mov.producto_id).first()
        if prod:
            if mov.tipo == "ENTRADA": prod.stock_actual += diff
            elif mov.tipo == "SALIDA": prod.stock_actual -= diff
        mov.cantidad = datos.cantidad
        
    db.commit()
    return {"mensaje": "Movimiento actualizado con éxito"}

# --- EXPORTAR EXCEL ---

@app.get("/api/reportes/excel")
def descargar_reporte_excel(db: Session = Depends(get_db), usuario: models.Usuario = Depends(obtener_usuario_actual)):
    productos = db.query(models.Producto).all()
    
    data = []
    for p in productos:
        data.append({
            "Código / SKU": p.sku,
            "Producto": p.nombre,
            "Stock Actual": p.stock_actual,
            "Stock Mínimo": p.stock_minimo,
            "Estado Stock": "ALERTA - BAJO" if p.stock_actual <= p.stock_minimo else "NORMAL",
            "URL Imagen": p.imagen_url or "Sin foto"
        })
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Brindes')
    output.seek(0)
    
    headers = {'Content-Disposition': 'attachment; filename="Inventario_Brindes_MKT.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
