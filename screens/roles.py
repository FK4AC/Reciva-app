import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from kivy.clock import Clock

from db.connection import get_connection
import utils.overlay as overlay
from utils.permisos import (
    PANTALLAS, PANTALLAS_LABELS,
    listar_roles, listar_permisos_rol,
    guardar_permisos_rol, crear_rol, eliminar_rol,
)
from theme import (TINTA, BG, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, TEXT_SEC, SUCCESS, DANGER, WARNING)
from widgets.components import PillButton


def _bg(w, col):
    with w.canvas.before:
        Color(*col)
        r = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda s, _: setattr(r, 'pos', s.pos),
           size=lambda s, _: setattr(r, 'size', s.size))


def _lbl(text, sx=1, color=None, size=12, bold=False, halign='left', height=None):
    kw = {}
    if height is not None:
        kw = {'size_hint_y': None, 'height': height}
    l = Label(text=str(text) if text else '—', size_hint_x=sx,
              color=color or TINTA, font_size=size, bold=bold,
              halign=halign, valign='middle', **kw)
    l.bind(size=lambda w, _: setattr(w, 'text_size', (w.width, w.height)))
    return l


class _CheckBox(Button):
    """Botón toggle que simula un checkbox con texto ✓ / —"""
    def __init__(self, value=False, **kw):
        super().__init__(**kw)
        self.value = value
        self._actualizar()
        self.background_normal = ''
        self.font_size = 13
        self.size_hint_y = None
        self.height = 32

    def _actualizar(self):
        self.text = '✓' if self.value else '—'
        self.background_color = SUCCESS if self.value else LINE
        self.color = (1, 1, 1, 1) if self.value else MUTED

    def toggle(self):
        self.value = not self.value
        self._actualizar()

    def on_press(self):
        self.toggle()


class RolesScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self._cargar()

    def _cargar(self):
        overlay.show('Cargando roles…')
        threading.Thread(target=self._tarea, daemon=True).start()

    def _tarea(self):
        conn = get_connection()
        if not conn:
            Clock.schedule_once(lambda *_: self._aplicar([], 'Sin conexión'), 0)
            return
        try:
            roles = listar_roles(conn)
        except Exception as e:
            roles, e_msg = [], str(e)
            Clock.schedule_once(lambda *_: self._aplicar([], e_msg), 0)
            return
        finally:
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar(roles), 0)

    def _aplicar(self, roles, error=None):
        overlay.hide()
        lista = self.ids.lista_roles
        lista.clear_widgets()

        if error:
            self.mensaje = f'Error: {error}'
            return

        self.mensaje = f'{len(roles)} rol(es)'

        for i, rol in enumerate(roles):
            fila = BoxLayout(size_hint_y=None, height=50, spacing=6, padding=[12, 0])
            _bg(fila, CARD if i % 2 == 0 else STAGE)

            nombre_txt = rol['nombre'].title()
            if rol['inmutable']:
                nombre_txt += '  🔒'

            fila.add_widget(_lbl(nombre_txt, sx=0.35, bold=True, size=13))
            fila.add_widget(_lbl(
                f"{rol['n_usuarios']} usuario(s)",
                sx=0.25, color=TEXT_SEC, size=12,
            ))

            btn_editar = PillButton(
                text='Permisos', font_size=12,
                bg_color=TINTA, pressed_color=LADRILLO,
                pill_radius=8, size_hint=(None, None), size=(100, 32),
            )
            btn_editar.bind(on_press=lambda _, r=rol: self._popup_permisos(r))

            btn_eliminar = PillButton(
                text='Eliminar', font_size=12,
                bg_color=DANGER if not rol['inmutable'] else LINE,
                fg_color=(1, 1, 1, 1) if not rol['inmutable'] else MUTED,
                pressed_color=LADRILLO,
                pill_radius=8, size_hint=(None, None), size=(90, 32),
            )
            if rol['inmutable']:
                btn_eliminar.disabled = True
            else:
                btn_eliminar.bind(on_press=lambda _, r=rol: self._confirmar_eliminar(r))

            wrap = BoxLayout(size_hint_x=0.40, spacing=10, padding=[0, 9])
            wrap.add_widget(btn_editar)
            wrap.add_widget(btn_eliminar)
            fila.add_widget(wrap)
            lista.add_widget(fila)

    # ── Popup: permisos de un rol ─────────────────────────────────────────────

    def _popup_permisos(self, rol):
        overlay.show('Cargando permisos…')

        def _do():
            conn = get_connection()
            if not conn:
                Clock.schedule_once(lambda *_: overlay.hide(), 0)
                return
            try:
                permisos = listar_permisos_rol(conn, rol['id'])
            finally:
                conn.close()
            Clock.schedule_once(lambda *_: self._abrir_popup_permisos(rol, permisos), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _abrir_popup_permisos(self, rol, permisos):
        overlay.hide()
        es_superadmin = rol['inmutable']

        content = BoxLayout(orientation='vertical', spacing=0)
        _bg(content, CARD)

        # ── Header ────────────────────────────────────────────────────
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=82,
                        padding=[22, 10])
        _bg(top, TINTA)
        t_row = BoxLayout(size_hint_y=None, height=38)
        ico = Label(text='🔑', font_size=20, color=(1, 1, 1, 1),
                    size_hint_x=None, width=32, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        lbl_tit = Label(text=rol['nombre'].title(), bold=True, font_size=18,
                        color=(1, 1, 1, 1), halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        t_row.add_widget(ico)
        t_row.add_widget(lbl_tit)
        top.add_widget(t_row)
        s_row = BoxLayout(size_hint_y=None, height=24)
        subtxt = 'Rol inmutable — permisos de solo lectura' if es_superadmin else 'Pantallas accesibles para este rol'
        lbl_sub = Label(text=subtxt, font_size=11,
                        color=(0.780, 0.820, 0.867, 1),
                        halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        s_row.add_widget(lbl_sub)
        top.add_widget(s_row)
        content.add_widget(top)

        # ── Cabecera tabla ─────────────────────────────────────────────
        col_hdr = BoxLayout(size_hint_y=None, height=30, padding=[12, 0])
        _bg(col_hdr, STAGE)
        for txt, sx, ha in [('Pantalla', 0.56, 'left'),
                             ('Ver',      0.22, 'center'),
                             ('Editar',   0.22, 'center')]:
            lh = Label(text=txt, font_size=10, color=MUTED, bold=True,
                       size_hint_x=sx, halign=ha, valign='middle')
            lh.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            col_hdr.add_widget(lh)
        content.add_widget(col_hdr)

        # ── Filas de permisos ──────────────────────────────────────────
        checks = {}
        tabla = BoxLayout(orientation='vertical', size_hint_y=None)
        tabla.bind(minimum_height=tabla.setter('height'))

        for i, pantalla in enumerate(PANTALLAS):
            if pantalla == 'roles' and not es_superadmin:
                ver_val, editar_val = False, False
            else:
                ver_val, editar_val = permisos.get(pantalla, (False, False))

            fila = BoxLayout(size_hint_y=None, height=42, padding=[12, 5], spacing=4)
            _bg(fila, CARD if i % 2 == 0 else STAGE)

            lbl_p = _lbl(PANTALLAS_LABELS.get(pantalla, pantalla),
                         sx=0.56, size=12, color=TINTA)
            cb_ver    = _CheckBox(value=ver_val,    size_hint_x=0.22)
            cb_editar = _CheckBox(value=editar_val, size_hint_x=0.22)

            if es_superadmin:
                cb_ver.disabled    = True
                cb_editar.disabled = True

            fila.add_widget(lbl_p)
            fila.add_widget(cb_ver)
            fila.add_widget(cb_editar)
            tabla.add_widget(fila)
            checks[pantalla] = (cb_ver, cb_editar)

        scroll = ScrollView(size_hint_y=1)
        scroll.add_widget(tabla)
        content.add_widget(scroll)

        # ── Footer ────────────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _bg(footer, STAGE)

        popup = Popup(title='', content=content, size_hint=(0.50, 0.86),
                      background_color=CARD, separator_height=0)

        footer.add_widget(Widget())
        btn_cancel = PillButton(text='Cerrar', font_size=13,
                                bg_color=LINE, fg_color=TINTA,
                                pressed_color=STAGE, pill_radius=20,
                                size_hint_x=None, width=100)
        footer.add_widget(btn_cancel)
        btn_cancel.bind(on_press=popup.dismiss)

        if not es_superadmin:
            btn_save = PillButton(text='Guardar permisos', font_size=13,
                                  bg_color=SUCCESS,
                                  pressed_color=(0.09, 0.40, 0.16, 1),
                                  pill_radius=20,
                                  size_hint_x=None, width=160)
            footer.add_widget(btn_save)

            def guardar(_):
                nuevos = {p: (cb_v.value, cb_e.value)
                          for p, (cb_v, cb_e) in checks.items()}
                overlay.show('Guardando…')

                def _do():
                    conn = get_connection()
                    if conn:
                        try:
                            guardar_permisos_rol(conn, rol['id'], nuevos)
                        finally:
                            conn.close()
                    Clock.schedule_once(lambda *_: (overlay.hide(), popup.dismiss()), 0)

                threading.Thread(target=_do, daemon=True).start()

            btn_save.bind(on_press=guardar)

        content.add_widget(footer)
        popup.open()

    # ── Popup: nuevo rol (nombre + permisos en un solo paso) ─────────────────

    def popup_nuevo_rol(self):
        checks = {}  # pantalla → (cb_ver, cb_editar)

        def _mk_bg_r(widget, col):
            with widget.canvas.before:
                Color(*col)
                _r = Rectangle(pos=widget.pos, size=widget.size)
            widget.bind(pos=lambda _, v, r=_r: setattr(r, 'pos', v),
                        size=lambda _, v, r=_r: setattr(r, 'size', v))

        def _div():
            d = BoxLayout(size_hint_y=None, height=1)
            with d.canvas.before:
                Color(*LINE)
                _dr = Rectangle(pos=d.pos, size=d.size)
            d.bind(pos=lambda _, v, r=_dr: setattr(r, 'pos', v),
                   size=lambda _, v, r=_dr: setattr(r, 'size', v))
            return d

        # ── Root ──────────────────────────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        _mk_bg_r(content, CARD)

        # ── Header ────────────────────────────────────────────────────
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=82,
                        padding=[22, 10])
        _mk_bg_r(top, TINTA)
        t_row = BoxLayout(size_hint_y=None, height=38)
        ico = Label(text='🔑', font_size=20, color=(1, 1, 1, 1),
                    size_hint_x=None, width=32, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        lbl_tit = Label(text='Nuevo Rol', bold=True, font_size=18,
                        color=(1, 1, 1, 1), halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        t_row.add_widget(ico)
        t_row.add_widget(lbl_tit)
        top.add_widget(t_row)
        s_row = BoxLayout(size_hint_y=None, height=24)
        lbl_sub = Label(text='Define el nombre y las pantallas accesibles',
                        font_size=11, color=(0.780, 0.820, 0.867, 1),
                        halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        s_row.add_widget(lbl_sub)
        top.add_widget(s_row)
        content.add_widget(top)

        # ── Body ──────────────────────────────────────────────────────
        body = BoxLayout(orientation='vertical', size_hint_y=1,
                         padding=[20, 14], spacing=8)

        # Nombre del rol
        lbl_n = Label(text='NOMBRE DEL ROL', font_size=10, color=MUTED, bold=True,
                      size_hint_y=None, height=16, halign='left', valign='middle')
        lbl_n.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_n)

        ti_wrap = BoxLayout(size_hint_y=None, height=44)
        with ti_wrap.canvas.before:
            Color(1, 1, 1, 1)
            _twbg = RoundedRectangle(pos=ti_wrap.pos, size=ti_wrap.size, radius=[8])
            Color(*LINE)
            _twbd = RoundedRectangle(pos=ti_wrap.pos, size=ti_wrap.size, radius=[8])
            Color(*TINTA)
            _twbar = Rectangle(pos=ti_wrap.pos, size=(3, 0))
        def _upd_tw(inst, v, a=_twbg, b=_twbd, bar=_twbar):
            a.pos, a.size = inst.pos, inst.size
            b.pos, b.size = inst.pos, inst.size
            bar.pos = (inst.x, inst.y)
            bar.size = (3, inst.height)
        ti_wrap.bind(pos=_upd_tw, size=_upd_tw)
        ti = TextInput(
            hint_text='Ej: supervisor, auditor…', multiline=False, font_size=13,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=VERMILLON, padding=[14, 12],
        )
        ti_wrap.add_widget(ti)
        body.add_widget(ti_wrap)

        lbl_err = Label(text='', font_size=12, color=DANGER,
                        size_hint_y=None, height=18, halign='left', valign='middle')
        lbl_err.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_err)

        body.add_widget(_div())

        # Cabecera de permisos
        lbl_ps = Label(text='PANTALLAS ACCESIBLES', font_size=10, color=MUTED, bold=True,
                       size_hint_y=None, height=16, halign='left', valign='middle')
        lbl_ps.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_ps)

        col_hdr = BoxLayout(size_hint_y=None, height=28, padding=[12, 0])
        _mk_bg_r(col_hdr, STAGE)
        for txt, sx, ha in [('Pantalla', 0.56, 'left'),
                             ('Ver',      0.22, 'center'),
                             ('Editar',   0.22, 'center')]:
            lh = Label(text=txt, font_size=10, color=MUTED, bold=True,
                       size_hint_x=sx, halign=ha, valign='middle')
            lh.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            col_hdr.add_widget(lh)
        body.add_widget(col_hdr)

        # Filas de permisos (scroll)
        sv = ScrollView(do_scroll_x=False)
        tabla = BoxLayout(orientation='vertical', size_hint_y=None)
        tabla.bind(minimum_height=tabla.setter('height'))

        for i, pantalla in enumerate(PANTALLAS):
            if pantalla == 'roles':
                continue  # roles solo superadmin
            fila = BoxLayout(size_hint_y=None, height=42, padding=[12, 5], spacing=4)
            _mk_bg_r(fila, CARD if i % 2 == 0 else STAGE)

            lbl_p = Label(
                text=PANTALLAS_LABELS.get(pantalla, pantalla),
                font_size=12, color=TINTA, size_hint_x=0.56,
                halign='left', valign='middle')
            lbl_p.bind(size=lambda inst, v: setattr(inst, 'text_size', v))

            cb_ver    = _CheckBox(value=False, size_hint_x=0.22)
            cb_editar = _CheckBox(value=False, size_hint_x=0.22)

            # Activar Ver al marcar Editar
            def _on_editar(inst, pantalla=pantalla):
                if inst.value:
                    v, _ = checks[pantalla]
                    if not v.value:
                        v.toggle()
            cb_editar.bind(on_press=lambda inst, p=pantalla: _on_editar(inst, p))

            fila.add_widget(lbl_p)
            fila.add_widget(cb_ver)
            fila.add_widget(cb_editar)
            tabla.add_widget(fila)
            checks[pantalla] = (cb_ver, cb_editar)

        sv.add_widget(tabla)
        body.add_widget(sv)
        content.add_widget(body)

        # ── Footer ────────────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _mk_bg_r(footer, STAGE)

        popup = Popup(title='', content=content, size_hint=(0.52, 0.88),
                      background_color=CARD, separator_height=0)

        btn_cancel = PillButton(text='Cancelar', font_size=13,
                                bg_color=LINE, fg_color=TINTA,
                                pressed_color=STAGE, pill_radius=20)
        btn_save = PillButton(text='Crear Rol', font_size=13,
                              bg_color=SUCCESS,
                              pressed_color=(0.09, 0.40, 0.16, 1), pill_radius=20)

        footer.add_widget(Widget())
        footer.add_widget(btn_cancel)
        footer.add_widget(btn_save)
        content.add_widget(footer)

        btn_cancel.bind(on_press=popup.dismiss)

        def guardar(_):
            nombre = ti.text.strip().lower().replace(' ', '_')
            if not nombre:
                lbl_err.text = '⚠  El nombre no puede estar vacío'
                return
            overlay.show('Creando rol…')

            def _do():
                conn = get_connection()
                if not conn:
                    Clock.schedule_once(lambda *_: overlay.hide(), 0)
                    return
                ok, result = False, 'Sin conexión'
                try:
                    ok, result = crear_rol(conn, nombre)
                    if ok:
                        nuevos = {p: (cb_v.value, cb_e.value)
                                  for p, (cb_v, cb_e) in checks.items()}
                        guardar_permisos_rol(conn, result, nuevos)
                finally:
                    conn.close()
                if ok:
                    Clock.schedule_once(
                        lambda *_: (overlay.hide(), popup.dismiss(), self._cargar()), 0)
                else:
                    Clock.schedule_once(
                        lambda *_, m=str(result): (
                            overlay.hide(),
                            setattr(lbl_err, 'text', f'⚠  {m}'),
                        ), 0)

            threading.Thread(target=_do, daemon=True).start()

        btn_save.bind(on_press=guardar)
        popup.open()

    # ── Confirmar eliminar ────────────────────────────────────────────────────

    def _confirmar_eliminar(self, rol):
        content = BoxLayout(orientation='vertical', padding=20, spacing=16)
        content.add_widget(Label(
            text=f'¿Eliminar el rol "{rol["nombre"]}"?',
            color=TINTA, font_size=13, halign='center',
            size_hint_y=None, height=40))
        lbl_err = Label(text='', color=DANGER, font_size=11,
                        size_hint_y=None, height=20)
        content.add_widget(lbl_err)
        btn_row = BoxLayout(size_hint_y=None, height=44, spacing=10)
        btn_cancel = PillButton(text='Cancelar', font_size=12,
                                bg_color=LINE, pressed_color=MUTED, pill_radius=8)
        btn_cancel.color = TINTA
        btn_ok = PillButton(text='Eliminar', font_size=12,
                            bg_color=DANGER, pressed_color=LADRILLO, pill_radius=8)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_ok)
        content.add_widget(btn_row)
        popup = Popup(title='Confirmar', content=content,
                      size_hint=(0.38, None), height=220)
        btn_cancel.bind(on_press=popup.dismiss)

        def eliminar(_):
            overlay.show()

            def _do():
                conn = get_connection()
                if not conn:
                    Clock.schedule_once(lambda *_: overlay.hide(), 0)
                    return
                try:
                    ok, err = eliminar_rol(conn, rol['id'])
                finally:
                    conn.close()
                if ok:
                    Clock.schedule_once(lambda *_: (overlay.hide(), popup.dismiss(),
                                                    self._cargar()), 0)
                else:
                    Clock.schedule_once(
                        lambda *_: (overlay.hide(),
                                    setattr(lbl_err, 'text', str(err))), 0)

            threading.Thread(target=_do, daemon=True).start()

        btn_ok.bind(on_press=eliminar)
        popup.open()
