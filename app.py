
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
import secrets
import sqlite3
import io
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
from functools import wraps
from hmac import compare_digest
from urllib.parse import urlsplit
from uuid import uuid4
from pymongo import MongoClient, ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def obtener_clave_secreta():
    clave_configurada = (
        os.environ.get('TORRAM_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
    )
    if clave_configurada:
        return clave_configurada
    os.makedirs(app.instance_path, exist_ok=True)
    ruta_clave = os.path.join(app.instance_path, 'secret_key')
    try:
        with open(ruta_clave, 'x', encoding='utf-8') as archivo:
            clave = secrets.token_hex(32)
            archivo.write(clave)
            return clave
    except FileExistsError:
        with open(ruta_clave, 'r', encoding='utf-8') as archivo:
            clave = archivo.read().strip()
        if not clave:
            raise RuntimeError(f'La clave de sesión está vacía: {ruta_clave}')
        return clave


app.secret_key = obtener_clave_secreta()

# MongoDB: usa Atlas en producción y MongoDB local como respaldo.
NOMBRE_BASE_MONGO = os.environ.get('TORRAM_MONGO_DB', 'torram_system').strip() or 'torram_system'
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://127.0.0.1:27017/').strip()
cliente_mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
base_datos = cliente_mongo[NOMBRE_BASE_MONGO]
usuarios = base_datos['usuarios']
pedidos = base_datos['pedidos']
productos = base_datos['productos']
reservas = base_datos['reservas']
ARCHIVO_USUARIOS_ANTERIOR = os.path.join(app.instance_path, 'users.json')
ARCHIVO_BASE_LOCAL = os.path.join(app.instance_path, 'torram.sqlite3')
ADMIN_EMAIL = (
    os.environ.get('TORRAM_ADMIN_EMAIL', '').strip().lower()
    or 'floresmorenoemiliano.cbtis272@gmail.com'
)
ADMIN_PASSWORD = os.environ.get('TORRAM_ADMIN_PASSWORD', '')
ESTADOS_PEDIDO = ['Pendiente', 'Preparando', 'En camino', 'Entregado', 'Cancelado']
DURACION_RESERVA_MINUTOS = 5
usar_mongo = False

PRODUCTS = [
    {"id": 1, "name": "iPhone 15 Pro Max Titan", "category": "telefonos", "price": 28499, "old_price": 32999, "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?q=80&w=800", "badge": "HOT", "desc": "Chip A17 Pro, 256GB, Titanio aeroespacial, camara 120mm.", "specs": ["A17 Pro", "256GB", "120Hz ProMotion"]},
    {"id": 2, "name": "Samsung Galaxy S24 Ultra", "category": "telefonos", "price": 25999, "old_price": 28999, "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?q=80&w=800", "badge": "NEW", "desc": "Snapdragon 8 Gen 3, S-Pen, 200MP, IA integrada.", "specs": ["200MP", "S-Pen", "Titanium"]},
    {"id": 3, "name": "iPad Pro M4 13''", "category": "tablets", "price": 32499, "old_price": 0, "image": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?q=80&w=800", "badge": "PRO", "desc": "Chip M4, OLED Ultra Retina XDR, el mas delgado.", "specs": ["M4 Chip", "OLED", "12.9h bateria"]},
    {"id": 4, "name": "Galaxy Tab S9 Ultra", "category": "tablets", "price": 21999, "old_price": 24999, "image": "https://images.unsplash.com/photo-1585791487250-23a51e8b48bf?q=80&w=800", "badge": "", "desc": "14.6'' Dynamic AMOLED 2X, S Pen incluido.", "specs": ["14.6''", "S Pen", "IP68"]},
    {"id": 5, "name": "MacBook Pro 16'' M3 Max", "category": "laptops", "price": 68999, "old_price": 74999, "image": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?q=80&w=800", "badge": "BEAST", "desc": "M3 Max 16-core, 48GB RAM, 1TB SSD. Para dioses.", "specs": ["M3 Max", "48GB RAM", "22h bateria"]},
    {"id": 6, "name": "ASUS ROG Zephyrus G14", "category": "laptops", "price": 38999, "old_price": 42999, "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?q=80&w=800", "badge": "GAMER", "desc": "Ryzen 9, RTX 4070, OLED 3K 120Hz.", "specs": ["RTX 4070", "OLED 120Hz", "1.65kg"]},
    {"id": 7, "name": "PC TorRam Nebula - RTX 4090", "category": "computadoras", "price": 79999, "old_price": 89999, "image": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?q=80&w=800", "badge": "CUSTOM", "desc": "i9-14900K, RTX 4090 24GB, 64GB DDR5, Custom Liquid.", "specs": ["RTX 4090", "64GB DDR5", "Liquid Cooling"]},
    {"id": 8, "name": "Mac Studio M2 Ultra", "category": "computadoras", "price": 94999, "old_price": 0, "image": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?q=80&w=800", "badge": "STUDIO", "desc": "La workstation definitiva de Apple.", "specs": ["M2 Ultra", "128GB RAM", "800GB/s"]},
    {"id": 9, "name": "RTX 4080 SUPER Founders", "category": "hardware", "price": 26499, "old_price": 28999, "image": "https://images.unsplash.com/photo-1591488320449-011701bb6704?q=80&w=800", "badge": "STOCK", "desc": "DLSS 3.5, 16GB GDDR6X, Ray Tracing extremo.", "specs": ["16GB GDDR6X", "DLSS 3", "AV1"]},
    {"id": 10, "name": "AMD Ryzen 9 7950X3D", "category": "hardware", "price": 12999, "old_price": 14499, "image": "https://images.unsplash.com/photo-1555617117-241da08dc2fd?q=80&w=800", "badge": "TOP", "desc": "16 nucleos, 3D V-Cache, rey del gaming.", "specs": ["16C/32T", "3D V-Cache", "5.7GHz"]},
    {"id": 11, "name": "Licencia Windows 11 Pro + Office", "category": "software", "price": 2499, "old_price": 4999, "image": "https://images.unsplash.com/photo-1629654297299-c8506221ca97?q=80&w=800", "badge": "KEY", "desc": "Activacion instantanea, lifetime, factura incluida.", "specs": ["Digital", "Lifetime", "Instant"]},
    {"id": 12, "name": "Adobe Creative Cloud 1 Ano", "category": "software", "price": 6999, "old_price": 8999, "image": "https://images.unsplash.com/photo-1611224923853-80b023f02d71?q=80&w=800", "badge": "CREATOR", "desc": "Toda la suite: PS, PR, AI, AE y 20+ apps.", "specs": ["20+ Apps", "100GB Cloud", "Fonts"]},
    {"id": 13, "name": "Funda TorRam Carbon - iPhone", "category": "cosmeticos", "price": 899, "old_price": 1299, "image": "https://images.unsplash.com/photo-1605236453806-6ff36851218e?q=80&w=800", "badge": "DROP TEST", "desc": "Kevlar real + MagSafe, 5m drop protection.", "specs": ["Kevlar", "MagSafe", "5m Drop"]},
    {"id": 14, "name": "Cargador TorRam GaN 120W Cube", "category": "cosmeticos", "price": 1299, "old_price": 1899, "image": "https://images.unsplash.com/photo-1583394838336-acd977736f90?q=80&w=800", "badge": "GaN", "desc": "3 puertos, carga laptop + 2 telefonos, mini tamano.", "specs": ["120W GaN", "3 Puertos", "USB-C PD"]},
    {"id": 15, "name": "AirPods Max TorRam Edition", "category": "cosmeticos", "price": 12499, "old_price": 13999, "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?q=80&w=800", "badge": "ANC", "desc": "Edicion anodizada negra mate, audio espacial.", "specs": ["ANC", "40h", "Spatial"]},
    {"id": 16, "name": "Stand Aluminio TorRam Float", "category": "cosmeticos", "price": 1599, "old_price": 0, "image": "https://images.unsplash.com/photo-1525598912003-663126343e1f?q=80&w=800", "badge": "MINIMAL", "desc": "Aluminio CNC, compatible MacBook/iPad.", "specs": ["Aluminio CNC", "Plegable", "360"]},
]

def preparar_base_datos():
    """Usa MongoDB si está disponible y SQLite local como alternativa."""
    global usar_mongo
    usar_mongo = False
    try:
        cliente_mongo.admin.command('ping')
        usuarios.create_index([('correo', ASCENDING)], unique=True)
        pedidos.create_index([('fecha', ASCENDING)])
        productos.create_index([('id', ASCENDING)], unique=True)
        reservas.create_index([('reserva_id', ASCENDING)], unique=True)
        reservas.create_index(
            [('visitante_id', ASCENDING)],
            unique=True,
            partialFilterExpression={'estado': 'activa'}
        )
        usar_mongo = True
        print(f'MongoDB conectado: usando la base de datos {NOMBRE_BASE_MONGO}.')
    except Exception as error:
        print(f'No se pudo conectar a MongoDB ({error}). Se usara SQLite local.')
        os.makedirs(app.instance_path, exist_ok=True)
        with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
            conexion.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    correo TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    contrasena_hash TEXT NOT NULL,
                    creado_en TEXT NOT NULL
                )
            ''')
            conexion.execute('''
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    datos TEXT NOT NULL
                )
            ''')
            conexion.execute('''
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY,
                    datos TEXT NOT NULL
                )
            ''')
            conexion.execute('''
                CREATE TABLE IF NOT EXISTS reservas (
                    reserva_id TEXT PRIMARY KEY,
                    visitante_id TEXT NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL,
                    estado TEXT NOT NULL,
                    creado_en TEXT NOT NULL,
                    vence_en TEXT NOT NULL,
                    datos TEXT NOT NULL
                )
            ''')
            conexion.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_reservas_visitante_activa "
                "ON reservas (visitante_id) WHERE estado = 'activa'"
            )
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    sembrar_productos()
    migrar_stock_productos()
    migrar_usuarios_anteriores()

def sembrar_productos():
    for producto in PRODUCTS:
        producto_con_stock = {**producto, 'stock': 10, 'reservados': 0}
        if usar_mongo:
            productos.update_one(
                {'id': producto['id']},
                {'$setOnInsert': producto_con_stock},
                upsert=True
            )
        else:
            with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
                conexion.execute(
                    'INSERT OR IGNORE INTO productos (id, datos) VALUES (?, ?)',
                    (producto['id'], json.dumps(producto_con_stock))
                )

def migrar_stock_productos():
    """Agrega inventario y campos de reservas a productos anteriores."""
    if usar_mongo:
        productos.update_many(
            {'stock': {'$exists': False}},
            {'$set': {'stock': 10}}
        )
        productos.update_many(
            {'reservados': {'$exists': False}},
            {'$set': {'reservados': 0}}
        )
        productos.update_many(
            {'upcoming': {'$exists': True}},
            {'$unset': {'upcoming': ''}}
        )
        productos.update_many(
            {'category': 'juegos'},
            {'$set': {'category': 'otros'}}
        )
        return

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        filas = conexion.execute('SELECT id, datos FROM productos').fetchall()
        for producto_id, datos in filas:
            producto = json.loads(datos)
            actualizado = False
            for campo, valor in (('stock', 10), ('reservados', 0)):
                if campo not in producto:
                    producto[campo] = valor
                    actualizado = True
            if 'upcoming' in producto:
                producto.pop('upcoming')
                actualizado = True
            if producto.get('category') == 'juegos':
                producto['category'] = 'otros'
                actualizado = True
            if actualizado:
                conexion.execute(
                    'UPDATE productos SET datos = ? WHERE id = ?',
                    (json.dumps(producto), producto_id)
                )


def ahora_utc():
    return datetime.now(timezone.utc)


def normalizar_fecha(fecha):
    if isinstance(fecha, str):
        fecha = datetime.fromisoformat(fecha)
    return fecha.replace(tzinfo=timezone.utc) if fecha.tzinfo is None else fecha


def normalizar_reserva(reserva):
    if not reserva:
        return None
    reserva.pop('_id', None)
    reserva['creado_en'] = normalizar_fecha(reserva['creado_en'])
    reserva['vence_en'] = normalizar_fecha(reserva['vence_en'])
    return reserva


def liberar_reservas_vencidas(producto_id=None):
    ahora = ahora_utc()
    if usar_mongo:
        consulta = {'estado': 'activa', 'vence_en': {'$lte': ahora}}
        if producto_id is not None:
            consulta['producto_id'] = producto_id
        for reserva in reservas.find(consulta):
            resultado = reservas.update_one(
                {'reserva_id': reserva['reserva_id'], 'estado': 'activa', 'vence_en': {'$lte': ahora}},
                {'$set': {'estado': 'vencida'}}
            )
            if resultado.modified_count:
                productos.update_one(
                    {'id': reserva['producto_id'], 'reservados': {'$gte': reserva['cantidad']}},
                    {'$inc': {'reservados': -reserva['cantidad']}}
                )
        return

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        consulta = "SELECT reserva_id, producto_id, cantidad, datos FROM reservas WHERE estado = 'activa' AND vence_en <= ?"
        parametros = [ahora.isoformat()]
        if producto_id is not None:
            consulta += ' AND producto_id = ?'
            parametros.append(producto_id)
        expiradas = conexion.execute(consulta, parametros).fetchall()
        for reserva_id, id_producto, cantidad, datos in expiradas:
            actualizacion = conexion.execute(
                "UPDATE reservas SET estado = 'vencida' WHERE reserva_id = ? AND estado = 'activa'",
                (reserva_id,)
            )
            if actualizacion.rowcount:
                fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (id_producto,)).fetchone()
                if fila:
                    producto = json.loads(fila[0])
                    producto['reservados'] = max(0, producto.get('reservados', 0) - cantidad)
                    conexion.execute(
                        'UPDATE productos SET datos = ? WHERE id = ?',
                        (json.dumps(producto), id_producto)
                    )
                reserva = json.loads(datos)
                reserva['estado'] = 'vencida'
                conexion.execute(
                    'UPDATE reservas SET datos = ? WHERE reserva_id = ?',
                    (json.dumps(reserva), reserva_id)
                )
        conexion.commit()


def obtener_reserva(reserva_id):
    if usar_mongo:
        return normalizar_reserva(reservas.find_one({'reserva_id': reserva_id}))
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        fila = conexion.execute('SELECT datos FROM reservas WHERE reserva_id = ?', (reserva_id,)).fetchone()
    return normalizar_reserva(json.loads(fila[0]) if fila else None)


def obtener_reserva_activa(visitante_id):
    liberar_reservas_vencidas()
    ahora = ahora_utc()
    if usar_mongo:
        reserva = reservas.find_one(
            {'visitante_id': visitante_id, 'estado': 'activa', 'vence_en': {'$gt': ahora}}
        )
        return normalizar_reserva(reserva)
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        fila = conexion.execute(
            "SELECT datos FROM reservas WHERE visitante_id = ? AND estado = 'activa' AND vence_en > ?",
            (visitante_id, ahora.isoformat())
        ).fetchone()
    return normalizar_reserva(json.loads(fila[0]) if fila else None)


def crear_reserva_temporal(producto_id, visitante_id):
    liberar_reservas_vencidas(producto_id)
    ahora = ahora_utc()
    reserva = {
        'reserva_id': uuid4().hex,
        'visitante_id': visitante_id,
        'producto_id': producto_id,
        'cantidad': 1,
        'estado': 'activa',
        'creado_en': ahora,
        'vence_en': ahora + timedelta(minutes=DURACION_RESERVA_MINUTOS)
    }
    if usar_mongo:
        producto_actualizado = productos.find_one_and_update(
            {
                'id': producto_id,
                '$expr': {'$gt': ['$stock', {'$ifNull': ['$reservados', 0]}]}
            },
            {'$inc': {'reservados': 1}},
            return_document=ReturnDocument.AFTER
        )
        if not producto_actualizado:
            return None
        try:
            reservas.insert_one(reserva)
        except DuplicateKeyError:
            productos.update_one({'id': producto_id}, {'$inc': {'reservados': -1}})
            return None
        except Exception:
            productos.update_one({'id': producto_id}, {'$inc': {'reservados': -1}})
            raise
        return reserva

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (producto_id,)).fetchone()
        if not fila:
            conexion.rollback()
            return None
        producto = json.loads(fila[0])
        if producto.get('stock', 0) <= producto.get('reservados', 0):
            conexion.rollback()
            return None
        producto['reservados'] = producto.get('reservados', 0) + 1
        conexion.execute(
            'UPDATE productos SET datos = ? WHERE id = ?',
            (json.dumps(producto), producto_id)
        )
        datos_reserva = json.dumps(reserva, default=lambda valor: valor.isoformat() if isinstance(valor, datetime) else str(valor))
        conexion.execute(
            'INSERT INTO reservas (reserva_id, visitante_id, producto_id, cantidad, estado, creado_en, vence_en, datos) '
            'VALUES (?, ?, ?, 1, ?, ?, ?, ?)',
            (reserva['reserva_id'], visitante_id, producto_id, 'activa', ahora.isoformat(), reserva['vence_en'].isoformat(), datos_reserva)
        )
        conexion.commit()
    return reserva


def cancelar_reserva_temporal(reserva_id, visitante_id):
    ahora = ahora_utc()
    if usar_mongo:
        reserva = reservas.find_one_and_update(
            {
                'reserva_id': reserva_id,
                'visitante_id': visitante_id,
                'estado': 'activa',
                'vence_en': {'$gt': ahora}
            },
            {'$set': {'estado': 'cancelada'}},
            return_document=ReturnDocument.BEFORE
        )
        if not reserva:
            return False
        productos.update_one(
            {'id': reserva['producto_id'], 'reservados': {'$gte': reserva['cantidad']}},
            {'$inc': {'reservados': -reserva['cantidad']}}
        )
        return True

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        fila = conexion.execute(
            "SELECT producto_id, cantidad, datos FROM reservas WHERE reserva_id = ? AND visitante_id = ? AND estado = 'activa' AND vence_en > ?",
            (reserva_id, visitante_id, ahora.isoformat())
        ).fetchone()
        if not fila:
            conexion.rollback()
            return False
        id_producto, cantidad, datos = fila
        producto_fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (id_producto,)).fetchone()
        if producto_fila:
            producto = json.loads(producto_fila[0])
            producto['reservados'] = max(0, producto.get('reservados', 0) - cantidad)
            conexion.execute('UPDATE productos SET datos = ? WHERE id = ?', (json.dumps(producto), id_producto))
        reserva = json.loads(datos)
        reserva['estado'] = 'cancelada'
        conexion.execute(
            "UPDATE reservas SET estado = 'cancelada', datos = ? WHERE reserva_id = ?",
            (json.dumps(reserva), reserva_id)
        )
        conexion.commit()
    return True


def confirmar_reserva_temporal(reserva_id, visitante_id):
    ahora = ahora_utc()
    if usar_mongo:
        reserva = reservas.find_one_and_update(
            {
                'reserva_id': reserva_id,
                'visitante_id': visitante_id,
                'estado': 'activa',
                'vence_en': {'$gt': ahora}
            },
            {'$set': {'estado': 'confirmando'}},
            return_document=ReturnDocument.BEFORE
        )
        if not reserva:
            return False
        producto_actualizado = productos.update_one(
            {
                'id': reserva['producto_id'],
                'stock': {'$gte': reserva['cantidad']},
                'reservados': {'$gte': reserva['cantidad']}
            },
            {'$inc': {'stock': -reserva['cantidad'], 'reservados': -reserva['cantidad']}}
        )
        if not producto_actualizado.modified_count:
            reservas.update_one(
                {'reserva_id': reserva_id, 'estado': 'confirmando'},
                {'$set': {'estado': 'activa'}}
            )
            return False
        reservas.update_one(
            {'reserva_id': reserva_id, 'estado': 'confirmando'},
            {'$set': {'estado': 'confirmada', 'confirmado_en': ahora}}
        )
        return True

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        fila = conexion.execute(
            "SELECT producto_id, cantidad, datos FROM reservas WHERE reserva_id = ? AND visitante_id = ? AND estado = 'activa' AND vence_en > ?",
            (reserva_id, visitante_id, ahora.isoformat())
        ).fetchone()
        if not fila:
            conexion.rollback()
            return False
        id_producto, cantidad, datos = fila
        producto_fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (id_producto,)).fetchone()
        if not producto_fila:
            conexion.rollback()
            return False
        producto = json.loads(producto_fila[0])
        if producto.get('stock', 0) < cantidad or producto.get('reservados', 0) < cantidad:
            conexion.rollback()
            return False
        producto['stock'] -= cantidad
        producto['reservados'] -= cantidad
        conexion.execute('UPDATE productos SET datos = ? WHERE id = ?', (json.dumps(producto), id_producto))
        reserva = json.loads(datos)
        reserva['estado'] = 'confirmada'
        reserva['confirmado_en'] = ahora.isoformat()
        conexion.execute(
            "UPDATE reservas SET estado = 'confirmada', datos = ? WHERE reserva_id = ?",
            (json.dumps(reserva), reserva_id)
        )
        conexion.commit()
    return True


def obtener_productos():
    liberar_reservas_vencidas()
    if usar_mongo:
        lista_productos = [
            {key: value for key, value in producto.items() if key != '_id'}
            for producto in productos.find().sort('id', ASCENDING)
        ]
    else:
        with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
            filas = conexion.execute('SELECT datos FROM productos ORDER BY id').fetchall()
        lista_productos = [json.loads(fila[0]) for fila in filas]
    for producto in lista_productos:
        producto['stock_disponible'] = max(0, producto.get('stock', 0) - producto.get('reservados', 0))
    return lista_productos


def obtener_producto(pid):
    liberar_reservas_vencidas(pid)
    if usar_mongo:
        producto = productos.find_one({'id': pid})
        if producto:
            producto.pop('_id', None)
    else:
        with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
            fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (pid,)).fetchone()
        producto = json.loads(fila[0]) if fila else None
    if producto:
        producto['stock_disponible'] = max(0, producto.get('stock', 0) - producto.get('reservados', 0))
    return producto


def guardar_producto(producto):
    if usar_mongo:
        producto_actualizado = {key: value for key, value in producto.items() if key != 'reservados'}
        resultado = productos.update_one(
            {
                'id': producto['id'],
                '$expr': {'$lte': [{'$ifNull': ['$reservados', 0]}, producto['stock']]}
            },
            {'$set': producto_actualizado}
        )
        if resultado.matched_count:
            return True
        if productos.find_one({'id': producto['id']}):
            return False
        producto['reservados'] = 0
        productos.insert_one(producto)
        return True

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        fila = conexion.execute('SELECT datos FROM productos WHERE id = ?', (producto['id'],)).fetchone()
        if fila:
            producto_actual = json.loads(fila[0])
            producto['reservados'] = producto_actual.get('reservados', 0)
            if producto['stock'] < producto['reservados']:
                conexion.rollback()
                return False
        else:
            producto['reservados'] = 0
        conexion.execute(
            'INSERT INTO productos (id, datos) VALUES (?, ?) '
            'ON CONFLICT(id) DO UPDATE SET datos = excluded.datos',
            (producto['id'], json.dumps(producto))
        )
        conexion.commit()
    return True


def siguiente_id_producto():
    if usar_mongo:
        ultimo = productos.find_one(sort=[('id', -1)])
        return (ultimo['id'] if ultimo else 0) + 1
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        return conexion.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM productos').fetchone()[0]


def buscar_usuario(correo):
    if usar_mongo:
        return usuarios.find_one({'correo': correo})
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        conexion.row_factory = sqlite3.Row
        fila = conexion.execute(
            'SELECT correo, nombre, contrasena_hash FROM usuarios WHERE correo = ?',
            (correo,)
        ).fetchone()
    return dict(fila) if fila else None


def guardar_usuario(usuario, ignorar_existente=False):
    if usar_mongo:
        if ignorar_existente:
            usuarios.update_one(
                {'correo': usuario['correo']},
                {'$setOnInsert': usuario},
                upsert=True
            )
            return True
        usuarios.insert_one(usuario)
        return True

    comando = 'INSERT OR IGNORE' if ignorar_existente else 'INSERT'
    try:
        with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
            conexion.execute(
                f'{comando} INTO usuarios (correo, nombre, contrasena_hash, creado_en) VALUES (?, ?, ?, ?)',
                (
                    usuario['correo'],
                    usuario['nombre'],
                    usuario['contrasena_hash'],
                    str(usuario['creado_en'])
                )
            )
            return conexion.execute('SELECT changes()').fetchone()[0] == 1
    except sqlite3.IntegrityError:
        return False


def guardar_pedido(pedido):
    if usar_mongo:
        pedidos.insert_one(pedido)
        return
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        conexion.execute(
            'INSERT INTO pedidos (fecha, datos) VALUES (?, ?)',
            (
                pedido['fecha'].isoformat(),
                json.dumps(pedido, default=lambda valor: valor.isoformat() if isinstance(valor, datetime) else str(valor))
            )
        )

def reservar_stock(articulos):
    """Descuenta las cantidades del carrito sin permitir inventario negativo."""
    if usar_mongo:
        reservados = []
        for articulo in articulos:
            producto_id = articulo['producto']['id']
            cantidad = articulo['cantidad']
            producto_actualizado = productos.find_one_and_update(
                {
                    'id': producto_id,
                    '$expr': {
                        '$gte': [
                            {'$subtract': ['$stock', {'$ifNull': ['$reservados', 0]}]},
                            cantidad
                        ]
                    }
                },
                {'$inc': {'stock': -cantidad}},
                return_document=ReturnDocument.AFTER
            )
            if not producto_actualizado:
                for id_reservado, cantidad_reservada in reversed(reservados):
                    productos.update_one(
                        {'id': id_reservado},
                        {'$inc': {'stock': cantidad_reservada}}
                    )
                return False
            reservados.append((producto_id, cantidad))
        return True

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        for articulo in articulos:
            producto_id = articulo['producto']['id']
            cantidad = articulo['cantidad']
            fila = conexion.execute(
                'SELECT datos FROM productos WHERE id = ?',
                (producto_id,)
            ).fetchone()
            if not fila:
                conexion.rollback()
                return False
            producto = json.loads(fila[0])
            if producto.get('stock', 0) - producto.get('reservados', 0) < cantidad:
                conexion.rollback()
                return False
            producto['stock'] -= cantidad
            conexion.execute(
                'UPDATE productos SET datos = ? WHERE id = ?',
                (json.dumps(producto), producto_id)
            )
        conexion.commit()
    return True

def devolver_stock(articulos):
    """Restaura una reserva si no se pudo guardar el pedido."""
    if usar_mongo:
        for articulo in articulos:
            productos.update_one(
                {'id': articulo['producto']['id']},
                {'$inc': {'stock': articulo['cantidad']}}
            )
        return

    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL, timeout=10)) as conexion, conexion:
        for articulo in articulos:
            producto_id = articulo['producto']['id']
            fila = conexion.execute(
                'SELECT datos FROM productos WHERE id = ?',
                (producto_id,)
            ).fetchone()
            if fila:
                producto = json.loads(fila[0])
                producto['stock'] = producto.get('stock', 0) + articulo['cantidad']
                conexion.execute(
                    'UPDATE productos SET datos = ? WHERE id = ?',
                    (json.dumps(producto), producto_id)
                )


def obtener_pedidos(correo=None):
    if usar_mongo:
        consulta = {'usuario.correo': correo} if correo else {}
        documentos = list(pedidos.find(consulta).sort('fecha', -1))
        for pedido in documentos:
            if not pedido.get('folio'):
                pedido['folio'] = f"TR-LEG-{str(pedido['_id'])[-10:].upper()}"
                pedidos.update_one({'_id': pedido['_id']}, {'$set': {'folio': pedido['folio']}})
            pedido.pop('_id', None)
    else:
        with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
            filas = conexion.execute('SELECT id, datos FROM pedidos ORDER BY fecha DESC').fetchall()
        documentos = []
        for pedido_id, datos in filas:
            pedido = json.loads(datos)
            pedido.setdefault('folio', f'TR-LEG-{pedido_id:06d}')
            documentos.append(pedido)
        if correo:
            documentos = [
                pedido for pedido in documentos
                if pedido.get('usuario', {}).get('correo') == correo
            ]
    for pedido in documentos:
        if isinstance(pedido.get('fecha'), str):
            pedido['fecha'] = datetime.fromisoformat(pedido['fecha'])
        pedido.setdefault('estado', 'Pendiente')
        pedido.setdefault('folio', f"TR-{pedido['fecha'].strftime('%Y%m%d')}-{pedido.get('total', 0)}")
    return documentos


def actualizar_estado_pedido(folio, estado):
    if usar_mongo:
        resultado = pedidos.update_one({'folio': folio}, {'$set': {'estado': estado}})
        if resultado.matched_count:
            return True
        if folio.startswith('TR-LEG-'):
            for pedido in pedidos.find({'folio': {'$exists': False}}, {'_id': 1}):
                if f"TR-LEG-{str(pedido['_id'])[-10:].upper()}" == folio:
                    pedidos.update_one(
                        {'_id': pedido['_id']},
                        {'$set': {'folio': folio, 'estado': estado}}
                    )
                    return True
        return False
    with closing(sqlite3.connect(ARCHIVO_BASE_LOCAL)) as conexion, conexion:
        filas = conexion.execute('SELECT id, datos FROM pedidos').fetchall()
        for pedido_id, datos in filas:
            pedido = json.loads(datos)
            if pedido.get('folio', f'TR-LEG-{pedido_id:06d}') == folio:
                pedido['folio'] = folio
                pedido['estado'] = estado
                conexion.execute(
                    'UPDATE pedidos SET datos = ? WHERE id = ?',
                    (json.dumps(pedido), pedido_id)
                )
                return True
    return False


def migrar_usuarios_anteriores():
    """Conserva los usuarios existentes de la versión que usaba JSON."""
    if not os.path.exists(ARCHIVO_USUARIOS_ANTERIOR):
        return
    try:
        with open(ARCHIVO_USUARIOS_ANTERIOR, 'r', encoding='utf-8') as archivo:
            usuarios_anteriores = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return

    for correo, datos in usuarios_anteriores.items():
        correo_normalizado = correo.lower().strip()
        guardar_usuario({
            'nombre': datos.get('name', ''),
            'correo': correo_normalizado,
            'contrasena_hash': generate_password_hash(datos.get('password', '')),
            'creado_en': datos.get('created', datetime.now())
        }, ignorar_existente=True)


def obtener_articulos_carrito():
    """Construye los productos y el total del carrito actual."""
    carrito = session.get('cart', {})
    articulos = []
    total = 0
    for id_producto, cantidad in carrito.items():
        producto = obtener_producto(int(id_producto))
        if producto:
            subtotal = producto['price'] * cantidad
            total += subtotal
            articulos.append({'producto': producto, 'cantidad': cantidad, 'subtotal': subtotal})
    return articulos, total

def carrito_disponible(articulos):
    carrito = session.get('cart', {})
    return (
        len(articulos) == len(carrito)
        and all(
            articulo['cantidad'] <= articulo['producto'].get('stock_disponible', 0)
            for articulo in articulos
        )
    )

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash('Inicia sesion para continuar, crack.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            flash('Inicia sesión para continuar.', 'warning')
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    cart = session.get('cart', {})
    cart_count = sum(cart.values())
    return dict(
        cart_count=cart_count,
        reservation_id=session.get('reservation_id'),
        current_user=session.get('user'),
        is_admin=session.get('is_admin', False),
        csrf_token=session.setdefault('_csrf_token', secrets.token_urlsafe(32))
    )


@app.before_request
def proteger_acciones_admin():
    if request.method == 'POST' and request.endpoint in (
        'admin_save_product', 'admin_update_order', 'reserve_product',
        'cancel_reservation', 'confirm_reservation'
    ):
        token = request.form.get('_csrf_token', '')
        if not compare_digest(token, session.get('_csrf_token', '')):
            abort(400)


@app.route('/')
def index():
    products = obtener_productos()
    featured = [p for p in products if p.get('badge') in ['HOT','BEAST','CUSTOM','NEW']][:4]
    return render_template('index.html', products=products[:8], featured=featured)

@app.route('/shop')
def shop():
    category = request.args.get('cat', 'all')
    q = request.args.get('q', '').lower()
    products = obtener_productos()
    filtered = products
    if category != 'all':
        filtered = [p for p in filtered if p['category'] == category]
    if q:
        filtered = [p for p in filtered if q in p['name'].lower() or q in p['desc'].lower()]
    return render_template('shop.html', products=filtered, active_cat=category, query=q)

@app.route('/product/<int:pid>')
def product_detail(pid):
    product = obtener_producto(pid)
    if not product:
        return "Producto no encontrado", 404
    related = [
        p for p in obtener_productos()
        if p['category'] == product['category'] and p['id'] != pid
    ][:4]
    return render_template('product.html', product=product, related=related)


def obtener_id_visitante_reserva():
    if 'reservation_visitor_id' not in session:
        session['reservation_visitor_id'] = uuid4().hex
    return session['reservation_visitor_id']


def obtener_url_publica(ruta):
    base_url = (
        os.environ.get('APP_BASE_URL')
        or os.environ.get('TORRAM_APP_BASE_URL')
        or request.host_url
    ).strip().rstrip('/')
    return f"{base_url}{ruta}"


def generar_qr_data_uri(url):
    imagen = qrcode.make(url)
    buffer = io.BytesIO()
    imagen.save(buffer, format='PNG')
    contenido = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{contenido}'


@app.route('/ficha/<int:pid>')
def public_product_detail(pid):
    liberar_reservas_vencidas(pid)
    producto = obtener_producto(pid)
    if not producto:
        return render_template('public_not_found.html',
                               mensaje='El producto solicitado no existe.'), 404
    return render_template('public_product.html', product=producto)


@app.route('/reserva/<reserva_id>')
def public_reservation_detail(reserva_id):
    liberar_reservas_vencidas()
    reserva = obtener_reserva(reserva_id)
    if not reserva:
        return render_template('public_not_found.html',
                               mensaje='La reserva o comprobante no existe.'), 404
    producto = obtener_producto(reserva['producto_id'])
    if not producto:
        return render_template('public_not_found.html',
                               mensaje='El producto de esta reserva no existe.'), 404
    segundos_restantes = 0
    if reserva['estado'] == 'activa':
        segundos_restantes = max(0, int((reserva['vence_en'] - ahora_utc()).total_seconds()))
    return render_template(
        'public_reservation.html',
        reservation=reserva,
        product=producto,
        remaining_seconds=segundos_restantes
    )


@app.route('/reservar/<int:pid>', methods=['POST'])
def reserve_product(pid):
    producto = obtener_producto(pid)
    if not producto:
        abort(404)

    visitante_id = obtener_id_visitante_reserva()
    reserva_activa = obtener_reserva_activa(visitante_id)
    if reserva_activa:
        session['reservation_id'] = reserva_activa['reserva_id']
        flash('Ya tienes una reserva temporal activa.', 'info')
        return redirect(url_for('reservation_view'))

    try:
        reserva = crear_reserva_temporal(pid, visitante_id)
    except sqlite3.IntegrityError:
        reserva = None
    if not reserva:
        flash('Ya no hay unidades disponibles para reservar.', 'warning')
        return redirect(url_for('product_detail', pid=pid))
    session['reservation_id'] = reserva['reserva_id']
    flash('Producto apartado durante 5 minutos.', 'success')
    return redirect(url_for('reservation_view'))


@app.route('/reserva')
def reservation_view():
    visitante_id = session.get('reservation_visitor_id')
    reserva_id = session.get('reservation_id')
    if not visitante_id or not reserva_id:
        return redirect(url_for('shop'))
    liberar_reservas_vencidas()
    reserva = obtener_reserva(reserva_id)
    if not reserva or reserva.get('visitante_id') != visitante_id:
        return redirect(url_for('shop'))
    producto = obtener_producto(reserva['producto_id'])
    segundos_restantes = max(0, int((reserva['vence_en'] - ahora_utc()).total_seconds()))
    ficha_url = obtener_url_publica(url_for('public_reservation_detail', reserva_id=reserva_id))
    qr_data_uri = generar_qr_data_uri(ficha_url)
    return render_template(
        'reservation.html',
        reservation=reserva,
        product=producto,
        remaining_seconds=segundos_restantes,
        qr_data_uri=qr_data_uri,
        ficha_url=ficha_url
    )


@app.route('/reserva/cancelar', methods=['POST'])
def cancel_reservation():
    visitante_id = session.get('reservation_visitor_id')
    reserva_id = session.get('reservation_id')
    if not visitante_id or not reserva_id:
        return redirect(url_for('shop'))
    if cancelar_reserva_temporal(reserva_id, visitante_id):
        flash('La reserva se canceló y la unidad volvió a estar disponible.', 'success')
    else:
        liberar_reservas_vencidas()
        flash('La reserva ya venció o no está activa.', 'warning')
    return redirect(url_for('reservation_view'))


@app.route('/reserva/confirmar', methods=['POST'])
def confirm_reservation():
    visitante_id = session.get('reservation_visitor_id')
    reserva_id = session.get('reservation_id')
    if not visitante_id or not reserva_id:
        return redirect(url_for('shop'))
    if confirmar_reserva_temporal(reserva_id, visitante_id):
        flash('Reserva confirmada. La unidad quedó apartada para ti.', 'success')
    else:
        liberar_reservas_vencidas()
        flash('La reserva venció o ya no se puede confirmar.', 'warning')
    return redirect(url_for('reservation_view'))

@app.route('/add_to_cart/<int:pid>', methods=['POST'])
def add_to_cart(pid):
    producto = obtener_producto(pid)
    if not producto:
        abort(404)
    try:
        qty = max(1, min(int(request.form.get('qty', 1)), 10))
    except ValueError:
        flash('La cantidad seleccionada no es válida.', 'warning')
        return redirect(url_for('product_detail', pid=pid))
    cart = session.get('cart', {})
    cantidad_actual = int(cart.get(str(pid), 0))
    stock = producto.get('stock_disponible', 0)
    if stock <= 0:
        flash('Este producto está agotado temporalmente.', 'warning')
        return redirect(request.referrer or url_for('shop'))
    if cantidad_actual + qty > stock:
        flash(f'Solo quedan {stock} unidades disponibles de este producto.', 'warning')
        return redirect(request.referrer or url_for('shop'))
    cart[str(pid)] = cantidad_actual + qty
    session['cart'] = cart
    flash('Agregado al carrito. Buena eleccion!', 'success')
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart')
def cart_view():
    articulos, total = obtener_articulos_carrito()
    items = [
        {'product': articulo['producto'], 'qty': articulo['cantidad'], 'subtotal': articulo['subtotal']}
        for articulo in articulos
    ]
    return render_template(
        'cart.html',
        items=items,
        total=total,
        can_checkout=carrito_disponible(articulos)
    )

@app.route('/remove/<int:pid>')
def remove_from_cart(pid):
    cart = session.get('cart', {})
    cart.pop(str(pid), None)
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    for pid_str in list(cart.keys()):
        new_qty = request.form.get(f'qty_{pid_str}')
        if new_qty:
            try:
                new_qty = int(new_qty)
            except ValueError:
                flash('Una de las cantidades no es válida.', 'warning')
                continue
            if new_qty <= 0:
                cart.pop(pid_str)
            else:
                producto = obtener_producto(int(pid_str))
                stock = producto.get('stock_disponible', 0) if producto else 0
                if stock <= 0:
                    cart.pop(pid_str)
                    flash('Se quitó del carrito un producto que se agotó.', 'warning')
                elif new_qty > stock:
                    cart[pid_str] = stock
                    flash(f'La cantidad se ajustó al stock disponible: {stock}.', 'warning')
                else:
                    cart[pid_str] = new_qty
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        correo = request.form['email'].lower().strip()
        contrasena = request.form['password']
        if (
            ADMIN_EMAIL and ADMIN_PASSWORD and correo == ADMIN_EMAIL
            and compare_digest(contrasena, ADMIN_PASSWORD)
        ):
            usuario = buscar_usuario(correo)
            session['user'] = {
                'email': correo,
                'name': usuario['nombre'] if usuario else 'Administrador'
            }
            session['is_admin'] = True
            flash('Sesión de administración iniciada.', 'success')
            return redirect(url_for('admin_panel'))
        usuario = buscar_usuario(correo)
        if usuario and check_password_hash(usuario['contrasena_hash'], contrasena):
            session['user'] = {'email': correo, 'name': usuario['nombre']}
            session['is_admin'] = correo == ADMIN_EMAIL
            if session['is_admin']:
                flash('Sesión de administración iniciada.', 'success')
                return redirect(url_for('admin_panel'))
            flash(f"Bienvenido de vuelta, {usuario['nombre']}!", 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas, bro.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['name'].strip()
        correo = request.form['email'].lower().strip()
        contrasena = request.form['password']
        if ADMIN_EMAIL and correo == ADMIN_EMAIL:
            flash('Ese email está reservado para administración.', 'danger')
            return render_template('register.html')
        usuario_nuevo = {
            'nombre': nombre,
            'correo': correo,
            'contrasena_hash': generate_password_hash(contrasena),
            'creado_en': datetime.now()
        }
        if not guardar_usuario(usuario_nuevo):
            flash('Ese email ya esta registrado.', 'danger')
        else:
            session['user'] = {'email': correo, 'name': nombre}
            flash('Cuenta creada. Bienvenido a TorRam System!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('is_admin', None)
    flash('Sesion cerrada. Nos vemos, leyenda.', 'info')
    return redirect(url_for('index'))

@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    if not session.get('cart', {}):
        return redirect(url_for('shop'))
    articulos, total = obtener_articulos_carrito()
    if not carrito_disponible(articulos):
        flash('Actualiza tu carrito: algún producto ya no tiene esa cantidad disponible.', 'warning')
        return redirect(url_for('cart_view'))
    items = [
        {'product': articulo['producto'], 'qty': articulo['cantidad'], 'subtotal': articulo['subtotal']}
        for articulo in articulos
    ]
    if request.method == 'POST':
        pedido = {
            'folio': f"TR-{uuid4().hex[:10].upper()}",
            'estado': 'Pendiente',
            'usuario': {'nombre': session['user']['name'], 'correo': session['user']['email']},
            'productos': articulos,
            'total': total,
            'direccion': {
                'calle': request.form['calle'],
                'ciudad': request.form['ciudad'],
                'cp': request.form['cp'],
                'estado': request.form['estado'],
                'telefono': request.form['telefono']
            },
            'metodo_pago': request.form['pago'],
            'fecha': datetime.now()
        }
        if not reservar_stock(articulos):
            flash('El stock cambió mientras terminabas la compra. Revisa las cantidades de tu carrito.', 'warning')
            return redirect(url_for('cart_view'))
        try:
            guardar_pedido(pedido)
        except Exception:
            devolver_stock(articulos)
            raise
        pedido.pop('_id', None)  # ObjectId no se puede guardar en la sesión de Flask.
        session['cart'] = {}
        session['last_order'] = pedido
        return redirect(url_for('success'))
    return render_template('checkout.html', items=items, total=total)

@app.route('/success')
@login_required
def success():
    order = session.get('last_order')
    if not order:
        return redirect(url_for('index'))
    return render_template('success.html', order=order)


@app.route('/mis-pedidos')
@login_required
def order_history():
    orders = obtener_pedidos(session['user']['email'])
    return render_template('orders.html', orders=orders)


@app.route('/admin')
@admin_required
def admin_panel():
    products = obtener_productos()
    orders = obtener_pedidos()
    return render_template(
        'admin.html',
        products=products,
        orders=orders,
        categories=['telefonos', 'tablets', 'laptops', 'computadoras', 'hardware', 'software', 'cosmeticos', 'otros'],
        states=ESTADOS_PEDIDO,
        total_stock=sum(product.get('stock', 0) for product in products),
        reserved_stock=sum(product.get('reservados', 0) for product in products)
    )


@app.route('/admin/productos', methods=['POST'])
@admin_required
def admin_save_product():
    product_id = request.form.get('id', '').strip()
    try:
        product_id = int(product_id) if product_id else siguiente_id_producto()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        price = int(request.form.get('price', ''))
        old_price = int(request.form.get('old_price', '0') or 0)
        stock = int(request.form.get('stock', ''))
        description = request.form.get('desc', '').strip()
        badge = request.form.get('badge', '').strip()
        categories = ['telefonos', 'tablets', 'laptops', 'computadoras', 'hardware', 'software', 'cosmeticos', 'otros']

        image_url = request.form.get('image', '').strip()
        archivo_imagen = request.files.get('image_file')
        image = image_url

        if archivo_imagen and archivo_imagen.filename:
            nombre_archivo = secure_filename(archivo_imagen.filename)
            if not nombre_archivo:
                raise ValueError
            extension = os.path.splitext(nombre_archivo)[1].lower().lstrip('.')
            if extension not in app.config['ALLOWED_IMAGE_EXTENSIONS']:
                raise ValueError
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            nombre_guardado = f'{uuid4().hex}.{extension}'
            ruta_guardada = os.path.join(app.config['UPLOAD_FOLDER'], nombre_guardado)
            archivo_imagen.save(ruta_guardada)
            image = url_for('static', filename=f'uploads/{nombre_guardado}', _external=False)
        elif image_url:
            image_url_parsed = urlsplit(image_url)
            if image_url_parsed.scheme not in ('http', 'https') or not image_url_parsed.netloc:
                raise ValueError
            image = image_url
        elif not image:
            raise ValueError

        if (
            not name or not description or price < 0 or old_price < 0 or stock < 0
            or category not in categories
        ):
            raise ValueError
    except ValueError:
        flash('Revisa los datos: nombre, descripción e imagen son obligatorios; precios y stock deben ser válidos.', 'danger')
        return redirect(url_for('admin_panel'))

    existing = obtener_producto(product_id)
    if request.form.get('id') and not existing:
        abort(404)
    reservados = existing.get('reservados', 0) if existing else 0
    if stock < reservados:
        flash(f'El stock no puede quedar por debajo de las {reservados} unidades reservadas.', 'danger')
        return redirect(url_for('admin_panel'))
    product = {
        'id': product_id,
        'name': name,
        'category': category,
        'price': price,
        'old_price': old_price,
        'stock': stock,
        'reservados': reservados,
        'image': image,
        'badge': badge,
        'desc': description,
        'specs': [spec.strip() for spec in request.form.get('specs', '').split(',') if spec.strip()]
    }
    if not guardar_producto(product):
        flash('El stock no puede quedar por debajo de las unidades reservadas.', 'danger')
        return redirect(url_for('admin_panel'))
    flash('Producto agregado.' if not existing else 'Producto actualizado.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/pedidos/<folio>/estado', methods=['POST'])
@admin_required
def admin_update_order(folio):
    estado = request.form.get('estado', '')
    if estado not in ESTADOS_PEDIDO:
        flash('El estado indicado no es válido.', 'danger')
    elif not actualizar_estado_pedido(folio, estado):
        abort(404)
    else:
        flash(f'Pedido {folio} actualizado: {estado}.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/api/cart_count')
def api_cart_count():
    cart = session.get('cart', {})
    return jsonify({'count': sum(cart.values())})

preparar_base_datos()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5000)
