from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import (Color, Rectangle, RoundedRectangle,
                            Line, Rotate, PushMatrix, PopMatrix)
from kivy.core.window import Window
from kivy.clock import Clock


class _Spinner(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), size=(44, 44), **kw)
        self._angle = 0
        self._event = None

        with self.canvas:
            Color(0.906, 0.863, 0.812, 1)
            self._track = Line(width=2.5)
            PushMatrix()
            self._rot = Rotate(angle=0, origin=(22, 22))
            Color(0.914, 0.306, 0.173, 1)
            self._arc = Line(width=2.5)
            PopMatrix()

        self.bind(pos=self._update_geom, size=self._update_geom)

    def _update_geom(self, *_):
        cx, cy, r = self.center_x, self.center_y, 16
        self._track.circle = (cx, cy, r)
        self._arc.circle   = (cx, cy, r, 0, 270)
        self._rot.origin   = (cx, cy)

    def start(self):
        self._event = Clock.schedule_interval(self._tick, 1 / 30)

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None

    def _tick(self, dt):
        self._angle = (self._angle - 10) % 360
        self._rot.angle = self._angle


class _Overlay(FloatLayout):
    def __init__(self, texto, **kw):
        super().__init__(size=Window.size, pos=(0, 0),
                         size_hint=(None, None), **kw)

        with self.canvas.before:
            Color(0, 0, 0, 0.42)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda _, v: setattr(self._bg, 'pos', v),
                  size=lambda _, v: setattr(self._bg, 'size', v))

        card = BoxLayout(
            orientation='vertical',
            size_hint=(None, None), size=(168, 100),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            spacing=8, padding=[16, 14],
        )
        with card.canvas.before:
            Color(1, 1, 1, 1)
            rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[12])
        card.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v),
                  size=lambda _, v, r=rr: setattr(r, 'size', v))

        self._spinner = _Spinner(pos_hint={'center_x': 0.5})
        card.add_widget(self._spinner)
        card.add_widget(Label(
            text=texto, font_size=11,
            color=(0.549, 0.502, 0.467, 1),
            size_hint_y=None, height=18,
            halign='center', valign='middle',
        ))
        self.add_widget(card)
        self._spinner.start()

    def dismiss(self):
        self._spinner.stop()
        if self.parent:
            Window.remove_widget(self)


# ── API pública ──────────────────────────────────────────────────────────────
_current = None


def show(texto='Cargando…'):
    global _current
    hide()
    _current = _Overlay(texto)
    Window.add_widget(_current)


def hide():
    global _current
    if _current is not None:
        _current.dismiss()
        _current = None
