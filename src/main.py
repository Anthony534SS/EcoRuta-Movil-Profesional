from pathlib import Path

import flet as ft
import flet_geolocator as ftg
import flet_permission_handler as fph

try:
    import flet_camera as fc
except ImportError:
    fc = None

from cliente_api import (
    iniciar_sesion,
    iniciar_sesion_admin,
    registrar_usuario,
    actualizar_perfil,
    obtener_usuarios,
    crear_reporte,
    obtener_reportes,
    obtener_reporte,
    actualizar_estado_reporte,
    eliminar_reporte,
    enviar_mensaje,
    obtener_mensajes,
    obtener_estadisticas,
    obtener_estadisticas_admin,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
)

VERDE = "#168A4A"
VERDE_OSCURO = "#0B5D32"
VERDE_SUAVE = "#EAF7EF"
VERDE_MUY_SUAVE = "#F4FBF6"
FONDO = "#F7F9F7"
TEXTO = "#17211B"
TEXTO_SECUNDARIO = "#66736B"
BLANCO = "#FFFFFF"
BORDE = "#DDE8E1"
ROJO_SUAVE = "#FFF1F1"
ROJO = "#B3261E"

ASSETS = Path(__file__).parent / "assets"


def main(page: ft.Page):

    page.title = "EcoRuta"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.adaptive = True
    page.padding = 0
    page.spacing = 0
    page.bgcolor = FONDO
    page.theme = ft.Theme(color_scheme_seed=VERDE, use_material3=True)

    if not page.platform.is_mobile():
        page.window.width = 410
        page.window.height = 820
        page.window.min_width = 360
        page.window.min_height = 680

    usuario_actual = {"datos": None}
    modo_admin = {"activo": False}
    foto_actual = {"bytes": None}
    reporte_para_chat = {"id": None}
    pantalla_actual = {"indice": 0}

    geo = ftg.Geolocator(
        configuration=ftg.GeolocatorConfiguration(
            accuracy=ftg.GeolocatorPositionAccuracy.HIGH
        )
    )

    permisos = fph.PermissionHandler()

    # ------------------------------------------------------------------
    # FUNCIONES GENERALES
    # ------------------------------------------------------------------

    def snackbar(texto, error=False):
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(texto),
                bgcolor="#B3261E" if error else VERDE_OSCURO,
            )
        )

    def limpiar():
        page.clean()
        page.appbar = None
        page.navigation_bar = None
        page.floating_action_button = None

    def logo(tamano=72):
        return ft.Container(
            width=tamano,
            height=tamano,
            border_radius=22,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src="icon.png", fit=ft.BoxFit.COVER),
        )

    def titulo_seccion(titulo, subtitulo=None):
        controles = [
            ft.Text(
                titulo,
                size=25,
                weight=ft.FontWeight.BOLD,
                color=TEXTO,
            )
        ]

        if subtitulo:
            controles.append(
                ft.Text(subtitulo, size=13, color=TEXTO_SECUNDARIO)
            )

        return ft.Column(controls=controles, spacing=3)

    def tarjeta(contenido, padding=16, bgcolor=BLANCO):
        return ft.Container(
            content=contenido,
            padding=padding,
            bgcolor=bgcolor,
            border=ft.Border.all(1, BORDE),
            border_radius=18,
        )

    def avatar_nombre(nombre, radio=20):
        inicial = nombre.strip()[0].upper() if nombre and nombre.strip() else "U"

        return ft.CircleAvatar(
            radius=radio,
            bgcolor=VERDE_SUAVE,
            content=ft.Text(
                inicial,
                color=VERDE_OSCURO,
                weight=ft.FontWeight.BOLD,
            ),
        )

    def barra_superior(titulo, mostrar_perfil=True):
        acciones = []

        if mostrar_perfil and usuario_actual["datos"]:
            acciones.append(
                ft.IconButton(
                    icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
                    icon_color=VERDE_OSCURO,
                    tooltip="Mi perfil",
                    on_click=lambda e: mostrar_pantalla(4),
                )
            )

        return ft.AppBar(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ECO_OUTLINED, color=VERDE, size=25),
                    ft.Text(
                        titulo,
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                        size=20,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=BLANCO,
            elevation=0,
            actions=acciones,
        )

    def crear_nav(indice):
        return ft.NavigationBar(
            selected_index=indice,
            bgcolor=BLANCO,
            indicator_color=VERDE_SUAVE,
            elevation=8,
            on_change=lambda e: mostrar_pantalla(e.control.selected_index),
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.HOME_OUTLINED,
                    selected_icon=ft.Icons.HOME,
                    label="Inicio",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
                    selected_icon=ft.Icons.ADD_A_PHOTO,
                    label="Reportar",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.PUBLIC_OUTLINED,
                    selected_icon=ft.Icons.PUBLIC,
                    label="Comunidad",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                    selected_icon=ft.Icons.CHAT_BUBBLE,
                    label="Chat",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.PERSON_OUTLINE,
                    selected_icon=ft.Icons.PERSON,
                    label="Perfil",
                ),
            ],
        )

    def contenedor_pantalla(controles, scroll=True):
        columna = ft.Column(
            controls=controles,
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO if scroll else None,
        )

        return ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                padding=ft.Padding.only(
                    left=18,
                    right=18,
                    top=14,
                    bottom=18,
                ),
                content=columna,
            ),
        )

    # ------------------------------------------------------------------
    # AUTENTICACIÓN
    # ------------------------------------------------------------------

    def pantalla_login():
        limpiar()
        modo_admin["activo"] = False

        email = ft.TextField(
            label="Correo electrónico",
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
            keyboard_type=ft.KeyboardType.EMAIL,
            autofocus=False,
        )

        contrasena = ft.TextField(
            label="Contraseña",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
        )

        def entrar(e):
            usuario = iniciar_sesion(
                email.value or "",
                contrasena.value or "",
            )

            if not usuario:
                snackbar("Correo o contraseña incorrectos.", error=True)
                return

            usuario_actual["datos"] = usuario
            modo_admin["activo"] = False
            mostrar_pantalla(0)

        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    padding=24,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        spacing=16,
                        controls=[
                            ft.Row(
                                [logo(86)],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                                controls=[
                                    ft.Text(
                                        "EcoRuta",
                                        size=32,
                                        weight=ft.FontWeight.BOLD,
                                        color=VERDE_OSCURO,
                                    ),
                                    ft.Text(
                                        "Reporta. Ubica. Comparte.",
                                        size=14,
                                        color=TEXTO_SECUNDARIO,
                                    ),
                                ],
                            ),
                            ft.Container(height=8),
                            tarjeta(
                                ft.Column(
                                    spacing=14,
                                    controls=[
                                        ft.Text(
                                            "Inicia sesión",
                                            size=20,
                                            weight=ft.FontWeight.BOLD,
                                            color=TEXTO,
                                        ),
                                        email,
                                        contrasena,
                                        ft.Button(
                                            content="Entrar a EcoRuta",
                                            icon=ft.Icons.LOGIN,
                                            bgcolor=VERDE,
                                            color=BLANCO,
                                            height=50,
                                            on_click=entrar,
                                        ),
                                        ft.TextButton(
                                            content="¿No tienes cuenta? Crear cuenta",
                                            on_click=lambda e: pantalla_registro(),
                                        ),
                                        ft.Divider(height=1),
                                        ft.OutlinedButton(
                                            content="Acceso de administrador",
                                            icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                                            height=46,
                                            on_click=lambda e: pantalla_login_admin(),
                                        ),
                                    ],
                                ),
                                padding=20,
                            ),
                            ft.Text(
                                "Prototipo móvil académico · Flet + REST API",
                                text_align=ft.TextAlign.CENTER,
                                size=11,
                                color=TEXTO_SECUNDARIO,
                            ),
                        ],
                    ),
                ),
            )
        )

    def pantalla_login_admin():
        limpiar()
        modo_admin["activo"] = True
        page.appbar = barra_superior(
            "Acceso administrador",
            mostrar_perfil=False,
        )

        email = ft.TextField(
            label="Correo de administrador",
            prefix_icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
            keyboard_type=ft.KeyboardType.EMAIL,
            value=ADMIN_EMAIL,
        )

        contrasena = ft.TextField(
            label="Contraseña",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
        )

        def entrar_admin(e):
            print("--- Intentando login de administrador ---")

            admin = iniciar_sesion_admin(
                email.value or "",
                contrasena.value or "",
            )

            print("Resultado recibido de la API:", admin)

            if not admin:
                snackbar(
                    "Credenciales de administrador incorrectas.",
                    error=True,
                )
                return

            usuario_actual["datos"] = admin
            modo_admin["activo"] = True
            mostrar_admin(0)

        page.add(
            contenedor_pantalla(
                [
                    ft.Container(height=20),
                    ft.Row(
                        [logo(78)],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Panel administrativo",
                                size=26,
                                weight=ft.FontWeight.BOLD,
                                color=VERDE_OSCURO,
                            ),
                            ft.Text(
                                "Consulta usuarios y reportes registrados.",
                                size=13,
                                color=TEXTO_SECUNDARIO,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                    tarjeta(
                        ft.Column(
                            spacing=14,
                            controls=[
                                email,
                                contrasena,
                                ft.Button(
                                    content="Entrar como administrador",
                                    icon=ft.Icons.ADMIN_PANEL_SETTINGS,
                                    bgcolor=VERDE_OSCURO,
                                    color=BLANCO,
                                    height=50,
                                    on_click=entrar_admin,
                                ),
                            ],
                        ),
                        padding=20,
                    ),
                    tarjeta(
                        ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "Credenciales del prototipo",
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXTO,
                                ),
                                ft.Text(
                                    f"Correo: {ADMIN_EMAIL}",
                                    size=12,
                                    color=TEXTO_SECUNDARIO,
                                ),
                                ft.Text(
                                    f"Contraseña: {ADMIN_PASSWORD}",
                                    size=12,
                                    color=TEXTO_SECUNDARIO,
                                ),
                            ],
                        ),
                        bgcolor=VERDE_MUY_SUAVE,
                    ),
                    ft.TextButton(
                        content="Volver al acceso de usuario",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=lambda e: pantalla_login(),
                    ),
                ]
            )
        )

    def pantalla_registro():
        limpiar()
        page.appbar = barra_superior(
            "Crear cuenta",
            mostrar_perfil=False,
        )

        nombre = ft.TextField(
            label="Nombre completo",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            capitalization=ft.TextCapitalization.WORDS,
        )

        email = ft.TextField(
            label="Correo electrónico",
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
            keyboard_type=ft.KeyboardType.EMAIL,
        )

        contrasena = ft.TextField(
            label="Contraseña",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
        )

        def registrar(e):
            correcto, texto = registrar_usuario(
                nombre.value or "",
                email.value or "",
                contrasena.value or "",
            )

            snackbar(texto, error=not correcto)

            if correcto:
                pantalla_login()

        page.add(
            contenedor_pantalla(
                [
                    titulo_seccion(
                        "Únete a EcoRuta",
                        "Crea tu cuenta para registrar y compartir reportes.",
                    ),
                    tarjeta(
                        ft.Column(
                            controls=[
                                nombre,
                                email,
                                contrasena,
                                ft.Button(
                                    content="Crear mi cuenta",
                                    icon=ft.Icons.PERSON_ADD_ALT_1,
                                    bgcolor=VERDE,
                                    color=BLANCO,
                                    height=50,
                                    on_click=registrar,
                                ),
                            ],
                            spacing=14,
                        ),
                        padding=20,
                    ),
                    ft.TextButton(
                        content="Ya tengo cuenta",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=lambda e: pantalla_login(),
                    ),
                ]
            )
        )

    # ------------------------------------------------------------------
    # INICIO
    # ------------------------------------------------------------------

    def pantalla_inicio():
        usuario = usuario_actual["datos"]
        estadisticas = obtener_estadisticas(usuario["id"])
        recientes = obtener_reportes(limite=2)

        def stat(icono, numero, etiqueta):
            return ft.Container(
                expand=True,
                padding=12,
                bgcolor=BLANCO,
                border=ft.Border.all(1, BORDE),
                border_radius=16,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Icon(icono, color=VERDE, size=22),
                        ft.Text(
                            str(numero),
                            size=21,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Text(
                            etiqueta,
                            size=10,
                            color=TEXTO_SECUNDARIO,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        controles = [
            ft.Row(
                controls=[
                    avatar_nombre(usuario["nombre"], 24),
                    ft.Column(
                        expand=True,
                        spacing=1,
                        controls=[
                            ft.Text(
                                "Hola,",
                                size=12,
                                color=TEXTO_SECUNDARIO,
                            ),
                            ft.Text(
                                usuario["nombre"],
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
                        icon_color=VERDE_OSCURO,
                        on_click=lambda e: mostrar_pantalla(4),
                    ),
                ]
            ),
            ft.Container(
                padding=20,
                bgcolor=VERDE_OSCURO,
                border_radius=22,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    padding=10,
                                    bgcolor="#26784C",
                                    border_radius=14,
                                    content=ft.Icon(
                                        ft.Icons.ADD_A_PHOTO_OUTLINED,
                                        color=BLANCO,
                                        size=30,
                                    ),
                                ),
                                ft.Column(
                                    expand=True,
                                    spacing=3,
                                    controls=[
                                        ft.Text(
                                            "¿Encontraste basura?",
                                            color=BLANCO,
                                            size=19,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            "Toma una foto y registra la ubicación en segundos.",
                                            color="#DDEFE5",
                                            size=12,
                                        ),
                                    ],
                                ),
                            ],
                            spacing=12,
                        ),
                        ft.Button(
                            content="Crear reporte",
                            icon=ft.Icons.ADD,
                            bgcolor=BLANCO,
                            color=VERDE_OSCURO,
                            height=46,
                            on_click=lambda e: mostrar_pantalla(1),
                        ),
                    ],
                ),
            ),
            ft.Row(
                controls=[
                    stat(
                        ft.Icons.FACT_CHECK_OUTLINED,
                        estadisticas["reportes"],
                        "Mis reportes",
                    ),
                    stat(
                        ft.Icons.SCHEDULE,
                        estadisticas["pendientes"],
                        "Pendientes",
                    ),
                    stat(
                        ft.Icons.CHAT_BUBBLE_OUTLINE,
                        estadisticas["mensajes"],
                        "Mensajes",
                    ),
                ],
                spacing=9,
            ),
            titulo_seccion(
                "Reportes comunitarios recientes",
                "Actividad compartida en EcoRuta.",
            ),
        ]

        if not recientes:
            controles.append(
                tarjeta(
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.ECO_OUTLINED,
                                color=VERDE,
                                size=42,
                            ),
                            ft.Text(
                                "Aún no hay reportes",
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                            ft.Text(
                                "Sé el primero en registrar un punto.",
                                size=12,
                                color=TEXTO_SECUNDARIO,
                            ),
                        ],
                    )
                )
            )
        else:
            for r in recientes:
                controles.append(
                    tarjeta_resumen_reporte(r, compacta=True)
                )

        return contenedor_pantalla(controles)

    # ------------------------------------------------------------------
    # NUEVO REPORTE: CÁMARA + GPS
    # ------------------------------------------------------------------

    def pantalla_nuevo_reporte():
        foto_actual["bytes"] = None

        latitud = ft.TextField(
            label="Latitud",
            prefix_icon=ft.Icons.MY_LOCATION,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )

        longitud = ft.TextField(
            label="Longitud",
            prefix_icon=ft.Icons.LOCATION_ON_OUTLINED,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )

        foto_preview = ft.Container(
            height=220,
            bgcolor=VERDE_MUY_SUAVE,
            border=ft.Border.all(1, BORDE),
            border_radius=20,
            alignment=ft.Alignment.CENTER,
        )

        estado_foto = ft.Text(
            "Agrega una fotografía del punto",
            size=12,
            color=TEXTO_SECUNDARIO,
        )

        estado_gps = ft.Text(
            "Ubicación todavía no registrada",
            size=12,
            color=TEXTO_SECUNDARIO,
        )

        def actualizar_foto():
            if foto_actual["bytes"]:
                foto_preview.content = ft.Image(
                    src=foto_actual["bytes"],
                    fit=ft.BoxFit.COVER,
                    border_radius=20,
                )

                estado_foto.value = "Fotografía lista para el reporte"
                estado_foto.color = VERDE_OSCURO

            else:
                foto_preview.content = ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(
                            ft.Icons.ADD_A_PHOTO_OUTLINED,
                            size=48,
                            color=VERDE,
                        ),
                        ft.Text(
                            "Sin fotografía",
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                    ],
                )

            page.update()

        async def elegir_galeria(e):
            archivos = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
                compression_quality=82,
            )

            if archivos and archivos[0].bytes:
                foto_actual["bytes"] = archivos[0].bytes
                actualizar_foto()

        async def abrir_camara(e):
            if not page.platform.is_mobile() or fc is None:
                snackbar(
                    "La cámara directa se usa en Android/iOS. "
                    "En Thonny selecciona una foto de tu PC."
                )
                await elegir_galeria(e)
                return

            try:
                permiso = await permisos.request(
                    fph.Permission.CAMERA
                )

                if permiso is None or permiso.name not in (
                    "GRANTED",
                    "LIMITED",
                ):
                    snackbar(
                        "Necesitas permitir el acceso a la cámara.",
                        error=True,
                    )
                    return

                preview = fc.Camera(
                    preview_enabled=True,
                    expand=True,
                )

                boton_capturar = ft.Button(
                    content="Tomar foto",
                    icon=ft.Icons.PHOTO_CAMERA,
                    bgcolor=VERDE,
                    color=BLANCO,
                    disabled=True,
                )

                estado = ft.Text(
                    "Preparando cámara...",
                    size=12,
                )

                async def capturar(_):
                    try:
                        datos = await preview.take_picture()

                        if datos:
                            foto_actual["bytes"] = datos
                            page.pop_dialog()
                            actualizar_foto()

                    except Exception as error:
                        snackbar(
                            f"No se pudo tomar la foto: {error}",
                            error=True,
                        )

                boton_capturar.on_click = capturar

                dialogo = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Cámara EcoRuta"),
                    content=ft.Container(
                        width=340,
                        height=430,
                        content=ft.Column(
                            expand=True,
                            controls=[
                                ft.Container(
                                    expand=True,
                                    bgcolor=ft.Colors.BLACK,
                                    border_radius=16,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    content=preview,
                                ),
                                estado,
                            ],
                        ),
                    ),
                    actions=[
                        ft.TextButton(
                            "Cancelar",
                            on_click=lambda _: page.pop_dialog(),
                        ),
                        boton_capturar,
                    ],
                )

                page.show_dialog(dialogo)
                page.update()

                camaras = await preview.get_available_cameras()

                if not camaras:
                    estado.value = "No se encontró una cámara disponible."
                    page.update()
                    return

                camara = next(
                    (
                        c
                        for c in camaras
                        if getattr(
                            getattr(c, "lens_direction", None),
                            "value",
                            "",
                        ) == "back"
                    ),
                    camaras[0],
                )

                await preview.initialize(
                    description=camara,
                    resolution_preset=fc.ResolutionPreset.MEDIUM,
                    enable_audio=False,
                    image_format_group=fc.ImageFormatGroup.JPEG,
                )

                estado.value = "Cámara lista"
                boton_capturar.disabled = False
                page.update()

            except Exception as error:
                snackbar(
                    f"No se pudo abrir la cámara: {error}",
                    error=True,
                )

        async def obtener_gps(e):
            try:
                permiso = await geo.request_permission()

                if permiso.name in ("DENIED", "DENIED_FOREVER"):
                    snackbar(
                        "Necesitas permitir el acceso a la ubicación.",
                        error=True,
                    )
                    return

                posicion = await geo.get_current_position()

                latitud.value = f"{posicion.latitude:.6f}"
                longitud.value = f"{posicion.longitude:.6f}"

                estado_gps.value = "Ubicación obtenida correctamente"
                estado_gps.color = VERDE_OSCURO

                page.update()

            except Exception as error:
                snackbar(
                    "No se pudo obtener el GPS. "
                    "Puedes escribir las coordenadas manualmente. "
                    + str(error),
                    error=True,
                )

        def guardar(e):
            if not foto_actual["bytes"]:
                snackbar(
                    "Primero agrega una fotografía.",
                    error=True,
                )
                return

            if not (latitud.value or "").strip() or not (
                longitud.value or ""
            ).strip():
                snackbar(
                    "Obtén o escribe la latitud y longitud.",
                    error=True,
                )
                return

            try:
                lat = float(latitud.value)
                lon = float(longitud.value)

            except ValueError:
                snackbar(
                    "Las coordenadas deben ser números.",
                    error=True,
                )
                return

            rid = crear_reporte(
                foto_actual["bytes"],
                lat,
                lon,
                usuario_actual["datos"]["id"],
            )

            snackbar(f"Reporte #{rid} enviado a la comunidad.")
            mostrar_pantalla(2)

        actualizar_foto()

        return contenedor_pantalla(
            [
                titulo_seccion(
                    "Nuevo reporte",
                    "Registra evidencia y ubicación del punto con residuos.",
                ),
                ft.Text(
                    "1. Evidencia fotográfica",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=TEXTO,
                ),
                foto_preview,
                estado_foto,
                ft.Row(
                    controls=[
                        ft.Button(
                            content="Cámara",
                            icon=ft.Icons.PHOTO_CAMERA,
                            bgcolor=VERDE,
                            color=BLANCO,
                            expand=True,
                            on_click=abrir_camara,
                        ),
                        ft.OutlinedButton(
                            content="Galería",
                            icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
                            expand=True,
                            on_click=elegir_galeria,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Text(
                    "2. Ubicación del reporte",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=TEXTO,
                ),
                tarjeta(
                    ft.Column(
                        controls=[
                            ft.Row(
                                [latitud, longitud],
                                spacing=8,
                            ),
                            ft.Button(
                                content="Usar mi ubicación GPS",
                                icon=ft.Icons.GPS_FIXED,
                                bgcolor=VERDE_SUAVE,
                                color=VERDE_OSCURO,
                                on_click=obtener_gps,
                            ),
                            estado_gps,
                        ],
                        spacing=10,
                    )
                ),
                tarjeta(
                    ft.Row(
                        controls=[
                            avatar_nombre(
                                usuario_actual["datos"]["nombre"],
                                20,
                            ),
                            ft.Column(
                                expand=True,
                                spacing=1,
                                controls=[
                                    ft.Text(
                                        "El reporte quedará visible públicamente por",
                                        size=11,
                                        color=TEXTO_SECUNDARIO,
                                    ),
                                    ft.Text(
                                        usuario_actual["datos"]["nombre"],
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXTO,
                                    ),
                                    ft.Text(
                                        "La fecha y hora se registran automáticamente.",
                                        size=10,
                                        color=TEXTO_SECUNDARIO,
                                    ),
                                ],
                            ),
                        ]
                    ),
                    bgcolor=VERDE_MUY_SUAVE,
                ),
                ft.Button(
                    content="Enviar reporte comunitario",
                    icon=ft.Icons.SEND,
                    bgcolor=VERDE_OSCURO,
                    color=BLANCO,
                    height=52,
                    on_click=guardar,
                ),
                ft.Container(height=8),
            ]
        )

    # ------------------------------------------------------------------
    # REPORTES COMUNITARIOS
    # ------------------------------------------------------------------

    def tarjeta_resumen_reporte(reporte, compacta=False):
        url_mapa = (
            "https://www.google.com/maps/search/?api=1&query="
            f"{reporte['latitud']},{reporte['longitud']}"
        )

        def compartir(e, rid=reporte["id"]):
            reporte_para_chat["id"] = rid
            mostrar_pantalla(3)

        def confirmar_eliminacion_comunitaria(reporte_id):
            def borrar(_):
                page.pop_dialog()

                es_admin = (
                    usuario_actual["datos"]["rol"] == "admin"
                ) or modo_admin["activo"]

                correcto = eliminar_reporte(
                    reporte_id=reporte_id,
                    usuario_id=usuario_actual["datos"]["id"],
                    es_admin=es_admin,
                )

                if correcto:
                    snackbar(f"Reporte #{reporte_id} eliminado.")

                    if modo_admin["activo"]:
                        mostrar_admin(1)
                    else:
                        mostrar_pantalla(2)

                else:
                    snackbar(
                        "No tienes permisos para eliminar este reporte.",
                        error=True,
                    )

            dialogo = ft.AlertDialog(
                modal=True,
                title=ft.Text("Eliminar reporte"),
                content=ft.Text(
                    f"¿Seguro que deseas eliminar el reporte #{reporte_id}? "
                    "Esta acción lo borrará de la comunidad."
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar",
                        on_click=lambda e: page.pop_dialog(),
                    ),
                    ft.TextButton(
                        "Eliminar",
                        style=ft.ButtonStyle(color=ROJO),
                        on_click=borrar,
                    ),
                ],
            )

            page.show_dialog(dialogo)

        imagen = ft.Image(
            src=reporte["imagen"],
            width=112 if compacta else None,
            height=100 if compacta else 190,
            fit=ft.BoxFit.COVER,
            border_radius=14,
        )

        info = ft.Column(
            expand=True,
            spacing=5,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            f"Reporte #{reporte['id']}",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                            color=TEXTO,
                            expand=True,
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(
                                horizontal=9,
                                vertical=4,
                            ),
                            bgcolor=VERDE_SUAVE,
                            border_radius=20,
                            content=ft.Text(
                                reporte["estado"],
                                size=10,
                                color=VERDE_OSCURO,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                    ]
                ),
                ft.Text(
                    f"Por: {reporte['usuario_nombre']}",
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=TEXTO,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.SCHEDULE,
                            size=14,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Text(
                            reporte["fecha_hora"],
                            size=11,
                            color=TEXTO_SECUNDARIO,
                        ),
                    ],
                    spacing=5,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.LOCATION_ON_OUTLINED,
                            size=14,
                            color=VERDE,
                        ),
                        ft.Text(
                            f"{reporte['latitud']:.5f}, "
                            f"{reporte['longitud']:.5f}",
                            size=11,
                            color=TEXTO_SECUNDARIO,
                        ),
                    ],
                    spacing=5,
                ),
            ],
        )

        es_autor = (
            usuario_actual["datos"]
            and reporte["usuario_id"] == usuario_actual["datos"]["id"]
        )

        es_admin = (
            usuario_actual["datos"]
            and usuario_actual["datos"]["rol"] == "admin"
        ) or modo_admin["activo"]

        acciones_botones = [
            ft.OutlinedButton(
                content="Mapa",
                icon=ft.Icons.MAP_OUTLINED,
                expand=True,
                action=ft.OpenUrl(url_mapa),
            ),
            ft.Button(
                content="Compartir",
                icon=ft.Icons.SHARE_OUTLINED,
                bgcolor=VERDE_SUAVE,
                color=VERDE_OSCURO,
                expand=True,
                on_click=compartir,
            ),
        ]

        if es_autor or es_admin:
            acciones_botones.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ROJO,
                    tooltip=(
                        "Eliminar reporte"
                        if es_autor
                        else "Eliminar como administrador"
                    ),
                    on_click=lambda e, rid=reporte["id"]: (
                        confirmar_eliminacion_comunitaria(rid)
                    ),
                )
            )

        if compacta:
            contenido = ft.Row(
                [imagen, info],
                spacing=12,
            )
        else:
            contenido = ft.Column(
                spacing=10,
                controls=[
                    imagen,
                    info,
                    ft.Row(
                        controls=acciones_botones,
                        spacing=8,
                    ),
                ],
            )

        return tarjeta(contenido)

    def pantalla_reportes():
        reportes = obtener_reportes()

        controles = [
            titulo_seccion(
                "Reportes comunitarios",
                "Consulta todos los puntos reportados por la comunidad en tiempo real.",
            )
        ]

        if not reportes:
            controles.append(
                tarjeta(
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.INBOX_OUTLINED,
                                size=50,
                                color=VERDE,
                            ),
                            ft.Text(
                                "No hay reportes comunitarios aún",
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Button(
                                content="Crear el primero",
                                icon=ft.Icons.ADD,
                                on_click=lambda e: mostrar_pantalla(1),
                            ),
                        ],
                    )
                )
            )

        else:
            controles.extend(
                tarjeta_resumen_reporte(r)
                for r in reportes
            )

        return contenedor_pantalla(controles)

    # ------------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------------

    def pantalla_chat():
        mensajes_lista = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        )

        contenedor_chat = ft.Container(
            content=mensajes_lista,
            expand=True,
            padding=5,
        )

        entrada = ft.TextField(
            hint_text="Escribe un mensaje...",
            multiline=True,
            min_lines=1,
            max_lines=3,
            expand=True,
        )

        aviso = ft.Container(visible=False)

        if reporte_para_chat["id"] is not None:
            rid = reporte_para_chat["id"]
            aviso.visible = True
            aviso.padding = 10
            aviso.bgcolor = VERDE_SUAVE
            aviso.border_radius = 14
            aviso.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ATTACH_FILE, color=VERDE_OSCURO),
                    ft.Text(
                        f"Reporte #{rid} adjunto",
                        expand=True,
                        color=VERDE_OSCURO,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=18,
                        on_click=lambda e: quitar_adjunto(),
                    ),
                ]
            )

        def quitar_adjunto():
            reporte_para_chat["id"] = None
            aviso.visible = False
            page.update()

        def cargar():
            mensajes_lista.controls.clear()
            datos = obtener_mensajes()
            print("DATOS RECIBIDOS EN CHAT:", datos)

            if not datos or not isinstance(datos, list):
                mensajes_lista.controls.append(
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=30,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.FORUM_OUTLINED, size=45, color=VERDE),
                                ft.Text(
                                    "Inicia la conversación",
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    "Aquí puedes compartir mensajes y reportes.",
                                    size=12,
                                    color=TEXTO_SECUNDARIO,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
            else:
                id_actual = usuario_actual["datos"].get("id") if usuario_actual.get("datos") else None

                for m in datos:
                    if not isinstance(m, dict):
                        continue

                    uid_mensaje = m.get("usuario_id") or m.get("id_usuario")
                    nombre_usuario = m.get("usuario_nombre") or m.get("nombre") or "Usuario"
                    
                    # Extraer el contenido del mensaje
                    contenido_texto = str(
                        m.get("texto") 
                        or m.get("contenido") 
                        or m.get("contenido_mensaje") 
                        or ""
                    ).strip()
                    
                    fecha_texto = str(m.get("fecha_hora") or m.get("fecha") or "").strip()
                    reporte_id_val = m.get("reporte_id")

                    propio = (uid_mensaje == id_actual) if id_actual is not None else False

                    controles = [
                        ft.Text(
                            "Tú" if propio else nombre_usuario,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=VERDE_OSCURO if propio else TEXTO_SECUNDARIO,
                        ),
                        ft.Text(
                            contenido_texto if contenido_texto else "(Mensaje sin contenido)",
                            size=14,
                            color=TEXTO,
                        ),
                    ]

                    if reporte_id_val is not None:
                        r = obtener_reporte(reporte_id_val)
                        if r:
                            controles.append(
                                ft.Container(
                                    padding=9,
                                    bgcolor=BLANCO,
                                    border_radius=12,
                                    border=ft.Border.all(1, BORDE),
                                    content=ft.Row(
                                        controls=[
                                            ft.Image(
                                                src=r.get("imagen"),
                                                width=72,
                                                height=72,
                                                fit=ft.BoxFit.COVER,
                                                border_radius=10,
                                            ),
                                            ft.Column(
                                                expand=True,
                                                spacing=3,
                                                controls=[
                                                    ft.Text(
                                                        f"Reporte #{r.get('id')}",
                                                        weight=ft.FontWeight.BOLD,
                                                        size=12,
                                                    ),
                                                    ft.Text(
                                                        f"{r.get('latitud', 0):.5f}, {r.get('longitud', 0):.5f}",
                                                        size=10,
                                                        color=TEXTO_SECUNDARIO,
                                                    ),
                                                    ft.Text(
                                                        f"Por {r.get('usuario_nombre', 'Usuario')}",
                                                        size=10,
                                                        color=TEXTO_SECUNDARIO,
                                                    ),
                                                ],
                                            ),
                                        ]
                                    ),
                                )
                            )

                    if fecha_texto:
                        controles.append(
                            ft.Text(fecha_texto, size=9, color=TEXTO_SECUNDARIO)
                        )

                    mensajes_lista.controls.append(
                        ft.Row(
                            alignment=(
                                ft.MainAxisAlignment.END
                                if propio
                                else ft.MainAxisAlignment.START
                            ),
                            controls=[
                                ft.Container(
                                    width=280,
                                    padding=12,
                                    bgcolor=VERDE_SUAVE if propio else BLANCO,
                                    border=ft.Border.all(1, BORDE),
                                    border_radius=16,
                                    content=ft.Column(controls=controles, spacing=4),
                                )
                            ],
                        )
                    )
            page.update()

        def mandar(e):
            texto = (entrada.value or "").strip()

            if not texto and reporte_para_chat["id"] is None:
                snackbar(
                    "Escribe un mensaje o adjunta un reporte.",
                    error=True,
                )
                return

            enviado = enviar_mensaje(
                texto,
                usuario_actual["datos"]["id"],
                reporte_para_chat["id"],
            )

            if not enviado:
                snackbar(
                    "No se pudo enviar el mensaje al servidor.",
                    error=True,
                )
                return

            entrada.value = ""
            reporte_para_chat["id"] = None
            aviso.visible = False

            try:
                entrada.focus_async()
            except AttributeError:
                pass
            cargar()

        cargar()

        return ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                padding=ft.Padding.only(
                    left=14,
                    right=14,
                    top=10,
                    bottom=10,
                ),
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.Row(
                            controls=[
                                titulo_seccion(
                                    "Comunidad",
                                    "Chat de usuarios EcoRuta.",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH,
                                    tooltip="Actualizar",
                                    on_click=lambda e: cargar(),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        aviso,
                        contenedor_chat,
                        ft.Container(
                            padding=8,
                            bgcolor=BLANCO,
                            border=ft.Border.all(1, BORDE),
                            border_radius=18,
                            content=ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    entrada,
                                    ft.IconButton(
                                        icon=ft.Icons.SEND_ROUNDED,
                                        icon_color=VERDE,
                                        on_click=mandar,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )

    # ------------------------------------------------------------------
    # PERFIL Y EDICIÓN DE PERFIL
    # ------------------------------------------------------------------

    def cerrar_sesion_general():
        usuario_actual["datos"] = None
        reporte_para_chat["id"] = None
        modo_admin["activo"] = False
        pantalla_login()

    def pantalla_editar_perfil(es_admin=False):
        usuario = usuario_actual["datos"]

        nombre = ft.TextField(
            label="Nombre",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            value=usuario["nombre"],
            capitalization=ft.TextCapitalization.WORDS,
        )

        email = ft.TextField(
            label="Correo electrónico",
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
            keyboard_type=ft.KeyboardType.EMAIL,
            value=usuario["email"],
        )

        nueva = ft.TextField(
            label="Nueva contraseña (opcional)",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            helper="Déjala vacía para conservar tu contraseña actual.",
        )

        def guardar_cambios(e):
            correcto, mensaje, actualizado = actualizar_perfil(
                usuario["id"],
                nombre.value or "",
                email.value or "",
                nueva.value or "",
            )

            snackbar(mensaje, error=not correcto)

            if correcto:
                usuario_actual["datos"] = actualizado

                if es_admin:
                    mostrar_admin(3)
                else:
                    mostrar_pantalla(4)

        def volver(e):
            if es_admin:
                mostrar_admin(3)
            else:
                mostrar_pantalla(4)

        limpiar()
        page.appbar = barra_superior(
            "Editar perfil",
            mostrar_perfil=False,
        )

        page.add(
            contenedor_pantalla(
                [
                    titulo_seccion(
                        "Editar perfil",
                        "Actualiza tu nombre, correo o contraseña.",
                    ),
                    tarjeta(
                        ft.Column(
                            controls=[nombre, email, nueva],
                            spacing=14,
                        ),
                        padding=20,
                    ),
                    ft.Button(
                        content="Guardar cambios",
                        icon=ft.Icons.SAVE_OUTLINED,
                        bgcolor=VERDE,
                        color=BLANCO,
                        height=50,
                        on_click=guardar_cambios,
                    ),
                    ft.OutlinedButton(
                        content="Cancelar",
                        icon=ft.Icons.ARROW_BACK,
                        height=48,
                        on_click=volver,
                    ),
                ]
            )
        )

    def pantalla_eliminar_reportes(es_admin=False):
        usuario = usuario_actual["datos"]

        if es_admin:
            reportes = obtener_reportes()
            subtitulo = "Elimina cualquier reporte registrado por los usuarios."
        else:
            reportes = obtener_reportes(usuario_id=usuario["id"])
            subtitulo = "Elimina uno de tus reportes registrados."

        def confirmar_eliminacion(reporte_id):
            def borrar(_):
                page.pop_dialog()

                correcto = eliminar_reporte(
                    reporte_id,
                    usuario["id"],
                    es_admin=es_admin,
                )

                if correcto:
                    snackbar(
                        f"Reporte #{reporte_id} eliminado correctamente."
                    )
                    mostrar_eliminacion_reportes(es_admin)

                else:
                    snackbar(
                        "No se pudo eliminar el reporte.",
                        error=True,
                    )

            dialogo = ft.AlertDialog(
                modal=True,
                title=ft.Text("Eliminar reporte"),
                content=ft.Text(
                    f"¿Seguro que deseas eliminar el reporte #{reporte_id}? "
                    "Esta acción no se puede deshacer."
                ),
                actions=[
                    ft.TextButton(
                        content="Cancelar",
                        on_click=lambda e: page.pop_dialog(),
                    ),
                    ft.TextButton(
                        content="Eliminar",
                        style=ft.ButtonStyle(color=ROJO),
                        on_click=borrar,
                    ),
                ],
            )

            page.show_dialog(dialogo)

        controles = [
            titulo_seccion(
                "Eliminar reporte",
                subtitulo,
            ),
        ]

        if not reportes:
            controles.append(
                tarjeta(
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(
                                ft.Icons.DELETE_OUTLINE,
                                size=46,
                                color=VERDE,
                            ),
                            ft.Text(
                                "No hay reportes para eliminar",
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                            ft.Text(
                                "Los reportes que registres aparecerán aquí.",
                                size=12,
                                color=TEXTO_SECUNDARIO,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    )
                )
            )

        else:
            for reporte in reportes:
                datos = ft.Column(
                    expand=True,
                    spacing=4,
                    controls=[
                        ft.Text(
                            f"Reporte #{reporte['id']}",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Text(
                            reporte.get("usuario_nombre", "Usuario"),
                            size=11,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Text(
                            f"Estado: {reporte['estado']}",
                            size=11,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Text(
                            reporte["fecha_hora"],
                            size=10,
                            color=TEXTO_SECUNDARIO,
                        ),
                    ],
                )

                controles.append(
                    tarjeta(
                        ft.Column(
                            spacing=10,
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Image(
                                            src=reporte["imagen"],
                                            width=92,
                                            height=92,
                                            fit=ft.BoxFit.COVER,
                                            border_radius=12,
                                        ),
                                        datos,
                                    ],
                                    spacing=12,
                                ),
                                ft.OutlinedButton(
                                    content="Eliminar reporte",
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    style=ft.ButtonStyle(
                                        color=ROJO,
                                        side=ft.BorderSide(1, ROJO),
                                    ),
                                    on_click=lambda e, rid=reporte["id"]: (
                                        confirmar_eliminacion(rid)
                                    ),
                                ),
                            ],
                        )
                    )
                )

        controles.append(
            ft.OutlinedButton(
                content="Volver al perfil",
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: (
                    mostrar_admin(3)
                    if es_admin
                    else mostrar_pantalla(4)
                ),
            )
        )

        return contenedor_pantalla(controles)

    def mostrar_eliminacion_reportes(es_admin=False):
        page.clean()

        if es_admin:
            page.appbar = barra_superior_admin("Eliminar reportes")
            page.navigation_bar = crear_nav_admin(3)

        else:
            page.appbar = barra_superior(
                "Eliminar reporte",
                mostrar_perfil=False,
            )
            page.navigation_bar = crear_nav(4)

        page.add(pantalla_eliminar_reportes(es_admin))
        page.update()

    def pantalla_perfil():
        usuario = usuario_actual["datos"]
        stats = obtener_estadisticas(usuario["id"])

        return contenedor_pantalla(
            [
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        avatar_nombre(usuario["nombre"], 44),
                        ft.Text(
                            usuario["nombre"],
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Text(
                            usuario["email"],
                            size=13,
                            color=TEXTO_SECUNDARIO,
                        ),
                    ],
                ),
                tarjeta(
                    ft.Column(
                        controls=[
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.FACT_CHECK_OUTLINED,
                                    color=VERDE,
                                ),
                                title=ft.Text("Mis reportes"),
                                trailing=ft.Text(
                                    str(stats["reportes"]),
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                            ft.Divider(height=1),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.EMAIL_OUTLINED,
                                    color=VERDE,
                                ),
                                title=ft.Text("Correo"),
                                subtitle=ft.Text(usuario["email"]),
                            ),
                            ft.Divider(height=1),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.GPS_FIXED,
                                    color=VERDE,
                                ),
                                title=ft.Text("GPS y cámara"),
                                subtitle=ft.Text(
                                    "Integrados para registrar reportes"
                                ),
                            ),
                            ft.Divider(height=1),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.DELETE_OUTLINE,
                                    color=ROJO,
                                ),
                                title=ft.Text(
                                    "Eliminar mi reporte",
                                    color=ROJO,
                                ),
                                subtitle=ft.Text(
                                    "Selecciona uno de tus reportes para eliminarlo"
                                ),
                                on_click=lambda e: (
                                    mostrar_eliminacion_reportes(False)
                                ),
                            ),
                        ]
                    )
                ),
                ft.Button(
                    content="Editar perfil",
                    icon=ft.Icons.EDIT_OUTLINED,
                    bgcolor=VERDE_SUAVE,
                    color=VERDE_OSCURO,
                    height=50,
                    on_click=lambda e: pantalla_editar_perfil(False),
                ),
                ft.OutlinedButton(
                    content="Cerrar sesión",
                    icon=ft.Icons.LOGOUT,
                    height=50,
                    on_click=lambda e: cerrar_sesion_general(),
                ),
                ft.Text(
                    "EcoRuta · Prototipo académico móvil",
                    size=11,
                    color=TEXTO_SECUNDARIO,
                    text_align=ft.TextAlign.CENTER,
                ),
            ]
        )

    # ------------------------------------------------------------------
    # PANEL DE ADMINISTRADOR
    # ------------------------------------------------------------------

    def barra_superior_admin(titulo):
        return ft.AppBar(
            title=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                        color=VERDE_OSCURO,
                        size=25,
                    ),
                    ft.Text(
                        titulo,
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                        size=20,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=BLANCO,
            elevation=0,
            actions=[
                ft.IconButton(
                    icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
                    icon_color=VERDE_OSCURO,
                    tooltip="Perfil administrador",
                    on_click=lambda e: mostrar_admin(3),
                )
            ],
        )

    def crear_nav_admin(indice):
        return ft.NavigationBar(
            selected_index=indice,
            bgcolor=BLANCO,
            indicator_color=VERDE_SUAVE,
            elevation=8,
            on_change=lambda e: mostrar_admin(
                e.control.selected_index
            ),
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.DASHBOARD_OUTLINED,
                    selected_icon=ft.Icons.DASHBOARD,
                    label="Resumen",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.FACT_CHECK_OUTLINED,
                    selected_icon=ft.Icons.FACT_CHECK,
                    label="Reportes",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.PEOPLE_OUTLINE,
                    selected_icon=ft.Icons.PEOPLE,
                    label="Usuarios",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.PERSON_OUTLINE,
                    selected_icon=ft.Icons.PERSON,
                    label="Perfil",
                ),
            ],
        )

    def tarjeta_reporte_admin(reporte, compacta=False):
        url_mapa = (
            "https://www.google.com/maps/search/?api=1&query="
            f"{reporte['latitud']},{reporte['longitud']}"
        )

        imagen = ft.Image(
            src=reporte["imagen"],
            width=105 if compacta else None,
            height=95 if compacta else 185,
            fit=ft.BoxFit.COVER,
            border_radius=14,
        )

        info = ft.Column(
            expand=True,
            spacing=4,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            f"Reporte #{reporte['id']}",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                            color=TEXTO,
                            expand=True,
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(
                                horizontal=9,
                                vertical=4,
                            ),
                            bgcolor=VERDE_SUAVE,
                            border_radius=20,
                            content=ft.Text(
                                reporte["estado"],
                                size=10,
                                color=VERDE_OSCURO,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                    ]
                ),
                ft.Text(
                    reporte["usuario_nombre"],
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=TEXTO,
                ),
                ft.Text(
                    reporte["usuario_email"],
                    size=10,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    reporte["fecha_hora"],
                    size=10,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    f"{reporte['latitud']:.5f}, "
                    f"{reporte['longitud']:.5f}",
                    size=10,
                    color=TEXTO_SECUNDARIO,
                ),
            ],
        )

        if compacta:
            return tarjeta(
                ft.Row(
                    [imagen, info],
                    spacing=12,
                )
            )

        def cambiar_estado(estado):
            if actualizar_estado_reporte(reporte["id"], estado):
                snackbar(
                    f"Reporte #{reporte['id']} actualizado a: {estado}."
                )
                mostrar_admin(1)

            else:
                snackbar(
                    "No se pudo actualizar el reporte.",
                    error=True,
                )

        def eliminar_como_admin(rid):
            if eliminar_reporte(rid, es_admin=True):
                snackbar(f"Reporte #{rid} eliminado.")
                mostrar_admin(1)

            else:
                snackbar(
                    "No se pudo eliminar el reporte.",
                    error=True,
                )

        return tarjeta(
            ft.Column(
                spacing=10,
                controls=[
                    imagen,
                    info,
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                content="Abrir mapa",
                                icon=ft.Icons.MAP_OUTLINED,
                                expand=True,
                                action=ft.OpenUrl(url_mapa),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ROJO,
                                tooltip="Eliminar reporte (Admin)",
                                on_click=lambda e, rid=reporte["id"]: (
                                    eliminar_como_admin(rid)
                                ),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Cambiar estado",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO_SECUNDARIO,
                    ),
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                content="Pendiente",
                                on_click=lambda e: cambiar_estado("Pendiente"),
                            ),
                            ft.TextButton(
                                content="En revisión",
                                on_click=lambda e: cambiar_estado("En revisión"),
                            ),
                            ft.TextButton(
                                content="Atendido",
                                on_click=lambda e: cambiar_estado("Atendido"),
                            ),
                        ],
                        spacing=1,
                    ),
                ],
            )
        )

    def pantalla_admin_inicio():
        admin_actual = usuario_actual["datos"]
        stats = obtener_estadisticas_admin()
        recientes = obtener_reportes(limite=3)

        def stat(icono, numero, etiqueta):
            return ft.Container(
                expand=True,
                padding=11,
                bgcolor=BLANCO,
                border=ft.Border.all(1, BORDE),
                border_radius=16,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Icon(icono, color=VERDE, size=22),
                        ft.Text(
                            str(numero),
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Text(
                            etiqueta,
                            size=9,
                            color=TEXTO_SECUNDARIO,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        controles = [
            ft.Row(
                controls=[
                    avatar_nombre(admin_actual["nombre"], 24),
                    ft.Column(
                        expand=True,
                        spacing=1,
                        controls=[
                            ft.Text("Panel administrativo", size=12, color=TEXTO_SECUNDARIO),
                            ft.Text(admin_actual["nombre"], size=19, weight=ft.FontWeight.BOLD, color=TEXTO),
                        ],
                    ),
                ]
            ),
            ft.Row(
                controls=[
                    stat(ft.Icons.PEOPLE_OUTLINE, stats["usuarios"], "Usuarios registrados"),
                    stat(ft.Icons.FACT_CHECK_OUTLINED, stats["reportes"], "Total reportes"),
                ],
                spacing=9,
            ),
            ft.Row(
                controls=[
                    stat(ft.Icons.SCHEDULE, stats["pendientes"], "Pendientes"),
                    stat(ft.Icons.CHECK_CIRCLE_OUTLINE, stats["atendidos"], "Atendidos"),
                ],
                spacing=9,
            ),
            titulo_seccion("Reportes recientes", "Últimos reportes enviados por los usuarios."),
        ]

        if recientes:
            controles.extend(tarjeta_reporte_admin(r, compacta=True) for r in recientes)
        else:
            controles.append(
                tarjeta(
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.INBOX_OUTLINED, size=44, color=VERDE),
                            ft.Text("Todavía no hay reportes", weight=ft.FontWeight.BOLD),
                        ],
                    )
                )
            )

        return contenedor_pantalla(controles)

    def pantalla_admin_reportes():
        reportes = obtener_reportes()

        controles = [
            titulo_seccion(
                "Reportes comunitarios (Admin)",
                "Administra estados o elimina reportes de cualquier usuario.",
            )
        ]

        if reportes:
            controles.extend(
                tarjeta_reporte_admin(r)
                for r in reportes
            )

        else:
            controles.append(
                tarjeta(
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.INBOX_OUTLINED,
                                size=48,
                                color=VERDE,
                            ),
                            ft.Text(
                                "No hay reportes registrados",
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                    )
                )
            )

        return contenedor_pantalla(controles)

    def pantalla_admin_usuarios():
        usuarios = obtener_usuarios()

        controles = [
            titulo_seccion(
                "Usuarios registrados",
                "Consulta las cuentas principales y cuántos reportes "
                "ha creado cada una.",
            )
        ]

        if not usuarios:
            controles.append(
                tarjeta(
                    ft.Text(
                        "Todavía no hay usuarios registrados.",
                        color=TEXTO_SECUNDARIO,
                    )
                )
            )

        else:
            for u in usuarios:
                controles.append(
                    tarjeta(
                        ft.Row(
                            controls=[
                                avatar_nombre(u["nombre"], 23),
                                ft.Column(
                                    expand=True,
                                    spacing=3,
                                    controls=[
                                        ft.Text(
                                            u["nombre"],
                                            weight=ft.FontWeight.BOLD,
                                            color=TEXTO,
                                        ),
                                        ft.Text(
                                            u["email"],
                                            size=11,
                                            color=TEXTO_SECUNDARIO,
                                        ),
                                        ft.Text(
                                            f"Reportes registrados: "
                                            f"{u['total_reportes']}",
                                            size=11,
                                            color=VERDE_OSCURO,
                                        ),
                                    ],
                                ),
                            ],
                            spacing=12,
                        )
                    )
                )

        return contenedor_pantalla(controles)

    def pantalla_admin_perfil():
        admin_actual = usuario_actual["datos"]

        return contenedor_pantalla(
            [
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        avatar_nombre(admin_actual["nombre"], 44),
                        ft.Text(
                            admin_actual["nombre"],
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Text(
                            admin_actual["email"],
                            size=13,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(
                                horizontal=12,
                                vertical=5,
                            ),
                            bgcolor=VERDE_SUAVE,
                            border_radius=20,
                            content=ft.Text(
                                "ADMINISTRADOR",
                                size=10,
                                weight=ft.FontWeight.BOLD,
                                color=VERDE_OSCURO,
                            ),
                        ),
                    ],
                ),
                tarjeta(
                    ft.Column(
                        controls=[
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                                    color=VERDE,
                                ),
                                title=ft.Text("Permisos"),
                                subtitle=ft.Text(
                                    "Consulta usuarios y administra/"
                                    "elimina cualquier reporte"
                                ),
                            ),
                            ft.Divider(height=1),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.SECURITY_OUTLINED,
                                    color=VERDE,
                                ),
                                title=ft.Text("Tipo de cuenta"),
                                subtitle=ft.Text(
                                    "Administrador de EcoRuta"
                                ),
                            ),
                            ft.Divider(height=1),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.DELETE_OUTLINE,
                                    color=ROJO,
                                ),
                                title=ft.Text(
                                    "Eliminar reportes",
                                    color=ROJO,
                                ),
                                subtitle=ft.Text(
                                    "Gestión y borrado global de reportes comunitarios"
                                ),
                                on_click=lambda e: (
                                    mostrar_eliminacion_reportes(True)
                                ),
                            ),
                        ]
                    )
                ),
                ft.OutlinedButton(
                    content="Cerrar sesión",
                    icon=ft.Icons.LOGOUT,
                    height=50,
                    on_click=lambda e: cerrar_sesion_general(),
                ),
            ]
        )

    def mostrar_admin(indice):
        if usuario_actual["datos"] is None or not modo_admin["activo"]:
            pantalla_login_admin()
            return

        page.clean()

        page.appbar = barra_superior_admin(
            [
                "Administración",
                "Reportes",
                "Usuarios",
                "Perfil administrador",
            ][indice]
        )

        page.navigation_bar = crear_nav_admin(indice)

        pantallas = [
            pantalla_admin_inicio,
            pantalla_admin_reportes,
            pantalla_admin_usuarios,
            pantalla_admin_perfil,
        ]

        page.add(pantallas[indice]())
        page.update()

    # ------------------------------------------------------------------
    # NAVEGACIÓN PRINCIPAL
    # ------------------------------------------------------------------

    def mostrar_pantalla(indice):
        if usuario_actual["datos"] is None:
            pantalla_login()
            return

        if modo_admin["activo"]:
            mostrar_admin(0)
            return

        pantalla_actual["indice"] = indice

        page.clean()

        page.appbar = barra_superior(
            [
                "EcoRuta",
                "Nuevo reporte",
                "Comunidad",
                "Chat",
                "Mi perfil",
            ][indice]
        )

        page.navigation_bar = crear_nav(indice)

        pantallas = [
            pantalla_inicio,
            pantalla_nuevo_reporte,
            pantalla_reportes,
            pantalla_chat,
            pantalla_perfil,
        ]

        page.add(pantallas[indice]())
        page.update()

    pantalla_login()


if __name__ == "__main__":
    ft.run(main, assets_dir=str(ASSETS))
