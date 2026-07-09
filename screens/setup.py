"""
Wizard de primer uso — se muestra cuando no hay reciva.ini o primer_uso=true.
4 pasos: Conexion BD -> Empresa -> Modulos -> SMTP (opcional)
"""

import os
import threading

import pymysql
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from theme import (TINTA, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, SUCCESS, DANGER)
from widgets.components import PillButton
from utils.licencia import verificar_codigo, LicenciaError


# ── Helpers de UI ─────────────────────────────────────────────────────────────

def _mk_bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        r = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda w, v, rect=r: setattr(rect, 'pos', v),
        size=lambda w, v, rect=r: setattr(rect, 'size', v),
    )


def _lbl(text, size=13, bold=False, color=None, halign='left', height=26):
    lbl = Label(
        text=text, font_name='Jakarta', font_size=size, bold=bold,
        color=color or TINTA, halign=halign, valign='middle',
        size_hint_y=None, height=height,
    )
    lbl.bind(size=lambda w, _: setattr(w, 'text_size', w.size))
    return lbl


def _field(hint='', password=False, text=''):
    wrap = BoxLayout(size_hint_y=None, height=44)
    with wrap.canvas.before:
        Color(1, 1, 1, 1)
        bg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
        Color(*LINE)
        bd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
    wrap.bind(
        pos =lambda _, v, a=bg, b=bd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
        size=lambda _, v, a=bg, b=bd: (setattr(a, 'size', v), setattr(b, 'size', v)),
    )
    ti = TextInput(
        text=text, hint_text=hint, multiline=False, password=password,
        font_name='Jakarta', font_size=13,
        background_normal='', background_active='', background_color=(0, 0, 0, 0),
        foreground_color=TINTA, cursor_color=VERMILLON,
        hint_text_color=MUTED, padding=[14, 12],
    )
    wrap.add_widget(ti)
    return wrap, ti


# ── Card base ─────────────────────────────────────────────────────────────────

class _Paso(BoxLayout):
    def __init__(self, titulo, subtitulo, **kw):
        super().__init__(orientation='vertical', **kw)
        _mk_bg(self, CARD)

        hdr = BoxLayout(orientation='vertical', size_hint_y=None, height=80, padding=[28, 10])
        _mk_bg(hdr, TINTA)
        row_t = BoxLayout(size_hint_y=None, height=36)
        row_t.add_widget(_lbl(titulo, size=18, bold=True, color=(1, 1, 1, 1), height=36))
        hdr.add_widget(row_t)
        row_s = BoxLayout(size_hint_y=None, height=22)
        row_s.add_widget(_lbl(subtitulo, size=11, color=(0.78, 0.82, 0.87, 1), height=22))
        hdr.add_widget(row_s)
        self.add_widget(hdr)

        self.body = BoxLayout(orientation='vertical', padding=[28, 18], spacing=8,
                              size_hint_y=1)
        self.add_widget(self.body)

        self.footer = BoxLayout(size_hint_y=None, height=64, padding=[28, 12], spacing=12)
        _mk_bg(self.footer, STAGE)
        self.add_widget(self.footer)

    def _add_field(self, hint, attr, default='', password=False):
        self.body.add_widget(_lbl(hint, size=11, color=MUTED, height=18))
        wrap, ti = _field(hint, password=password, text=default)
        setattr(self, attr, ti)
        self.body.add_widget(wrap)
        return ti

    def _btn_back(self, on_back):
        btn = PillButton(text='<  Atras', bg_color=LINE, fg_color=TINTA,
                         pressed_color=STAGE, font_size=13, pill_radius=20,
                         size_hint_x=None, width=120)
        btn.bind(on_press=lambda _: on_back())
        return btn

    def _btn_next(self, text, on_press, color=None, width=140):
        btn = PillButton(text=text, bg_color=color or VERMILLON,
                         pressed_color=LADRILLO, font_size=13, pill_radius=20,
                         size_hint_x=None, width=width)
        btn.bind(on_press=on_press)
        return btn


# ── Paso 1 — Codigo de activacion ────────────────────────────────────────────

