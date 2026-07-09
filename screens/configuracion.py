"""
Pantalla de Configuracion — solo visible para superadmin.
Tabs: Empresa | Etiquetas | Modulos | Volcado AIR-E | Correo SMTP | Conexion BD
"""

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from theme import (TINTA, BG, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, TEXT_SEC, SUCCESS, DANGER, WARNING)
from widgets.components import PillButton


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


def _field(hint='', text='', password=False, readonly=False):
    wrap = BoxLayout(size_hint_y=None, height=44)
    bg_col = STAGE if readonly else (1, 1, 1, 1)
    with wrap.canvas.before:
        Color(*bg_col)
        bg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
        Color(*LINE)
        bd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
    wrap.bind(
        pos =lambda _, v, a=bg, b=bd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
        size=lambda _, v, a=bg, b=bd: (setattr(a, 'size', v), setattr(b, 'size', v)),
    )
    ti = TextInput(
        text=text, hint_text=hint, multiline=False, password=password,
        readonly=readonly, font_name='Jakarta', font_size=13,
        background_normal='', background_active='', background_color=(0, 0, 0, 0),
        foreground_color=TINTA, cursor_color=VERMILLON,
        hint_text_color=MUTED, padding=[14, 12],
    )
    wrap.add_widget(ti)
    return wrap, ti


def _section(text, parent):
    parent.add_widget(_lbl(text, size=10, bold=True, color=MUTED, height=20))


def _divider(parent):
    div = BoxLayout(size_hint_y=None, height=1)
    with div.canvas.before:
        Color(*LINE)
        r = Rectangle(pos=div.pos, size=div.size)
    div.bind(pos=lambda _, v, rect=r: setattr(rect, 'pos', v),
             size=lambda _, v, rect=r: setattr(rect, 'size', v))
    parent.add_widget(div)


# ── Tabs ──────────────────────────────────────────────────────────────────────

_TABS = ['Empresa', 'Etiquetas', 'Modulos', 'Volcado', 'SMTP', 'Conexion BD']


