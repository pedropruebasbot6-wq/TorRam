# TorRam System - Tienda Flask

Tienda de tecnología: teléfonos, tablets, computadoras, laptops, hardware, software y cosméticos (fundas, cargadores, stands, etc).

## Features
- Flask + Jinja
- Login / Registro persistentes en MongoDB (`usuarios`) o SQLite local
- Pedidos persistentes en MongoDB (`pedidos`) o SQLite local
- Panel de administración para catálogo y estado de pedidos
- Inventario por producto, visible para clientes y editable desde administración
- Agotamiento automático al vender la última unidad; los productos agotados no se pueden comprar hasta reponerlos
- Reservas temporales de productos con stock disponible: duran 5 minutos, se pueden confirmar o cancelar y bloquean unidades concurrentemente
- Historial de pedidos y seguimiento de envíos para clientes
- Carrito con session
- Checkout con dirección, forma de pago (tarjeta, PayPal, OXXO, SPEI)
- Diseño cyber-premium: Space Grotesk + JetBrains Mono, glassmorphism, neón
- 16 productos curados con categorías
- Ficha pública y comprobante con código QR

## Correr
```bash
pip install -r requirements.txt
# MongoDB es opcional; sin él se usa SQLite en instance/torram.sqlite3.
python app.py
```
Abre http://localhost:5000

## Variables de entorno
```bash
MONGO_URI=mongodb+srv://USUARIO:CONTRASENA@CLUSTER/...
TORRAM_MONGO_DB=torram_system
TORRAM_SECRET_KEY=frase_larga_privada
APP_BASE_URL=https://tu-servicio.onrender.com
```
`MONGO_URI` activa MongoDB Atlas. Sin esa variable se usa MongoDB local y, si no está disponible, SQLite local.

## Administración
La cuenta `floresmorenoemiliano.cbtis272@gmail.com` tiene acceso de administración de forma predeterminada: inicia sesión con la contraseña de esa cuenta ya registrada y se abrirá el panel. El registro público reserva esa dirección para evitar que otra persona cree una cuenta con ella. Puedes cambiar la dirección administradora con `TORRAM_ADMIN_EMAIL`.

También puedes habilitar el acceso administrativo independiente con `TORRAM_ADMIN_EMAIL` y `TORRAM_ADMIN_PASSWORD` como variables de entorno antes de iniciar la aplicación. En PowerShell, por ejemplo:
```powershell
$env:TORRAM_ADMIN_EMAIL = "admin@tudominio.com"
$env:TORRAM_ADMIN_PASSWORD = "una-clave-larga-y-unica"
python app.py
```
Inicia sesión con esos datos para abrir el enlace **ADMIN** en la barra superior. No publiques estas credenciales. Desde el panel puedes agregar y editar productos (incluida la URL de imagen y el stock), revisar existencias agrupadas por categoría y actualizar el estado de cada pedido. Cualquier producto con unidades libres se puede apartar durante 5 minutos; la disponibilidad se valida y bloquea en el servidor para evitar sobreventa. Las reservas canceladas o vencidas liberan su unidad; las confirmadas consumen inventario. Los productos iniciales reciben 10 unidades si todavía no tenían inventario; al llegar a cero se muestran agotados y se desactiva su compra o reserva hasta que se reponga el stock. En producción, configura también `TORRAM_SECRET_KEY` con un valor aleatorio y privado; en desarrollo se genera y persiste localmente en `instance/secret_key`.

Los clientes con sesión pueden abrir **PEDIDOS** para consultar su historial y el estado actual: pendiente, preparando, en camino, entregado o cancelado.

## Estructura
```
torram_system/
  app.py
  requirements.txt
  templates/
    base.html
    index.html
    shop.html
    product.html
    cart.html
    login.html
    register.html
    checkout.html
    success.html
    orders.html
    admin.html
    reservation.html
  static/
    css/style.css
    js/app.js
```

## Notas
- Imágenes desde Unsplash (CDN)
- Base de datos preferida: MongoDB Atlas o MongoDB local; si no está disponible, SQLite local.
- Colecciones en español: `usuarios`, `pedidos`, `productos` y `reservas`.
- Si existe el antiguo `instance/users.json`, sus cuentas se migran a `usuarios` al iniciar la app.
- TorRam System v2.6.9 - Hecho con odio al mal diseño.

Autor: Wolters / Umbra
