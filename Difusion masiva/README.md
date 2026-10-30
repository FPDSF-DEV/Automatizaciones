# Difusión masiva

Aplicación web local para enviar correos personalizados a muchos destinatarios, con un archivo adjunto y control de lo que ya se envió. Funciona en tu propio equipo y no guarda nada en la nube.

## Qué puedes hacer

- Cargar destinatarios desde Excel, CSV o JSON, y corregir errores comunes en los correos.
- Excluir registros antes de enviar, sin borrarlos.
- Adjuntar el mismo archivo para todos o generar un Word y un PDF por destinatario.
- Personalizar el asunto y el cuerpo con `{{campos}}`.
- Usar varias cuentas de correo, con límite diario y cambio automático entre ellas.
- Simular el envío y hacer pruebas antes de enviar de verdad.
- Retomar un envío interrumpido sin repetir correos.

## Requisitos

- Python 3.10 o superior.
- Una cuenta de correo con acceso SMTP.
- Solo si generas PDF por destinatario: Windows con Microsoft Word instalado.

`iniciar_app.bat` es para Windows. En otros sistemas, usa los comandos equivalentes para activar el entorno y ejecutar Streamlit.

## Instalación

```powershell
git clone https://github.com/FPDSF-DEV/Automatizaciones.git
cd "Automatizaciones\Difusion masiva"
python -m venv venv
venv\Scripts\python.exe -m pip install -e .
```

## Abrir la aplicación

Haz doble clic en `iniciar_app.bat`, o ejecuta:

