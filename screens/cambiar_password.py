import hashlib
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from theme import TINTA, STAGE, CARD, VERMILLON, LADRILLO, LINE, MUTED, SUCCESS, DANGER
from widgets.components import PillButton


def _mk_bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        r = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda w, v, rect=r: setattr(rect, 'pos', v),
        size=lambda w, v, rect=r: setattr(rect, 'size', v),
    )


def _lbl(parent, text, size=13, color=None, halign='left', height=26):
    lbl = Label(
        text=text, font_name='Jakarta', font_size=size,
        color=color or TINTA, halign=halign, valign='middle',
        size_hint_y=None, height=height,
    )
    lbl.bind(size=lambda w, _: setattr(w, 'text_size', w.size))
    parent.add_widget(lbl)
    return lbl


def _field(parent, hint='', password=False):
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
        hint_text=hint, multiline=False, password=password,
        font_name='Jakarta', font_size=13,
        background_normal='', background_active='', background_color=(0, 0, 0, 0),
        foreground_color=TINTA, cursor_color=VERMILLON,
        hint_text_color=MUTED, padding=[14, 12],
    )
    wrap.add_widget(ti)
    parent.add_widget(wrap)
    return ti


class CambiarPasswordScreen(Screen):

    def on_enter(self):
        self.clear_widgets()
        outer = BoxLayout(orientation='vertical')
        _mk_bg(outer, (0.945, 0.918, 0.882, 1))
        self.add_widget(outer)

        # centrar la card
        outer.add_widget(Widget())
        row = BoxLayout(size_hint_y=None, height=420)
        outer.add_widget(row)
        outer.add_widget(Widget())

        row.add_widget(Widget())
        card = BoxLayout(orientation='vertical', size_hint_x=None, width=420)
        _mk_bg(card, CARD)
        row.add_widget(card)
        row.add_widget(Widget())

        # Header
        hdr = BoxLayout(orientation='vertical', size_hint_y=None, height=80, padding=[28, 10])
        _mk_bg(hdr, TINTA)
        _lbl(hdr, 'Cambia tu contraseña', size=18, color=(1, 1, 1, 1), height=36)
        _lbl(hdr, 'Este es tu primer acceso. Elige una contraseña segura.',
             size=11, color=(0.78, 0.82, 0.87, 1), height=22)
        card.add_widget(hdr)

        # Body
        body = BoxLayout(orientation='vertical', padding=[28, 18], spacing=8, size_hint_y=1)
        card.add_widget(body)

        _lbl(body, 'Nueva contraseña', size=11, color=MUTED, height=18)
        self.ti_new = _field(body, 'Mínimo 6 caracteres', password=True)
        _lbl(body, 'Confirmar contraseña', size=11, color=MUTED, height=18)
        self.ti_confirm = _field(body, 'Repite la contraseña', password=True)

        self.lbl_err = Label(
            text='', font_name='Jakarta', font_size=12, color=DANGER,
            halign='left', valign='middle', size_hint_y=None, height=22,
        )
        self.lbl_err.bind(size=lambda w, _: setattr(w, 'text_size', w.size))
        body.add_widget(self.lbl_err)
        body.add_widget(Widget())

        # Footer
        footer = BoxLayout(size_hint_y=None, height=64, padding=[28, 12], spacing=12)
        _mk_bg(footer, STAGE)
        card.add_widget(footer)

        footer.add_widget(Widget())
        btn = PillButton(
            text='Guardar y continuar  →',
            bg_color=VERMILLON, pressed_color=LADRILLO,
            font_size=13, pill_radius=20,
            size_hint_x=None, width=220,
        )
        btn.bind(on_press=self._guardar)
        footer.add_widget(btn)
        self.btn_ok = btn

    def _guardar(self, *_):
        nueva    = self.ti_new.get() if hasattr(self.ti_new, 'get') else self.ti_new.text
        confirma = self.ti_confirm.get() if hasattr(self.ti_confirm, 'get') else self.ti_confirm.text
        # ti_new es TextInput, acceso directo con .text
        nueva    = self.ti_new.text.strip()
        confirma = self.ti_confirm.text.strip()

        if not nueva:
            self.lbl_err.text = 'Ingresa una nueva contraseña'
            return
        if len(nueva) < 6:
            self.lbl_err.text = 'La contraseña debe tener al menos 6 caracteres'
            return
        if nueva != confirma:
            self.lbl_err.text = 'Las contraseñas no coinciden'
            return

        self.btn_ok.disabled = True
        self.lbl_err.color = MUTED
        self.lbl_err.text = 'Guardando...'
        threading.Thread(target=self._tarea, args=(nueva,), daemon=True).start()

    def _tarea(self, nueva):
        try:
            app = App.get_running_app()
            user_id = app.current_user['id']
            pwd_hash = hashlib.sha256(nueva.encode()).hexdigest()

            from db.connection import get_connection
            conn = get_connection()
            if not conn:
                raise Exception('Sin conexión')
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE usuarios SET password=%s, must_change_password=0 WHERE id=%s",
                        (pwd_hash, user_id)
                    )
                conn.commit()
            finally:
                conn.close()

            Clock.schedule_once(lambda *_: self._continuar(), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_, m=str(e): self._error(m), 0)

    def _continuar(self):
        app = App.get_running_app()
        from utils.permisos import cargar_permisos
        permisos = app.current_user  # ya fue cargado en login
        # Ir al dashboard si tiene permiso, sino tickets
        if app.perm_dashboard:
            self.manager.current = 'dashboard'
        else:
            self.manager.current = 'tickets'

    def _error(self, msg):
        self.btn_ok.disabled = False
        self.lbl_err.color = DANGER
        self.lbl_err.text = f'Error: {msg}'
