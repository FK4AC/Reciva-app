import hashlib
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from kivy.clock import Clock

from db.connection import get_connection
import utils.overlay as overlay
from utils.email_smtp import enviar_credenciales
from utils.volcado import cargar_smtp_config
from theme import TINTA, STAGE, CARD, VERMILLON, LADRILLO, LINE, MUTED, SUCCESS, TEXT_SEC, WARNING
from widgets.components import PillButton, show_toast

ROL_COLORS = {
    'operador':   (0.549, 0.502, 0.467, 1),
    'admin':      (0.149, 0.447, 0.671, 1),
    'superadmin': (0.149, 0.600, 0.314, 1),
}
_ROL_COLOR_DEFAULT = (0.200, 0.470, 0.820, 1)

_roles_cache: list = []  # lista de nombres de rol (cargada desde BD)


class UsuariosScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self._cargar()

    def _cargar(self):
        overlay.show('Cargando usuarios…')
        threading.Thread(target=self._tarea, daemon=True).start()

    def _tarea(self):
        global _roles_cache
        rows, error = [], None
        conn = get_connection()
        if not conn:
            Clock.schedule_once(lambda *_: self._aplicar([], 'Sin conexión'), 0)
            return
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, nombre, email, rol, activo FROM usuarios ORDER BY id"
            )
            rows = cur.fetchall()
            cur.execute("SELECT nombre FROM roles ORDER BY id")
            _roles_cache = [r[0] for r in cur.fetchall()]
        except Exception as e:
            error = str(e)
        finally:
            cur.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar(rows, error), 0)

    def _aplicar(self, rows, error=None):
        overlay.hide()
        if error:
            if 'conexión' in str(error).lower():
                from kivy.app import App
                App.get_running_app().ir_sin_conexion(self.name)
            else:
                self.mensaje = f'Error: {error}'
            return

        lista = self.ids.lista_usuarios
        lista.clear_widgets()

        for i, (uid, nombre, email, rol, activo) in enumerate(rows):
            fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=46, spacing=4)
            bg = CARD if i % 2 == 0 else STAGE
            with fila.canvas.before:
                Color(*bg)
                r = Rectangle(pos=fila.pos, size=fila.size)
            fila.bind(pos=lambda _, v, rr=r: setattr(rr, 'pos', v))
            fila.bind(size=lambda _, v, rr=r: setattr(rr, 'size', v))

            for txt, sx, col, bld in [
                (nombre[:24],    0.27, TINTA,                               True),
                (email[:28],     0.34, TEXT_SEC,                            False),
                (rol,            0.16, ROL_COLORS.get(rol, _ROL_COLOR_DEFAULT), False),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=13, color=col,
                            bold=bld, halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 8, v[1])))
                fila.add_widget(lbl)

            # Chip activo / inactivo
            estado_txt = 'Activo' if activo else 'Inactivo'
            estado_col = SUCCESS if activo else MUTED
            chip = Label(text=estado_txt, size_hint_x=0.10, font_size=13, color=estado_col,
                         bold=True, halign='left', valign='middle')
            chip.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 8, v[1])))
            fila.add_widget(chip)

            btn_edit = PillButton(
                text='Editar', size_hint_x=0.07, font_size=11,
                bg_color=TINTA, pressed_color=LADRILLO, pill_radius=6
            )
            btn_edit.bind(on_press=lambda _, u=uid, n=nombre, e=email, rl=rol, a=activo:
                          self._popup_editar(u, n, e, rl, a))
            fila.add_widget(btn_edit)

            btn_tog = PillButton(
                text='Desactivar' if activo else 'Activar',
                size_hint_x=0.09, font_size=10,
                bg_color=VERMILLON if activo else SUCCESS,
                pressed_color=LADRILLO if activo else (0.09, 0.40, 0.16, 1),
                pill_radius=6
            )
            btn_tog.bind(on_press=lambda _, u=uid, a=activo: self._toggle_activo(u, a))
            fila.add_widget(btn_tog)

            lista.add_widget(fila)

        self.mensaje = f'{len(rows)} usuario(s)'

    # ── Crear usuario ────────────────────────────────────────────────
    def popup_nuevo(self):
        self._popup_form('Nuevo usuario', None, '', '', 'operador', True)

    def _popup_editar(self, uid, nombre, email, rol, activo):
        self._popup_form('Editar usuario', uid, nombre, email, rol, activo)

    def _popup_form(self, titulo, uid, nombre, email, rol, activo):
        AZUL  = (0.200, 0.470, 0.820, 1)
        VERDE = (0.149, 0.600, 0.314, 1)
        PURP  = (0.502, 0.251, 0.671, 1)

        def _mk_bg(widget, col):
            with widget.canvas.before:
                Color(*col)
                _r = Rectangle(pos=widget.pos, size=widget.size)
            widget.bind(pos=lambda _, v, r=_r: setattr(r, 'pos', v),
                        size=lambda _, v, r=_r: setattr(r, 'size', v))

        # ── Root ──────────────────────────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        _mk_bg(content, CARD)

        # ── Header TINTA ──────────────────────────────────────────────
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=86,
                        padding=[22, 10])
        _mk_bg(top, TINTA)

        title_row = BoxLayout(size_hint_y=None, height=40)
        ico = Label(text='👤', font_size=22, color=(1, 1, 1, 1),
                    size_hint_x=None, width=36, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        title_row.add_widget(ico)
        lbl_tit = Label(text=titulo, bold=True, font_size=18, color=(1, 1, 1, 1),
                        halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        title_row.add_widget(lbl_tit)
        top.add_widget(title_row)

        sub_row = BoxLayout(size_hint_y=None, height=26)
        subtxt = (f'ID #{uid}  ·  {email}' if uid
                  else 'Completa los datos del nuevo usuario')
        lbl_sub = Label(text=subtxt, font_size=11, color=(0.780, 0.820, 0.867, 1),
                        halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        sub_row.add_widget(lbl_sub)
        top.add_widget(sub_row)
        content.add_widget(top)

        # ── Avatar strip (solo al editar) ─────────────────────────────
        if uid is not None:
            av_strip = BoxLayout(size_hint_y=None, height=64,
                                 padding=[20, 10], spacing=14)
            _mk_bg(av_strip, STAGE)

            av_col = ROL_COLORS.get(rol, _ROL_COLOR_DEFAULT)
            initials = ''.join(w[0].upper() for w in nombre.split()[:2]) if nombre else '?'
            av_box = BoxLayout(size_hint_x=None, width=44)
            with av_box.canvas.before:
                Color(*av_col)
                _avc = RoundedRectangle(pos=av_box.pos, size=av_box.size, radius=[22])
            av_box.bind(pos=lambda _, v, r=_avc: setattr(r, 'pos', v),
                        size=lambda _, v, r=_avc: setattr(r, 'size', v))
            av_box.add_widget(Label(text=initials, font_size=16, bold=True,
                                    color=(1, 1, 1, 1)))
            av_strip.add_widget(av_box)

            info_col = BoxLayout(orientation='vertical', spacing=2)
            lbl_nom2 = Label(text=nombre, bold=True, font_size=14, color=TINTA,
                             halign='left', valign='middle',
                             size_hint_y=None, height=26)
            lbl_nom2.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            info_col.add_widget(lbl_nom2)

            chip_row = BoxLayout(size_hint_y=None, height=22, spacing=6)
            chip_w = BoxLayout(size_hint_x=None, width=82, size_hint_y=None, height=20)
            with chip_w.canvas.before:
                Color(av_col[0], av_col[1], av_col[2], 0.18)
                _cc = RoundedRectangle(pos=chip_w.pos, size=chip_w.size, radius=[10])
            chip_w.bind(pos=lambda _, v, r=_cc: setattr(r, 'pos', v),
                        size=lambda _, v, r=_cc: setattr(r, 'size', v))
            chip_w.add_widget(Label(text=rol, font_size=10, bold=True, color=av_col))
            chip_row.add_widget(chip_w)
            chip_row.add_widget(Widget())
            info_col.add_widget(chip_row)
            av_strip.add_widget(info_col)
            content.add_widget(av_strip)

        # ── Body ──────────────────────────────────────────────────────
        body = BoxLayout(orientation='vertical', size_hint_y=1,
                         padding=[20, 14], spacing=8)

        def _field(sec_label, hint, texto='', password=False, accent=TINTA):
            lbl = Label(text=sec_label, font_size=10, color=MUTED, bold=True,
                        size_hint_y=None, height=16, halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            body.add_widget(lbl)

            wrap = BoxLayout(size_hint_y=None, height=44, padding=[0, 0])
            with wrap.canvas.before:
                Color(1, 1, 1, 1)
                _wbg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
                Color(*LINE)
                _wbd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
                Color(*accent)
                _wbar = Rectangle(pos=wrap.pos, size=(3, 0))
            def _upd(inst, v, bg=_wbg, bd=_wbd, bar=_wbar):
                bg.pos, bg.size = inst.pos, inst.size
                bd.pos, bd.size = inst.pos, inst.size
                bar.pos = (inst.x, inst.y)
                bar.size = (3, inst.height)
            wrap.bind(pos=_upd, size=_upd)

            ti = TextInput(
                text=texto, hint_text=hint, multiline=False, password=password,
                background_normal='', background_active='',
                background_color=(0, 0, 0, 0),
                foreground_color=TINTA, cursor_color=accent,
                hint_text_color=MUTED, padding=[14, 12], font_size=13,
            )
            wrap.add_widget(ti)
            body.add_widget(wrap)
            return ti

        ti_nombre = _field('NOMBRE COMPLETO', 'Nombre completo', nombre)
        ti_email  = _field('CORREO ELECTRÓNICO', 'correo@ejemplo.com', email,
                           accent=AZUL)
        hint_pw   = 'Nueva contraseña (vacío = sin cambio)' if uid else 'Contraseña'
        ti_pw     = _field('CONTRASEÑA', hint_pw, password=True, accent=PURP)

        # ── Rol selector (lista dinámica, scrollable) ─────────────────
        lbl_rol = Label(text='ROL DEL USUARIO', font_size=10, color=MUTED, bold=True,
                        size_hint_y=None, height=16, halign='left', valign='middle')
        lbl_rol.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_rol)

        roles_disponibles = [r for r in _roles_cache if r != 'superadmin'] or ['operador']
        rol_actual = rol if rol in roles_disponibles else (
            roles_disponibles[0] if roles_disponibles else 'operador')
        sel_rol = [rol_actual]

        ROW_H   = 44
        N_VIS   = min(len(roles_disponibles), 3)
        wrap_h  = ROW_H * N_VIS + 2

        sel_wrap = BoxLayout(size_hint_y=None, height=wrap_h, padding=[1, 1])
        with sel_wrap.canvas.before:
            Color(1, 1, 1, 1)
            _swbg = RoundedRectangle(pos=sel_wrap.pos, size=sel_wrap.size, radius=[8])
            Color(*LINE)
            _swbd = RoundedRectangle(pos=sel_wrap.pos, size=sel_wrap.size, radius=[8])
        sel_wrap.bind(
            pos =lambda _, v, a=_swbg, b=_swbd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
            size=lambda _, v, a=_swbg, b=_swbd: (setattr(a, 'size', v), setattr(b, 'size', v)),
        )

        sv    = ScrollView(do_scroll_x=False, size_hint=(1, 1))
        inner = BoxLayout(orientation='vertical', size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        _row_refs = {}  # rol -> (Color inst, lbl_dot, lbl_name, lbl_chk)

        def _refresh_rol():
            for r, (ci, ldot, lname, lchk) in _row_refs.items():
                col = ROL_COLORS.get(r, _ROL_COLOR_DEFAULT)
                if r == sel_rol[0]:
                    ci.rgba    = (col[0], col[1], col[2], 0.12)
                    ldot.color = list(col)
                    lname.bold  = True
                    lname.color = list(col)
                    lchk.text  = '✓'
                    lchk.color = list(col)
                else:
                    ci.rgba    = (1, 1, 1, 1)
                    ldot.color = list(MUTED)
                    lname.bold  = False
                    lname.color = list(TINTA)
                    lchk.text  = ''

        for idx, r in enumerate(roles_disponibles):
            col    = ROL_COLORS.get(r, _ROL_COLOR_DEFAULT)
            is_sel = (r == sel_rol[0])

            row = BoxLayout(size_hint_y=None, height=ROW_H, padding=[14, 0], spacing=8)
            with row.canvas.before:
                _ci  = Color(*(col[0], col[1], col[2], 0.12) if is_sel else (1, 1, 1, 1))
                _rbg = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos =lambda inst, v, rr=_rbg: setattr(rr, 'pos',  v),
                     size=lambda inst, v, rr=_rbg: setattr(rr, 'size', v))

            lbl_dot = Label(text='●', font_size=11,
                            color=list(col) if is_sel else list(MUTED),
                            size_hint_x=None, width=18,
                            halign='center', valign='middle')
            lbl_dot.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            row.add_widget(lbl_dot)

            lbl_name = Label(text=r.title(), font_size=13, bold=is_sel,
                             color=list(col) if is_sel else list(TINTA),
                             halign='left', valign='middle')
            lbl_name.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            row.add_widget(lbl_name)

            lbl_chk = Label(text='✓' if is_sel else '', font_size=14, bold=True,
                            color=list(col), size_hint_x=None, width=28,
                            halign='center', valign='middle')
            lbl_chk.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            row.add_widget(lbl_chk)

            _row_refs[r] = (_ci, lbl_dot, lbl_name, lbl_chk)

            def _on_touch(inst, touch, r=r):
                if inst.collide_point(*touch.pos):
                    sel_rol[0] = r
                    _refresh_rol()
                    return True
            row.bind(on_touch_down=_on_touch)
            inner.add_widget(row)

            if idx < len(roles_disponibles) - 1:
                div = BoxLayout(size_hint_y=None, height=1)
                with div.canvas.before:
                    Color(*LINE)
                    _dr = Rectangle(pos=div.pos, size=div.size)
                div.bind(pos =lambda _, v, r=_dr: setattr(r, 'pos',  v),
                         size=lambda _, v, r=_dr: setattr(r, 'size', v))
                inner.add_widget(div)

        sv.add_widget(inner)
        sel_wrap.add_widget(sv)
        body.add_widget(sel_wrap)

        lbl_error = Label(text='', font_size=12, color=VERMILLON,
                          size_hint_y=None, height=22,
                          halign='left', valign='middle')
        lbl_error.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_error)

        content.add_widget(body)

        # ── Footer fijo ───────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _mk_bg(footer, STAGE)

        popup = Popup(title='', content=content, size_hint=(0.50, 0.84),
                      background_color=CARD, separator_height=0)

        def _guardar(_):
            n = ti_nombre.text.strip()
            e = ti_email.text.strip()
            p = ti_pw.text.strip()
            rl = sel_rol[0]

            if not n or not e:
                lbl_error.text = '⚠  Nombre y email son obligatorios'
                return
            if uid is None and not p:
                lbl_error.text = '⚠  La contraseña es obligatoria para un usuario nuevo'
                return

            popup.dismiss()
            overlay.show('Guardando…')

            def _tarea():
                conn2 = get_connection()
                if not conn2:
                    Clock.schedule_once(
                        lambda *_: setattr(self, 'mensaje', 'Error de conexión'), 0)
                    return
                cur2 = conn2.cursor()
                es_nuevo = (uid is None)
                try:
                    if es_nuevo:
                        pw_hash = hashlib.sha256(p.encode()).hexdigest()
                        cur2.execute(
                            "INSERT INTO usuarios (nombre, email, password, rol, activo) "
                            "VALUES (%s, %s, %s, %s, 1)",
                            (n, e, pw_hash, rl)
                        )
                    else:
                        if p:
                            pw_hash = hashlib.sha256(p.encode()).hexdigest()
                            cur2.execute(
                                "UPDATE usuarios SET nombre=%s, email=%s, "
                                "password=%s, rol=%s WHERE id=%s",
                                (n, e, pw_hash, rl, uid)
                            )
                        else:
                            cur2.execute(
                                "UPDATE usuarios SET nombre=%s, email=%s, rol=%s "
                                "WHERE id=%s",
                                (n, e, rl, uid)
                            )
                    conn2.commit()
                except Exception as ex:
                    Clock.schedule_once(
                        lambda *_, err=ex: setattr(self, 'mensaje', f'Error: {err}'), 0)
                    return
                finally:
                    cur2.close()
                    conn2.close()

                if es_nuevo:
                    smtp_cfg = {}
                    conn3 = get_connection()
                    if conn3:
                        try:
                            smtp_cfg = cargar_smtp_config(conn3)
                        finally:
                            conn3.close()
                    ok, smtp_err = enviar_credenciales(n, e, p, rl, smtp_cfg=smtp_cfg or None)
                    if ok:
                        Clock.schedule_once(
                            lambda *_, em=e: show_toast(
                                f'Credenciales enviadas a {em}', duration=3.5), 0)
                    else:
                        Clock.schedule_once(
                            lambda *_, m=smtp_err: show_toast(
                                f'Usuario creado. Email no enviado: {m}', duration=5), 0)

                Clock.schedule_once(lambda *_: self._cargar(), 0)

            threading.Thread(target=_tarea, daemon=True).start()

        footer.add_widget(Widget())
        btn_cancel = PillButton(
            text='Cancelar', size_hint_x=0.34,
            bg_color=LINE, fg_color=TINTA, pressed_color=STAGE,
            font_size=13, pill_radius=20)
        btn_save = PillButton(
            text='Guardar cambios' if uid else 'Crear usuario',
            size_hint_x=0.52,
            bg_color=VERDE, pressed_color=(0.09, 0.40, 0.16, 1),
            font_size=13, pill_radius=20)
        btn_cancel.bind(on_press=popup.dismiss)
        btn_save.bind(on_press=_guardar)
        footer.add_widget(btn_cancel)
        footer.add_widget(btn_save)
        content.add_widget(footer)
        popup.open()

    # ── Toggle activo ────────────────────────────────────────────────
    def _toggle_activo(self, uid, activo_actual):
        nuevo = 0 if activo_actual else 1
        overlay.show()

        def _tarea():
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (nuevo, uid))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
            Clock.schedule_once(lambda *_: self._cargar(), 0)

        threading.Thread(target=_tarea, daemon=True).start()
