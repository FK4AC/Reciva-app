import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config import SMTP_CONFIG


def _resolve_smtp(override=None):
    """Mezcla el override (dict con 'user'/'password') sobre SMTP_CONFIG."""
    cfg = dict(SMTP_CONFIG)
    if override:
        for k, v in override.items():
            if v:
                cfg[k] = v
    return cfg


def _parse_destinatarios(raw):
    """Acepta str (un correo o varios separados por coma/salto de línea) o lista."""
    if isinstance(raw, list):
        return [d.strip() for d in raw if d.strip()]
    return [d.strip()
            for d in raw.replace(',', '\n').splitlines()
            if d.strip()]

# ── Colores marca INGESAM (rojo) ─────────────────────────────────────────────
_VERDE       = '#C9040B'   # rojo INGESAM principal
_VERDE_OSC   = '#8F0307'   # rojo oscuro (footer / banda)
_VERDE_CLARO = '#FDECED'   # rojo muy claro (fondos)
_VERDE_TXT   = '#F7BBBE'   # texto claro sobre fondo rojo
_LINE        = '#F0C8CA'   # borde cálido
_TEXTO       = '#1B1512'   # tinta oscura
_MUTED       = '#7A5252'   # muted cálido

# CID para el logo embebido (imagen adjunta inline, no base64 en HTML)
_LOGO_CID  = 'logo_ingesam_aseo'
_LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'logo_png',
                          'logo-512-space-no-fondo-1.png')


def _logo_disponible() -> bool:
    return os.path.exists(_LOGO_PATH)


def _adjuntar_logo(related: MIMEMultipart) -> None:
    """Adjunta el logo como imagen inline CID al contenedor 'related'."""
    try:
        with open(_LOGO_PATH, 'rb') as f:
            datos = f.read()
        img = MIMEBase('image', 'png')
        img.set_payload(datos)
        encoders.encode_base64(img)
        img.add_header('Content-ID', f'<{_LOGO_CID}>')
        img.add_header('Content-Disposition', 'inline', filename='logo_ingesam.png')
        related.attach(img)
    except Exception:
        pass


def _cabecera(subtitulo: str = '', con_logo: bool = False) -> str:
    if con_logo:
        cuerpo_header = f"""
      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%">
        <tr>
          <td style="width:60px;vertical-align:middle">
            <img src="cid:{_LOGO_CID}" width="54" height="54" alt="INGESAM"
                 style="display:block;border-radius:50%;background:#fff;padding:3px">
          </td>
          <td style="vertical-align:middle;padding-left:14px">
            <div style="color:#fff;font-size:18px;font-weight:bold;letter-spacing:0.4px">
              INGESAM ASEO S.A.S E.S.P.</div>
            <div style="color:{_VERDE_TXT};font-size:11px;margin-top:3px">
              Servicio Público de Aseo &nbsp;·&nbsp; Hatonuevo, La Guajira</div>
          </td>
        </tr>
      </table>"""
    else:
        cuerpo_header = f"""
      <div style="color:#fff;font-size:19px;font-weight:bold;letter-spacing:0.5px;
                  margin-bottom:5px">INGESAM ASEO S.A.S E.S.P.</div>
      <div style="color:{_VERDE_TXT};font-size:12px;letter-spacing:0.3px">
        Servicio Público de Aseo &nbsp;·&nbsp; Hatonuevo, La Guajira</div>"""

    banda_sub = (f'<div style="background:{_VERDE_OSC};padding:9px 28px">'
                 f'<span style="color:{_VERDE_TXT};font-size:12px;font-weight:bold;'
                 f'letter-spacing:1px;text-transform:uppercase">{subtitulo}</span></div>'
                 if subtitulo else '')
    return f"""
    <div style="background:{_VERDE};padding:20px 28px 16px 28px">
      {cuerpo_header}
    </div>
    {banda_sub}"""


def _pie() -> str:
    return f"""
    <div style="background:{_VERDE_OSC};padding:12px 28px;text-align:center">
      <p style="color:rgba(255,255,255,0.65);font-size:10px;margin:0;line-height:1.6">
        INGESAM ASEO S.A.S E.S.P. · Hatonuevo, La Guajira · Tel: +57 300 285 3547<br>
        <a href="mailto:pqringesamaseo@gmail.com"
           style="color:rgba(255,255,255,0.85);text-decoration:none">
          pqringesamaseo@gmail.com</a><br>
        Generado automáticamente por Sistema RECIVA
      </p>
    </div>"""