```powershell
venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Se abre en <http://localhost:8501>, solo en tu equipo. Deja abierta la ventana y la pestaña del navegador mientras envías.

## Paso 1: registra una cuenta de envío

Entra a **⚙️ Cuentas SMTP**, elige el proveedor, completa los datos y pulsa **Guardar**. Luego selecciona la cuenta y pulsa **🔌 Probar conexión**; esta prueba no envía correos.

| Proveedor | Servidor | Puerto | Qué necesitas |
|---|---|---|---|
| Gmail o Google Workspace (usuario) | `smtp.gmail.com` | 587 | Verificación en 2 pasos y una [contraseña de aplicación](https://myaccount.google.com/apppasswords) |
| Relay de Google Workspace | `smtp-relay.gmail.com` | 587 | Configurar el relay en la consola de administración |
| Hostinger | `smtp.hostinger.com` | 587 | Usuario y contraseña del buzón |
| Otro | El de tu proveedor | El de tu proveedor | Los datos que indique tu proveedor |

Consejos:

- **Límite diario:** pon el de tu plan, con margen. La aplicación lo respeta y pasa a la siguiente cuenta al agotarlo.
- **Remitente visible:** por ejemplo `Mi Organización <noreply@tudominio.com>`.
- **Responder a:** usa un buzón que alguien revise, sobre todo si envías desde una dirección `noreply@`.

### Relay de Google Workspace

En la consola de administración, ve a **Aplicaciones → Google Workspace → Gmail → Enrutamiento → Servicio de retransmisión SMTP**. Permite solo direcciones de tus dominios y exige TLS. Luego elige una de estas formas de autenticación:

- **Por usuario (recomendada):** activa la autenticación SMTP. En la aplicación usa un usuario real con contraseña de aplicación y pon `noreply@tudominio.com` como remitente visible.
- **Por IP:** autoriza la IP pública de tu equipo. En la aplicación elige **Sin login** y escribe tu dominio en **Nombre EHLO**. Si tu proveedor de internet cambia la IP, tendrás que actualizarla.

Para recibir los avisos de correos no entregados de `noreply@`, crea un grupo de Google con esa dirección y permite que publiquen remitentes externos.

## Paso 2: crea una campaña

En **📨 Envío masivo**, elige **➕ Nueva campaña**, escribe un nombre y pulsa **Crear campaña**. Cada campaña guarda en su propia carpeta los destinatarios, adjuntos, asunto, cuerpo y registros.

## Paso 3: carga los destinatarios (1. Datos)

1. Elige **Subir archivo** o pon tu archivo en una carpeta `data/` y elígelo de la lista. Para probar, sube `ejemplos/destinatarios_ejemplo.csv`.
2. Selecciona la columna que tiene el correo.
3. Deja activado **🧹 Sanear correos automáticamente** y revisa el detalle de los cambios y las advertencias.
4. Elige qué se adjunta:
   - **Un mismo archivo para todos:** pulsa **Preparar lista de destinatarios**.
   - **Un documento Word personalizado:** sube una plantilla con marcadores como `{{NOMBRE}}`, asigna cada uno a una columna o a un texto fijo y pulsa **Generar documentos**.

## Paso 4: excluye registros si hace falta (2. Excluir registros)

Elige una o dos columnas y pega una línea por registro:

```text
Municipio Uno, Departamento A
Municipio Dos, Departamento A
```

Revisa las coincidencias y confirma. Los registros salen de la lista y quedan documentados en la carpeta `excluidos/` de la campaña.

## Paso 5: convierte a PDF (3. Exportar PDF)

Solo aplica si generaste un Word por destinatario. Cierra Word antes de empezar. Si usas un mismo archivo para todos, omite este paso.

## Paso 6: prepara y envía el correo (4. Enviar correos)

1. Sube el adjunto, si lo hay.
2. Escribe el asunto y el cuerpo, o carga una plantilla como `email_ejemplo.html`.
3. Revisa la **Vista previa** con varios registros.
4. Envía **siempre en este orden**:

| Orden | Modo | Cómo activarlo | Qué pasa |
|---|---|---|---|
| 1 | Simulación | Deja marcada **Simulación** | No sale ningún correo |
| 2 | Prueba | Desmarca Simulación, escribe tus correos en **Modo prueba** y pon un máximo de 1 a 10 | Los mensajes llegan solo a esos correos |
| 3 | Envío real | Deja vacío Modo prueba, pon el máximo en 0 y marca **Confirmo** | Cada destinatario recibe su correo |

### Campos del correo

En el asunto y el cuerpo, `{{campo}}` debe coincidir **exactamente** con el nombre de una columna, incluidas mayúsculas y minúsculas. Por ejemplo, con el archivo de ejemplo puedes usar `{{nombre}}`, `{{entidad}}`, `{{municipio}}` y `{{departamento}}`.

Si un campo no existe en la campaña, la aplicación bloquea el envío. Los marcadores de la plantilla Word son independientes: se asignan en el paso 3.

### Si el envío se interrumpe

Cada correo aceptado por el servidor queda en `campanas/<campaña>/enviados.csv`, y cada fallo en `fallidos.csv`. Vuelve a abrir la campaña y pulsa **Enviar**: solo se procesan los pendientes.

Que un correo aparezca como enviado significa que el servidor lo aceptó, no que haya llegado. Los correos no entregados se notifican después al remitente.

## Problemas frecuentes

| Mensaje o síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Credenciales rechazadas` o error `535` | Contraseña incorrecta o sin contraseña de aplicación | Genera una contraseña de aplicación y vuelve a guardarla |
| `550 5.7.1 Invalid credentials for relay` | El relay no reconoce tu IP o tu dominio | Revisa la IP autorizada, la autenticación y el nombre EHLO |
| El correo llega a spam | El dominio no está autenticado | Configura SPF, DKIM y DMARC |
| `Cupos agotados` | Se alcanzó el límite diario o todas las cuentas fallaron | Lee `fallidos.csv`; corrige el error o continúa cuando haya cupo |
| Un `{{campo}}` bloquea el envío | No coincide con una columna | Corrige el nombre, incluidas las mayúsculas |
| Un marcador del Word no se reemplaza | Word lo partió por un cambio de formato | Vuelve a escribirlo de corrido |

## Seguridad y privacidad

> **Nunca subas al repositorio credenciales ni datos de personas o entidades.**

Estos archivos quedan solo en tu equipo y `.gitignore` los excluye:

| Archivo o carpeta | Contenido |
|---|---|
| `smtp_accounts.json` | Cuentas y contraseñas **en texto plano** |
| `smtp_usage.json` | Uso diario de cada cuenta |
| `data/` y `campanas/` | Destinatarios, adjuntos y registros de envío |

Antes de cada `git push`, revisa la lista de archivos con `git diff --cached --name-only`. Si subes una contraseña por error, cámbiala de inmediato: borrar el archivo no la elimina del historial.

Usa la aplicación solo para comunicaciones legítimas y con destinatarios a quienes tengas permitido escribir, respetando las normas de protección de datos y las condiciones de tu proveedor de correo.

## Estructura

```text
Difusion masiva/
├── streamlit_app.py         # Interfaz
├── iniciar_app.bat          # Inicio rápido en Windows
├── pyproject.toml           # Dependencias
├── ejemplos/                # Datos inventados y formato de cuentas
└── src/diplomas/            # Datos, documentos, saneamiento y envío
    └── templates/           # Plantillas de correo
```
