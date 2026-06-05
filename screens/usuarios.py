import hashlib
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from kivy.clock import Clock

from db.connection import get_connection
import utils.overlay as overlay
from theme import TINTA, STAGE, CARD, VERMILLON, LINE, MUTED, SUCCESS, TEXT_SEC, WARNING

ROL_LABELS = {'operador': 'Operador', 'admin': 'Admin', 'superadmin': 'Super Admin'}
ROL_COLORS = {
    'operador':   (0.549, 0.502, 0.467, 1),
    'admin':      (0.149, 0.447, 0.671, 1),
    'superadmin': (0.149, 0.600, 0.314, 1),
}


class UsuariosScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self._cargar()

    def _cargar(self):
        overlay.show('Cargando usuarios…')
        threading.Thread(target=self._tarea, daemon=True).start()

    def _tarea(self):
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

            for txt, sx, col in [
                (nombre[:24],         0.27, TINTA),
                (email[:28],          0.34, TEXT_SEC),
                (ROL_LABELS.get(rol, rol), 0.16, ROL_COLORS.get(rol, MUTED)),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=12, color=col,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 6, v[1])))
                fila.add_widget(lbl)

            # Chip activo / inactivo
            estado_txt = 'Activo' if activo else 'Inactivo'
            estado_col = SUCCESS if activo else MUTED
            chip = Label(text=estado_txt, size_hint_x=0.10, font_size=11, color=estado_col,
                         bold=True, halign='center', valign='middle')
            chip.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            fila.add_widget(chip)

            btn_edit = Button(
                text='Editar', size_hint_x=0.07, font_size=11,
                background_normal='', background_color=TINTA, color=(1, 1, 1, 1)
            )
            btn_edit.bind(on_press=lambda _, u=uid, n=nombre, e=email, rl=rol, a=activo:
                          self._popup_editar(u, n, e, rl, a))
            fila.add_widget(btn_edit)

            btn_tog = Button(
                text='Desactivar' if activo else 'Activar',
                size_hint_x=0.09, font_size=10,
                background_normal='',
                background_color=VERMILLON if activo else SUCCESS,
                color=(1, 1, 1, 1)
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
        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            r = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(r, 'pos', v))
        content.bind(size=lambda _, v: setattr(r, 'size', v))

        # Cabecera
        hdr = BoxLayout(size_hint_y=None, height=52, padding=[16, 0])
        with hdr.canvas.before:
            Color(*TINTA)
            rh = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda _, v: setattr(rh, 'pos', v))
        hdr.bind(size=lambda _, v: setattr(rh, 'size', v))
        hdr.add_widget(Label(text=titulo, bold=True, font_size=14, color=(1, 1, 1, 1),
                             halign='left', valign='middle', text_size=(400, 52)))
        content.add_widget(hdr)

        body = BoxLayout(orientation='vertical', padding=[20, 14], spacing=10)
        content.add_widget(body)

        def campo(label_txt, hint, texto='', password=False):
            body.add_widget(Label(text=label_txt, font_size=11, color=MUTED,
                                  size_hint_y=None, height=18,
                                  halign='left', text_size=(400, 18)))
            ti = TextInput(text=texto, hint_text=hint, multiline=False,
                           password=password, font_size=13,
                           size_hint_y=None, height=36,
                           background_color=STAGE,
                           foreground_color=TINTA,
                           cursor_color=TINTA)
            body.add_widget(ti)
            return ti

        ti_nombre = campo('Nombre', 'Nombre completo', nombre)
        ti_email  = campo('Email', 'correo@ejemplo.com', email)
        hint_pw   = 'Nueva contraseña (dejar vacío para no cambiar)' if uid else 'Contraseña'
        ti_pw     = campo('Contraseña', hint_pw, password=True)

        body.add_widget(Label(text='Rol', font_size=11, color=MUTED,
                              size_hint_y=None, height=18,
                              halign='left', text_size=(400, 18)))
        sp_rol = Spinner(
            text=ROL_LABELS.get(rol, 'Operador'),
            values=['Operador', 'Admin', 'Super Admin'],
            size_hint_y=None, height=36, font_size=13,
            background_normal='', background_color=STAGE,
            color=TINTA
        )
        body.add_widget(sp_rol)

        lbl_error = Label(text='', font_size=11, color=VERMILLON,
                          size_hint_y=None, height=20,
                          halign='left', text_size=(400, 20))
        body.add_widget(lbl_error)

        # Footer
        footer = BoxLayout(size_hint_y=None, height=56, spacing=10, padding=[16, 10])
        with footer.canvas.before:
            Color(*STAGE)
            rf = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(rf, 'pos', v))
        footer.bind(size=lambda _, v: setattr(rf, 'size', v))

        popup = Popup(title='', content=content, size_hint=(0.44, None), height=430,
                      background_color=CARD, separator_height=0)

        ROL_MAP = {'Operador': 'operador', 'Admin': 'admin', 'Super Admin': 'superadmin'}

        def _guardar(_):
            n = ti_nombre.text.strip()
            e = ti_email.text.strip()
            p = ti_pw.text.strip()
            rl = ROL_MAP.get(sp_rol.text, 'operador')

            if not n or not e:
                lbl_error.text = 'Nombre y email son obligatorios'
                return
            if uid is None and not p:
                lbl_error.text = 'La contraseña es obligatoria para un usuario nuevo'
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
                try:
                    if uid is None:
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
                                "UPDATE usuarios SET nombre=%s, email=%s, password=%s, rol=%s "
                                "WHERE id=%s",
                                (n, e, pw_hash, rl, uid)
                            )
                        else:
                            cur2.execute(
                                "UPDATE usuarios SET nombre=%s, email=%s, rol=%s WHERE id=%s",
                                (n, e, rl, uid)
                            )
                    conn2.commit()
                except Exception as ex:
                    Clock.schedule_once(
                        lambda *_: setattr(self, 'mensaje', f'Error: {ex}'), 0)
                    return
                finally:
                    cur2.close()
                    conn2.close()
                Clock.schedule_once(lambda *_: self._cargar(), 0)

            threading.Thread(target=_tarea, daemon=True).start()

        btn_cancel = Button(text='Cancelar', size_hint=(0.32, None), height=36,
                            background_normal='', background_color=LINE, color=TINTA,
                            font_size=12)
        btn_save   = Button(text='Guardar', size_hint=(0.68, None), height=36,
                            background_normal='', background_color=SUCCESS,
                            color=(1, 1, 1, 1), font_size=12)
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