def _envolver(contenido: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;background:#EFEFEF">
  <div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;
              border-radius:8px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.13)">
    {contenido}
  </div>
</body></html>"""


# ── PQR ──────────────────────────────────────────────────────────────────────
def enviar_respuesta_pqr(destinatario, nombre_destinatario,
                         pqr_id, asunto_original, mensaje):
    """
    Envía la respuesta de una PQR al correo del solicitante.
    Retorna (True, '') en éxito o (False, mensaje_error) en fallo.
    """
    cfg = SMTP_CONFIG
    if not cfg.get('password'):
        return False, 'Contraseña SMTP no configurada. Revisa config.py.'

    try:
        tiene_logo = _logo_disponible()

        msg = MIMEMultipart('mixed')
        msg['Subject'] = f'Respuesta a su PQR #{pqr_id} — {asunto_original}'
        msg['From']    = f"INGESAM ASEO <{cfg['user']}>"
        msg['To']      = destinatario

        cuerpo_txt = (
            f"Estimado/a {nombre_destinatario},\n\n"
            f"En respuesta a su solicitud PQR #{pqr_id} ({asunto_original}):\n\n"
            f"{mensaje}\n\n"
            f"Atentamente,\n"
            f"INGESAM ASEO S.A.S E.S.P.\n"
            f"Hatonuevo, La Guajira\n"
            f"Tel: +57 300 285 3547\n"
            f"pqringesamaseo@gmail.com"
        )

        cuerpo_html = _envolver(f"""
    {_cabecera(f'Respuesta a PQR #{pqr_id}', con_logo=tiene_logo)}
    <div style="background:#fff;padding:28px 32px">
      <p style="color:{_TEXTO};font-size:14px;margin:0 0 10px">
        Estimado/a <strong>{nombre_destinatario}</strong>,
      </p>
      <p style="color:#555;font-size:13px;margin:0 0 18px">
        Hemos atendido su solicitud <strong>PQR #{pqr_id}</strong>
        referente a: <em>{asunto_original}</em>
      </p>
      <div style="background:{_VERDE_CLARO};border-left:4px solid {_VERDE};
                  border-radius:0 6px 6px 0;padding:16px 20px;margin:0 0 22px">
        <p style="color:{_TEXTO};margin:0;font-size:13px;line-height:1.75;
                  white-space:pre-line">{mensaje}</p>
      </div>
      <p style="color:{_MUTED};font-size:12px;margin:0;padding-top:16px;
                border-top:1px solid {_LINE}">
        Atentamente,<br>
        <strong style="color:{_TEXTO}">INGESAM ASEO S.A.S E.S.P.</strong><br>
        Hatonuevo, La Guajira · Tel: +57 300 285 3547<br>
        <a href="mailto:pqringesamaseo@gmail.com"
           style="color:{_VERDE};text-decoration:none">pqringesamaseo@gmail.com</a>
      </p>
    </div>
    {_pie()}""")

        # Estructura: mixed > related > alternative + imagen CID
        related = MIMEMultipart('related')
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(cuerpo_txt, 'plain', 'utf-8'))
        alt.attach(MIMEText(cuerpo_html, 'html',  'utf-8'))
        related.attach(alt)
        if tiene_logo:
            _adjuntar_logo(related)
        msg.attach(related)

        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], destinatario, msg.as_string())

        return True, ''

    except smtplib.SMTPAuthenticationError:
        return False, 'Error de autenticación. Verifica la contraseña de aplicación en config.py.'
    except smtplib.SMTPException as e:
        return False, f'Error SMTP: {e}'
    except Exception as e:
        return False, f'Error inesperado: {e}'


# ── Volcado ───────────────────────────────────────────────────────────────────
def enviar_volcado(destinatarios, periodo_texto: str, archivos: list, smtp_cfg=None) -> tuple:
    """
    Envía los archivos volcado (5 adjuntos) a uno o varios destinatarios.
    destinatarios: str (un correo o varios separados por coma/salto de línea) o lista.
    smtp_cfg: dict opcional con 'user' y/o 'password' para sobreescribir SMTP_CONFIG.
    Retorna (True, '') en éxito o (False, mensaje_error) en fallo.
    """
    cfg = _resolve_smtp(smtp_cfg)
    if not cfg.get('password'):
        return False, 'Contraseña SMTP no configurada. Ve a Volcado → ✉ Correo.'

    lista_dest = _parse_destinatarios(destinatarios)
    if not lista_dest:
        return False, 'No hay destinatarios configurados.'

    try:
        tiene_logo = _logo_disponible()

        msg = MIMEMultipart('mixed')
        msg['Subject'] = f'Volcado INGESAM ASEO — {periodo_texto}'
        msg['From']    = f"INGESAM ASEO <{cfg['user']}>"
        msg['To']      = ', '.join(lista_dest)

        cuerpo_txt = (
            f"Estimados,\n\n"
            f"Adjunto los archivos de volcado correspondientes al período {periodo_texto}:\n\n"
            + '\n'.join(f"  • {os.path.basename(a)}" for a in archivos) +
            f"\n\nAtentamente,\n"
            f"INGESAM ASEO S.A.S E.S.P.\n"
            f"Hatonuevo, La Guajira\n"
            f"Tel: +57 300 285 3547"
        )

        filas_archivos = ''.join(
            f'<tr style="border-bottom:1px solid {_LINE}">'
            f'<td style="padding:9px 16px;color:{_TEXTO};font-size:13px">'
            f'&#128196; {os.path.basename(a)}</td></tr>'
            for a in archivos if os.path.exists(a)
        )

        cuerpo_html = _envolver(f"""
    {_cabecera(f'Volcado período {periodo_texto}', con_logo=tiene_logo)}
    <div style="background:#fff;padding:28px 32px">
      <p style="color:{_TEXTO};font-size:14px;margin:0 0 10px">Estimados,</p>
      <p style="color:#555;font-size:13px;margin:0 0 20px">
        Se adjuntan los archivos de volcado correspondientes al período
        <strong>{periodo_texto}</strong> para su procesamiento en el sistema AIR-E.
      </p>
      <div style="border:1px solid {_LINE};border-radius:6px;overflow:hidden;margin:0 0 22px">
        <div style="background:{_VERDE_CLARO};padding:10px 16px;border-bottom:1px solid {_LINE}">
          <span style="color:{_VERDE};font-weight:bold;font-size:11px;
                       text-transform:uppercase;letter-spacing:0.6px">
            Archivos adjuntos</span>
        </div>
        <table style="width:100%;border-collapse:collapse">
          {filas_archivos}
        </table>
      </div>
      <p style="color:{_MUTED};font-size:12px;margin:0;padding-top:16px;
                border-top:1px solid {_LINE}">
        Atentamente,<br>
        <strong style="color:{_TEXTO}">INGESAM ASEO S.A.S E.S.P.</strong><br>
        Hatonuevo, La Guajira · Tel: +57 300 285 3547
      </p>
    </div>
    {_pie()}""")

        # Estructura: mixed > related > alternative + imagen CID | adjuntos de volcado
        related = MIMEMultipart('related')
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(cuerpo_txt, 'plain', 'utf-8'))
        alt.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))
        related.attach(alt)
        if tiene_logo:
            _adjuntar_logo(related)
        msg.attach(related)

        for ruta in archivos:
            if not os.path.exists(ruta):
                continue
            with open(ruta, 'rb') as fh:
                parte = MIMEBase('application', 'octet-stream')
                parte.set_payload(fh.read())
            encoders.encode_base64(parte)
            parte.add_header('Content-Disposition', 'attachment',
                             filename=os.path.basename(ruta))
            msg.attach(parte)

        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], lista_dest, msg.as_string())

        return True, ''

    except smtplib.SMTPAuthenticationError:
        return False, 'Error de autenticación SMTP. Verifica config.py.'
    except smtplib.SMTPException as e:
        return False, f'Error SMTP: {e}'
    except Exception as e:
        return False, f'Error inesperado: {e}'


# ── Credenciales nuevo usuario ────────────────────────────────────────────────
def enviar_credenciales(nombre: str, email: str, password_plain: str, rol: str,
                        smtp_cfg=None) -> tuple:
    """
    Envía las credenciales de acceso a un usuario recién creado.
    smtp_cfg: dict opcional con 'user'/'password' para sobreescribir SMTP_CONFIG.
    Retorna (True, '') en éxito o (False, mensaje_error) en fallo.
    """
    cfg = _resolve_smtp(smtp_cfg)
    if not cfg.get('password'):
        return False, 'Contraseña SMTP no configurada. Ve a Volcado → ✉ Correo.'

    try:
        tiene_logo = _logo_disponible()

        msg = MIMEMultipart('mixed')
        msg['Subject'] = 'Bienvenido a RECIVA — Tus credenciales de acceso'
        msg['From']    = f"INGESAM ASEO <{cfg['user']}>"
        msg['To']      = email

        cuerpo_txt = (
            f"Hola {nombre},\n\n"
            f"Tu cuenta en el sistema RECIVA de INGESAM ASEO ha sido creada.\n\n"
            f"Credenciales de acceso:\n"
            f"  Correo:      {email}\n"
            f"  Contraseña:  {password_plain}\n"
            f"  Rol:         {rol.title()}\n\n"
            f"Por seguridad, te recomendamos cambiar tu contraseña en el primer inicio de sesión.\n\n"
            f"Atentamente,\n"
            f"INGESAM ASEO S.A.S E.S.P.\n"
            f"Hatonuevo, La Guajira · Tel: +57 300 285 3547"
        )

        cuerpo_html = _envolver(f"""
    {_cabecera('Bienvenido a RECIVA', con_logo=tiene_logo)}
    <div style="background:#fff;padding:28px 32px">
      <p style="color:{_TEXTO};font-size:14px;margin:0 0 10px">
        Hola <strong>{nombre}</strong>,
      </p>
      <p style="color:#555;font-size:13px;margin:0 0 20px">
        Tu cuenta en el sistema de gestión <strong>RECIVA</strong> de INGESAM ASEO
        ha sido creada correctamente. A continuación tus credenciales de acceso:
      </p>
      <div style="background:{_VERDE_CLARO};border-left:4px solid {_VERDE};
                  border-radius:0 6px 6px 0;padding:18px 22px;margin:0 0 22px">
        <table style="width:100%;border-collapse:collapse">
          <tr>
            <td style="color:{_MUTED};font-size:12px;padding:5px 0;width:110px;
                       vertical-align:top"><strong>Correo</strong></td>
            <td style="color:{_TEXTO};font-size:13px;padding:5px 0">{email}</td>
          </tr>
          <tr>
            <td style="color:{_MUTED};font-size:12px;padding:5px 0;vertical-align:top">
              <strong>Contraseña</strong></td>
            <td style="color:{_TEXTO};font-size:14px;padding:5px 0;
                       font-family:monospace;letter-spacing:1.5px;font-weight:bold">
              {password_plain}</td>
          </tr>
          <tr>
            <td style="color:{_MUTED};font-size:12px;padding:5px 0;vertical-align:top">
              <strong>Rol</strong></td>
            <td style="color:{_TEXTO};font-size:13px;padding:5px 0">{rol.title()}</td>
          </tr>
        </table>
      </div>
      <p style="color:{_MUTED};font-size:12px;margin:0 0 20px">
        &#128274; Por seguridad te recomendamos cambiar tu contraseña en el primer inicio de sesión.
      </p>
      <p style="color:{_MUTED};font-size:12px;margin:0;padding-top:16px;
                border-top:1px solid {_LINE}">
        Atentamente,<br>
        <strong style="color:{_TEXTO}">INGESAM ASEO S.A.S E.S.P.</strong><br>
        Hatonuevo, La Guajira · Tel: +57 300 285 3547<br>
        <a href="mailto:pqringesamaseo@gmail.com"
           style="color:{_VERDE};text-decoration:none">pqringesamaseo@gmail.com</a>
      </p>
    </div>
    {_pie()}""")

        related = MIMEMultipart('related')
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(cuerpo_txt, 'plain', 'utf-8'))
        alt.attach(MIMEText(cuerpo_html, 'html',  'utf-8'))
        related.attach(alt)
        if tiene_logo:
            _adjuntar_logo(related)
        msg.attach(related)

        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], email, msg.as_string())

        return True, ''

    except smtplib.SMTPAuthenticationError:
        return False, 'Error de autenticación SMTP. Verifica config.py.'
    except smtplib.SMTPException as e:
        return False, f'Error SMTP: {e}'
    except Exception as e:
        return False, f'Error inesperado: {e}'
