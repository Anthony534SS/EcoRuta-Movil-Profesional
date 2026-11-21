# Backend EcoRuta — Aiven / Render

El backend de esta carpeta se conecta exclusivamente a la base MySQL existente `ecoruta`.
No crea bases, no crea tablas y no ejecuta migraciones automáticas.

## Variables requeridas

Configura en Render (Environment):

- `MYSQL_HOST=ecoruta-antonio-618d.c.aivencloud.com`
- `MYSQL_PORT=21716`
- `MYSQL_USER=avnadmin`
- `MYSQL_PASSWORD`: contraseña vigente de Aiven (no guardarla en Git).
- `MYSQL_DATABASE=ecoruta`
- `MYSQL_SSL_CA=/etc/secrets/ca.pem`
- `ECORUTA_SECRET_KEY`: secreto aleatorio de al menos 32 caracteres.
- `TOKEN_MINUTOS=720`
- `PUBLIC_API_URL=https://ecoruta-api-antonio.onrender.com`
- `MEDIA_DIR=/var/data/ecoruta/uploads`

Agrega el certificado CA de Aiven en Render como Secret File con nombre `ca.pem`.

## Almacenamiento de imágenes

Los reportes nuevos se guardan en un directorio de archivos y MySQL conserva su URL relativa en `reportes.imagen_url`.
En Render se necesita un Persistent Disk montado en `/var/data`, porque el disco temporal del servicio puede perder los archivos al reiniciar o desplegar.

## Render

Desde la raíz del repositorio:

Build Command:

```bash
pip install -r EcoRuta/requirements.txt
```

Start Command:

```bash
uvicorn api:app --app-dir EcoRuta --host 0.0.0.0 --port $PORT
```

Health Check Path: `/health`

No cambies el servicio ni el dominio anterior `https://ecoruta-api-antonio.onrender.com`.

## Cuenta administradora

Se conservan el correo y la contraseña que tenía configurados el proyecto original. Para crear o actualizar solo esa cuenta en la tabla `usuarios`, ejecuta una vez desde esta carpeta:

```bash
python crear_admin.py
```

El script no borra otras cuentas ni cambia IDs de usuarios existentes. En producción se recomienda establecer `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `ADMIN_NAME` como variables de entorno antes de ejecutarlo.

## Esquema utilizado

El backend está adaptado a las columnas del SQL original `EcoRuta_MySQL_Completa_800_Registros.sql`:
`usuarios.id_usuario`, `usuarios.password_hash`, `reportes.id_reporte`, `reportes.id_usuario`, `reportes.id_categoria`, `reportes.id_area`, `reportes.imagen_url`, `categorias_residuos.id_categoria`, `areas_responsables.id_area`, `seguimiento_reportes`, `asignaciones_reportes`, `mensajes` y `notificaciones`.

No ejecutes el antiguo `src/ecoruta_db.sql`: correspondía a otro esquema (`ecoruta_db`) e incluía sentencias DROP TABLE.