class ConfiguracionScreen(Screen):
    _tab_activa = 'Empresa'
    _cfg: dict = {}

    def on_enter(self):
        threading.Thread(target=self._cargar, daemon=True).start()

    def _cargar(self):
        try:
            from utils.config_sistema import get_all
            cfg = get_all()
        except Exception:
            cfg = {}
        self._cfg = cfg
        Clock.schedule_once(lambda *_: self._construir(), 0)

    # ── Layout principal ──────────────────────────────────────────────────────

    def _construir(self):
        self.clear_widgets()

        root = BoxLayout(orientation='horizontal')
        _mk_bg(root, BG)

        # Panel de tabs (vertical, izq)
        tab_panel = BoxLayout(
            orientation='vertical', size_hint_x=None, width=160,
            padding=[0, 12], spacing=0,
        )
        _mk_bg(tab_panel, CARD)

        tab_panel.add_widget(_lbl('Ajustes', size=14, bold=True,
                                  color=TINTA, height=36,
                                  halign='center'))
        _divider(tab_panel)

        self._tab_btns = {}
        for nombre in _TABS:
            btn = PillButton(
                text=nombre, font_size=12,
                bg_color=VERMILLON if nombre == self._tab_activa else (0, 0, 0, 0),
                fg_color=(1, 1, 1, 1) if nombre == self._tab_activa else TINTA,
                pressed_color=LADRILLO,
                size_hint_y=None, height=44, pill_radius=0,
            )
            btn.bind(on_press=lambda _, n=nombre: self._cambiar_tab(n))
            tab_panel.add_widget(btn)
            self._tab_btns[nombre] = btn

        tab_panel.add_widget(Widget())
        root.add_widget(tab_panel)

        # Divisor
        div = Widget(size_hint_x=None, width=1)
        _mk_bg(div, LINE)
        root.add_widget(div)

        # Panel de contenido
        self._contenido = BoxLayout(orientation='vertical', padding=[28, 20], spacing=12)
        _mk_bg(self._contenido, BG)
        root.add_widget(self._contenido)

        self.add_widget(root)
        self._mostrar_tab(self._tab_activa)

    def _cambiar_tab(self, nombre):
        for n, btn in self._tab_btns.items():
            activo = n == nombre
            btn.bg_color = VERMILLON if activo else (0, 0, 0, 0)
            btn.fg_color = (1, 1, 1, 1) if activo else TINTA
        self._tab_activa = nombre
        self._mostrar_tab(nombre)

    def _mostrar_tab(self, nombre):
        self._contenido.clear_widgets()
        if nombre == 'Empresa':
            self._tab_empresa()
        elif nombre == 'Etiquetas':
            self._tab_etiquetas()
        elif nombre == 'Modulos':
            self._tab_modulos()
        elif nombre == 'Volcado':
            self._tab_volcado()
        elif nombre == 'SMTP':
            self._tab_smtp()
        elif nombre == 'Conexion BD':
            self._tab_conexion()

    # ── Tab Empresa ───────────────────────────────────────────────────────────

    def _tab_empresa(self):
        c = self._contenido
        c.add_widget(_lbl('Empresa', size=18, bold=True, height=36))
        _divider(c)

        fields = {}
        for label, key in [
            ('Nombre de la empresa', 'empresa_nombre'),
            ('NIT / RUT',            'empresa_nit'),
        ]:
            c.add_widget(_lbl(label, size=11, color=MUTED, height=18))
            wrap, ti = _field(label, text=self._cfg.get(key, ''))
            fields[key] = ti
            c.add_widget(wrap)

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row.add_widget(Widget())
        btn = PillButton(text='Guardar cambios', bg_color=SUCCESS,
                         pressed_color=(0.09, 0.40, 0.16, 1),
                         font_size=13, pill_radius=20,
                         size_hint_x=None, width=180)

        def _guardar(_):
            cambios = {k: ti.text.strip() for k, ti in fields.items()}
            lbl_ok.text = 'Guardando...'
            lbl_ok.color = MUTED
            threading.Thread(target=self._guardar_cfg, args=(cambios, lbl_ok, 'Empresa'),
                             daemon=True).start()

        btn.bind(on_press=_guardar)
        row.add_widget(btn)
        c.add_widget(row)

    # ── Tab Etiquetas ─────────────────────────────────────────────────────────

    def _tab_etiquetas(self):
        c = self._contenido
        c.add_widget(_lbl('Etiquetas de modulos', size=18, bold=True, height=36))
        c.add_widget(_lbl('Personaliza los nombres que ven los usuarios en el menu',
                          size=12, color=MUTED, height=22))
        _divider(c)

        labels_info = [
            ('Clientes',           'label_clientes',   'Clientes, Suscriptores, Arrendatarios...'),
            ('Cobros',             'label_cobros',      'Cobros, Facturas, Cuotas, Mensualidades...'),
            ('Pagos',              'label_pagos',       'Pagos, Abonos, Ingresos, Recaudos...'),
            ('Soporte',            'label_soporte',     'Soporte, PQR, Tickets, Solicitudes...'),
            ('ID del cliente',     'label_id_cliente',  'Codigo, NIC, Cedula, Matricula...'),
        ]
        fields = {}
        for etiq, key, hint in labels_info:
            row = BoxLayout(size_hint_y=None, height=44, spacing=12)
            lbl_e = _lbl(etiq, size=12, height=44)
            lbl_e.size_hint_x = 0.28
            wrap, ti = _field(hint, text=self._cfg.get(key, ''))
            fields[key] = ti
            row.add_widget(lbl_e)
            row.add_widget(wrap)
            c.add_widget(row)

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row_btn = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row_btn.add_widget(Widget())
        btn = PillButton(text='Guardar etiquetas', bg_color=SUCCESS,
                         pressed_color=(0.09, 0.40, 0.16, 1),
                         font_size=13, pill_radius=20,
                         size_hint_x=None, width=180)

        def _guardar(_):
            cambios = {k: ti.text.strip() for k, ti in fields.items()}
            threading.Thread(target=self._guardar_cfg, args=(cambios, lbl_ok, 'Etiquetas'),
                             daemon=True).start()

        btn.bind(on_press=_guardar)
        row_btn.add_widget(btn)
        c.add_widget(row_btn)

    # ── Tab Modulos ───────────────────────────────────────────────────────────

    def _tab_modulos(self):
        c = self._contenido
        c.add_widget(_lbl('Modulos activos', size=18, bold=True, height=36))
        c.add_widget(_lbl('Los modulos desactivados desaparecen del menu lateral',
                          size=12, color=MUTED, height=22))
        _divider(c)

        activos = {m.strip() for m in self._cfg.get('modulos_activos', '').split(',') if m.strip()}
        modulos = [
            ('clientes',     'Clientes / Suscriptores'),
            ('cobros',       'Cobros / Facturacion'),
            ('pagos',        'Pagos / Recaudos'),
            ('soporte',      'Soporte / PQR / Tickets'),
            ('estadisticas', 'Estadisticas'),
            ('volcado',      'Volcado AIR-E'),
        ]
        checks = {}
        for key, texto in modulos:
            row = BoxLayout(size_hint_y=None, height=44, spacing=12)
            cb = CheckBox(active=(key in activos),
                          size_hint=(None, None), size=(28, 28), color=VERMILLON)
            row.add_widget(cb)
            row.add_widget(_lbl(texto, size=13, height=44))
            c.add_widget(row)
            checks[key] = cb

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row_btn = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row_btn.add_widget(Widget())
        btn = PillButton(text='Guardar modulos', bg_color=SUCCESS,
                         pressed_color=(0.09, 0.40, 0.16, 1),
                         font_size=13, pill_radius=20,
                         size_hint_x=None, width=180)

        def _guardar(_):
            activos_new = ','.join(k for k, cb in checks.items() if cb.active)
            self._cfg['modulos_activos'] = activos_new

            def _bg():
                from utils import config_sistema
                try:
                    config_sistema.set('modulos_activos', activos_new)
                    app = App.get_running_app()
                    if hasattr(app, 'perm_volcado'):
                        app.perm_volcado = (
                            app.perm_volcado and 'volcado' in activos_new
                        )
                    Clock.schedule_once(lambda *_: (
                        setattr(lbl_ok, 'text', 'Modulos guardados'),
                        setattr(lbl_ok, 'color', SUCCESS),
                    ), 0)
                except Exception as e:
                    msg = str(e)
                    Clock.schedule_once(lambda *_, m=msg: (
                        setattr(lbl_ok, 'text', f'Error: {m}'),
                        setattr(lbl_ok, 'color', DANGER),
                    ), 0)

            threading.Thread(target=_bg, daemon=True).start()

        btn.bind(on_press=_guardar)
        row_btn.add_widget(btn)
        c.add_widget(row_btn)

    # ── Tab Volcado ───────────────────────────────────────────────────────────

    def _tab_volcado(self):
        c = self._contenido
        c.add_widget(_lbl('Volcado AIR-E', size=18, bold=True, height=36))
        c.add_widget(_lbl('Configuracion especifica para el volcado de servicios publicos',
                          size=12, color=MUTED, height=22))
        _divider(c)

        # Cargar valores desde config_volcado
        self._volcado_cfg = {}
        threading.Thread(target=self._cargar_volcado_cfg, daemon=True).start()

        fields = {}
        for label, key, default in [
            ('Sufijo del servicio (SUFIJO)', 'sufijo',   '1261'),
            ('Convenio AIR-E (CONVENIO)',    'convenio', '2087'),
            ('Email destino AIR-E',          'email_destino', ''),
        ]:
            c.add_widget(_lbl(label, size=11, color=MUTED, height=18))
            # Valor desde config_volcado se carga async, por ahora vacio
            wrap, ti = _field(label, text=default)
            fields[key] = ti
            c.add_widget(wrap)

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row_btn = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row_btn.add_widget(Widget())
        btn = PillButton(text='Guardar configuracion volcado', bg_color=SUCCESS,
                         pressed_color=(0.09, 0.40, 0.16, 1),
                         font_size=13, pill_radius=20,
                         size_hint_x=None, width=240)

        def _guardar(_):
            sufijo   = fields['sufijo'].text.strip()
            convenio = fields['convenio'].text.strip()
            email    = fields['email_destino'].text.strip()

            def _bg():
                from db.connection import get_connection
                from utils.volcado import guardar_config
                conn = get_connection()
                if not conn:
                    Clock.schedule_once(lambda *_: (
                        setattr(lbl_ok, 'text', 'Sin conexion'),
                        setattr(lbl_ok, 'color', DANGER),
                    ), 0)
                    return
                try:
                    cur = conn.cursor()
                    # Actualizar sufijo y convenio
                    for col, val in [('sufijo', sufijo), ('convenio', convenio)]:
                        cur.execute(
                            f"UPDATE config_volcado SET `{col}` = %s WHERE 1", (val,)
                        )
                    guardar_config(conn, None, email)
                    conn.commit()
                    cur.close()
                    Clock.schedule_once(lambda *_: (
                        setattr(lbl_ok, 'text', 'Guardado'),
                        setattr(lbl_ok, 'color', SUCCESS),
                    ), 0)
                except Exception as e:
                    msg = str(e)
                    Clock.schedule_once(lambda *_, m=msg: (
                        setattr(lbl_ok, 'text', f'Error: {m}'),
                        setattr(lbl_ok, 'color', DANGER),
                    ), 0)
                finally:
                    conn.close()

            threading.Thread(target=_bg, daemon=True).start()

        btn.bind(on_press=_guardar)
        row_btn.add_widget(btn)
        c.add_widget(row_btn)

    def _cargar_volcado_cfg(self):
        pass  # valores se cargan al entrar a la tab volcado en el futuro

    # ── Tab SMTP ──────────────────────────────────────────────────────────────

    def _tab_smtp(self):
        c = self._contenido
        c.add_widget(_lbl('Correo SMTP', size=18, bold=True, height=36))
        c.add_widget(_lbl('Cuenta de correo para enviar notificaciones',
                          size=12, color=MUTED, height=22))
        _divider(c)

        import config as _cfg
        ini = _cfg.get_db_config_from_ini()

        smtp_user = _cfg._ini_get('smtp', 'user', '')
        smtp_pass = _cfg._ini_get('smtp', 'pass', '')

        fields = {}
        for label, key, default, pwd in [
            ('Correo emisor',           'user', smtp_user, False),
            ('Contrasena de aplicacion', 'pass', smtp_pass, True),
        ]:
            c.add_widget(_lbl(label, size=11, color=MUTED, height=18))
            wrap, ti = _field(label, text=default, password=pwd)
            fields[key] = ti
            c.add_widget(wrap)

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row_btn = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row_btn.add_widget(Widget())
        btn = PillButton(text='Guardar SMTP', bg_color=SUCCESS,
                         pressed_color=(0.09, 0.40, 0.16, 1),
                         font_size=13, pill_radius=20,
                         size_hint_x=None, width=160)

        def _guardar(_):
            import config as _c
            _c.guardar_ini(smtp=dict(
                host='smtp.gmail.com', port=587,
                user=fields['user'].text.strip(),
                password=fields['pass'].text.strip(),
            ))
            lbl_ok.text = 'SMTP guardado en reciva.ini'
            lbl_ok.color = SUCCESS

        btn.bind(on_press=_guardar)
        row_btn.add_widget(btn)
        c.add_widget(row_btn)

    # ── Tab Conexion BD ───────────────────────────────────────────────────────

    def _tab_conexion(self):
        c = self._contenido
        c.add_widget(_lbl('Conexion a la base de datos', size=18, bold=True, height=36))
        c.add_widget(_lbl('Requiere reiniciar la aplicacion para aplicar cambios',
                          size=12, color=WARNING, height=22))
        _divider(c)

        import config as _cfg
        ini = _cfg.get_db_config_from_ini()
        fields = {}
        for label, key, pwd in [
            ('Host',      'host', False),
            ('Puerto',    'port', False),
            ('Base de datos', 'database', False),
            ('Usuario',   'user', False),
            ('Contrasena', 'password', True),
        ]:
            c.add_widget(_lbl(label, size=11, color=MUTED, height=18))
            wrap, ti = _field(label, text=ini.get(key, ''), password=pwd)
            fields[key] = ti
            c.add_widget(wrap)

        lbl_ok = _lbl('', size=12, height=22)
        c.add_widget(lbl_ok)
        c.add_widget(Widget())

        row_btn = BoxLayout(size_hint_y=None, height=48, spacing=12)
        row_btn.add_widget(Widget())
        btn = PillButton(text='Guardar y reiniciar', bg_color=WARNING,
                         pressed_color=LADRILLO, font_size=13, pill_radius=20,
                         size_hint_x=None, width=200)

        def _guardar(_):
            import config as _c
            new_db = {k: ti.text.strip() for k, ti in fields.items()}
            _c.guardar_ini(db=new_db)
            lbl_ok.text = 'Guardado en reciva.ini — reinicia la app para aplicar'
            lbl_ok.color = WARNING

        btn.bind(on_press=_guardar)
        row_btn.add_widget(btn)
        c.add_widget(row_btn)

    # ── Guardar config_sistema ────────────────────────────────────────────────

    def _guardar_cfg(self, cambios: dict, lbl_ok, context=''):
        from utils import config_sistema
        try:
            config_sistema.set_many(cambios)
            self._cfg.update(cambios)
            # Actualizar empresa_nombre en la app si se cambio
            if 'empresa_nombre' in cambios:
                app = App.get_running_app()
                if hasattr(app, 'empresa_nombre'):
                    Clock.schedule_once(
                        lambda *_, n=cambios['empresa_nombre']:
                            setattr(app, 'empresa_nombre', n), 0
                    )
            Clock.schedule_once(lambda *_: (
                setattr(lbl_ok, 'text', 'Guardado correctamente'),
                setattr(lbl_ok, 'color', SUCCESS),
            ), 0)
        except Exception as e:
            msg = str(e)
            Clock.schedule_once(lambda *_, m=msg: (
                setattr(lbl_ok, 'text', f'Error: {m}'),
                setattr(lbl_ok, 'color', DANGER),
            ), 0)