class _Paso1(_Paso):
    def __init__(self, on_ok, **kw):
        super().__init__('Activacion de Reciva',
                         'Pega el codigo de activacion que te dio tu proveedor', **kw)
        self._on_ok = on_ok

        self.body.add_widget(_lbl(
            'El codigo contiene los datos de conexion cifrados. '
            'Tiene aproximadamente 200 caracteres.',
            size=12, color=MUTED, height=38,
        ))
        self.body.add_widget(Widget(size_hint_y=None, height=8))

        self.body.add_widget(_lbl('Codigo de activacion', size=11, color=MUTED, height=18))
        wrap = BoxLayout(size_hint_y=None, height=90)
        with wrap.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
            Color(*LINE)
            bd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
        wrap.bind(
            pos =lambda _, v, a=bg, b=bd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
            size=lambda _, v, a=bg, b=bd: (setattr(a, 'size', v), setattr(b, 'size', v)),
        )
        self.ti_codigo = TextInput(
            hint_text='gAAAAAB...  (pega aqui el codigo completo)',
            multiline=True, font_name='Jakarta', font_size=12,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=VERMILLON,
            hint_text_color=MUTED, padding=[14, 12],
        )
        wrap.add_widget(self.ti_codigo)
        self.body.add_widget(wrap)

        self.lbl_err = _lbl('', size=12, color=DANGER, height=22)
        self.body.add_widget(self.lbl_err)
        self.body.add_widget(Widget())

        self.btn_ok = self._btn_next('Activar  ->', self._activar, width=160)
        self.footer.add_widget(Widget())
        self.footer.add_widget(self.btn_ok)

    def _activar(self, *_):
        codigo = self.ti_codigo.text.strip()
        if not codigo:
            self._err('Pega el codigo de activacion')
            return
        self.btn_ok.disabled = True
        self.lbl_err.color = MUTED
        self.lbl_err.text = 'Verificando codigo...'
        threading.Thread(target=self._tarea, args=(codigo,), daemon=True).start()

    def _tarea(self, codigo):
        try:
            creds = verificar_codigo(codigo)
        except LicenciaError as e:
            Clock.schedule_once(lambda *_, m=str(e): self._err(m), 0)
            return
        except Exception as e:
            Clock.schedule_once(lambda *_, m=str(e): self._err(f'Error inesperado: {m}'), 0)
            return

        host     = creds['host']
        port     = int(creds['port'])
        name     = creds['database']
        user     = creds['user']
        pwd      = creds['password']
        cliente  = creds.get('cliente', '')

        self.lbl_err.text = f'Codigo valido ({cliente}). Conectando...' if cliente else 'Codigo valido. Conectando...'

        try:
            conn = pymysql.connect(
                host=host, port=port, user=user, password=pwd,
                ssl={'ssl_verify_cert': False}, connect_timeout=10,
            )
            cur = conn.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cur.close()
            conn.close()

            conn2 = pymysql.connect(
                host=host, port=port, user=user, password=pwd, database=name,
                ssl={'ssl_verify_cert': False}, connect_timeout=10,
            )
            self._crear_tablas(conn2)
            conn2.close()

            Clock.schedule_once(lambda *_: self._on_ok(host, port, name, user, pwd), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_, m=str(e): self._err(f'Conexion fallida: {m}'), 0)

    def _crear_tablas(self, conn):
        import sys
        base = getattr(sys, '_MEIPASS',
                       os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sql_path = os.path.join(base, 'setup_db.sql')
        cur = conn.cursor()
        with open(sql_path, encoding='utf-8') as f:
            raw = f.read()
        for stmt in raw.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
        conn.commit()
        cur.close()

    def _err(self, msg):
        self.btn_ok.disabled = False
        self.lbl_err.color = DANGER
        self.lbl_err.text = msg


# ── Paso 2 — Empresa ──────────────────────────────────────────────────────────

class _Paso2(_Paso):
    def __init__(self, on_ok, on_back, **kw):
        super().__init__('Informacion de la empresa',
                         'Estos datos aparecen en reportes y archivos generados', **kw)
        self._on_ok = on_ok

        self._add_field('Nombre de la empresa', 'ti_nombre')
        self._add_field('NIT / RUT (opcional)',  'ti_nit')

        self.lbl_err = _lbl('', size=12, color=DANGER, height=22)
        self.body.add_widget(self.lbl_err)
        self.body.add_widget(Widget())

        self.footer.add_widget(Widget())
        self.footer.add_widget(self._btn_back(on_back))
        self.footer.add_widget(self._btn_next('Siguiente  ->', self._siguiente))

    def _siguiente(self, *_):
        nombre = self.ti_nombre.text.strip()
        if not nombre:
            self.lbl_err.text = 'El nombre de la empresa es obligatorio'
            return
        self.lbl_err.text = ''
        self._on_ok(nombre, self.ti_nit.text.strip())


# ── Paso 3 — Modulos ──────────────────────────────────────────────────────────

_MODULOS = [
    ('clientes',     'Clientes / Suscriptores',           True),
    ('cobros',       'Cobros / Facturacion',               True),
    ('pagos',        'Pagos / Recaudos',                   True),
    ('soporte',      'Soporte / PQR / Tickets',            True),
    ('estadisticas', 'Estadisticas',                       True),
    ('volcado',      'Volcado AIR-E  (servicios publicos)', False),
]


class _Paso3(_Paso):
    def __init__(self, on_ok, on_back, **kw):
        super().__init__('Modulos activos',
                         'Activa solo los modulos que tu negocio necesita', **kw)
        self._on_ok = on_ok
        self._checks = {}

        for key, texto, default in _MODULOS:
            row = BoxLayout(size_hint_y=None, height=40, spacing=12)
            cb = CheckBox(active=default, size_hint=(None, None), size=(28, 28),
                          color=VERMILLON)
            lbl = _lbl(texto, size=13, height=40)
            row.add_widget(cb)
            row.add_widget(lbl)
            self.body.add_widget(row)
            self._checks[key] = cb

        self.body.add_widget(Widget())
        self.footer.add_widget(Widget())
        self.footer.add_widget(self._btn_back(on_back))
        self.footer.add_widget(self._btn_next('Siguiente  ->', self._siguiente))

    def _siguiente(self, *_):
        activos = ','.join(k for k, cb in self._checks.items() if cb.active)
        self._on_ok(activos)


# ── Paso 4 — SMTP ─────────────────────────────────────────────────────────────

class _Paso4(_Paso):
    def __init__(self, on_ok, on_back, **kw):
        super().__init__('Correo SMTP (opcional)',
                         'Para enviar notificaciones y volcados por correo', **kw)
        self._on_ok = on_ok

        self.body.add_widget(_lbl(
            'Puedes omitir esto y configurarlo despues en Ajustes.',
            size=12, color=MUTED, height=24,
        ))
        self.body.add_widget(Widget(size_hint_y=None, height=8))
        self._add_field('Correo emisor (ej: empresa@gmail.com)', 'ti_user')
        self._add_field('Contrasena de aplicacion', 'ti_pass', password=True)
        self.body.add_widget(Widget())

        btn_skip = self._btn_next('Omitir', lambda _: self._on_ok('', ''),
                                  color=STAGE, width=100)
        btn_fin  = self._btn_next('Finalizar  v', self._finalizar,
                                  color=SUCCESS, width=140)
        self.footer.add_widget(Widget())
        self.footer.add_widget(self._btn_back(on_back))
        self.footer.add_widget(btn_skip)
        self.footer.add_widget(btn_fin)

    def _finalizar(self, *_):
        self._on_ok(self.ti_user.text.strip(), self.ti_pass.text.strip())


# ── Screen principal ──────────────────────────────────────────────────────────

class SetupScreen(Screen):
    _db_params: dict = {}
    _empresa:   dict = {}
    _modulos:   str  = ''

    def on_enter(self):
        self._ir_paso(1)

    def _ir_paso(self, paso):
        self.clear_widgets()
        kw = dict(size_hint=(1, 1))
        if paso == 1:
            self.add_widget(_Paso1(on_ok=self._ok1, **kw))
        elif paso == 2:
            self.add_widget(_Paso2(on_ok=self._ok2,
                                   on_back=lambda: self._ir_paso(1), **kw))
        elif paso == 3:
            self.add_widget(_Paso3(on_ok=self._ok3,
                                   on_back=lambda: self._ir_paso(2), **kw))
        elif paso == 4:
            self.add_widget(_Paso4(on_ok=self._ok4,
                                   on_back=lambda: self._ir_paso(3), **kw))

    def _ok1(self, host, port, name, user, pwd):
        self._db_params = dict(host=host, port=port, database=name,
                               user=user, password=pwd)
        import config
        config.guardar_ini(db=self._db_params)
        config.reload_db_config(host, port, user, pwd, name)
        self._ir_paso(2)

    def _ok2(self, nombre, nit):
        self._empresa = dict(empresa_nombre=nombre, empresa_nit=nit or '')
        self._ir_paso(3)

    def _ok3(self, modulos):
        self._modulos = modulos
        self._ir_paso(4)

    def _ok4(self, smtp_user, smtp_pass):
        threading.Thread(target=self._guardar, args=(smtp_user, smtp_pass),
                         daemon=True).start()

    def _guardar(self, smtp_user, smtp_pass):
        try:
            import config
            from db.connection import get_connection
            from utils import config_sistema

            if smtp_user:
                config.guardar_ini(smtp=dict(
                    host='smtp.gmail.com', port=587,
                    user=smtp_user, password=smtp_pass,
                ))

            conn = get_connection()
            if conn:
                try:
                    cambios = dict(self._empresa)
                    cambios['modulos_activos'] = self._modulos
                    cambios['empresa_logo'] = ''
                    config_sistema.set_many(cambios)
                finally:
                    conn.close()

            config.marcar_configurado()

            app = App.get_running_app()
            if hasattr(app, 'empresa_nombre'):
                app.empresa_nombre = self._empresa.get('empresa_nombre', '')

        except Exception as e:
            print(f'[Setup] Error al guardar: {e}')
        finally:
            Clock.schedule_once(lambda *_: self._ir_login(), 0)

    def _ir_login(self):
        self.manager.current = 'login'
