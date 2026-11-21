@echo off
cd /d "%~dp0"
echo Restableciendo administrador de EcoRuta...
py crear_admin.py
if errorlevel 1 (
  echo.
  echo Error: comprueba .env, certificado CA y conexion a Aiven.
) else (
  echo.
  echo Administrador configurado correctamente.
)
pause
