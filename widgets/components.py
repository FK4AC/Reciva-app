"""
Reciva — Design System Components
Widgets reutilizables que implementan el lenguaje visual "Recibo".
Cada clase registra su propia regla KV al cargarse.
"""
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import (
    ColorProperty, NumericProperty, BooleanProperty, StringProperty
)
from theme import VERMILLON, LADRILLO, SUCCESS, TINTA, LINE, MUTED, STAGE, CARD, BG

# ── SIDEBAR_HDR (no exportado en theme.py) ───────────────────────────────────
SIDEBAR_HDR = (0.082, 0.063, 0.055, 1)

# =============================================================================
#  SidebarButton — botón de navegación lateral con indicador activo
# =============================================================================
Builder.load_string('''
<SidebarButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: (1, 1, 1, 1) if self.is_active else (0.820, 0.761, 0.722, 1)
    font_name: 'Jakarta'
    font_size: 13
    bold: True
    halign: 'left'
    text_size: self.width - 20, None
    padding: [20, 0, 8, 0]
    canvas.before:
        Color:
            rgba: (0.294, 0.220, 0.176, 1) if self.is_active else (0, 0, 0, 0)
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: (0.788, 0.016, 0.043, 1) if self.is_active else (0, 0, 0, 0)
        Rectangle:
            pos: self.x, self.y
            size: 3, self.height
''')


class SidebarButton(Button):
    is_active = BooleanProperty(False)


# =============================================================================
#  PillButton — botón redondeado con acento de color
# =============================================================================
Builder.load_string('''
<PillButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: self.fg_color
    font_name: 'Jakarta'
    canvas.before:
        Color:
            rgba: self.pressed_color if self.state == 'down' else self.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.pill_radius]
        Color:
            rgba: self.border_color
        Line:
            rounded_rectangle: self.x, self.y, self.width, self.height, self.pill_radius
            width: 1.2
''')


class PillButton(Button):
    bg_color      = ColorProperty(VERMILLON)
    pressed_color = ColorProperty(LADRILLO)
    fg_color      = ColorProperty((1, 1, 1, 1))
    pill_radius   = NumericProperty(21)
    border_color  = ColorProperty((0, 0, 0, 0))


# =============================================================================
#  TabButton — botón de pestaña con estado activo/inactivo
# =============================================================================
Builder.load_string('''
<TabButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: self.active_fg if self.is_active else self.inactive_fg
    font_name: 'Jakarta'
    canvas.before:
        Color:
            rgba: self.active_color if self.is_active else self.inactive_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.pill_radius]
''')


class TabButton(Button):
    is_active      = BooleanProperty(False)
    active_color   = ColorProperty(VERMILLON)
    inactive_color = ColorProperty(LINE)
    active_fg      = ColorProperty((1, 1, 1, 1))
    inactive_fg    = ColorProperty(TINTA)
    pill_radius    = NumericProperty(7)


# =============================================================================
#  AccentCard — tarjeta blanca con sombra y barra lateral de color
# =============================================================================
Builder.load_string('''
<AccentCard>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0, 0, 0, 0.07
        RoundedRectangle:
            pos: self.x + 2, self.y - 3
            size: self.size
            radius: [10]
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10]
        Color:
            rgba: self.accent_color
        Rectangle:
            pos: self.pos
            size: 4, self.height
''')


class AccentCard(BoxLayout):
    accent_color = ColorProperty(SUCCESS)


# =============================================================================
#  FilterPill — contenedor redondeado para spinners y campos de búsqueda
# =============================================================================
Builder.load_string('''
<FilterPill>:
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.pill_radius]
        Color:
            rgba: self.border_color
        Line:
            rounded_rectangle: self.x, self.y, self.width, self.height, self.pill_radius
            width: 1
''')


class FilterPill(BoxLayout):
    pill_radius  = NumericProperty(21)
    border_color = ColorProperty(LINE)


# =============================================================================
#  PopupHeader — franja oscura usada en la parte superior de popups
# =============================================================================
Builder.load_string('''
<PopupHeader>:
    size_hint_y: None
    height: 56
    padding: [18, 0]
    canvas.before:
        Color:
            rgba: 0.106, 0.082, 0.071, 1
        Rectangle:
            pos: self.pos
            size: self.size
''')


class PopupHeader(BoxLayout):
    pass


# =============================================================================
#  MetaStrip — franja de metadatos (STAGE) bajo el header del popup
# =============================================================================
Builder.load_string('''
<MetaStrip>:
    size_hint_y: None
    height: 38
    spacing: 1
    canvas.before:
        Color:
            rgba: 0.984, 0.969, 0.945, 1
        Rectangle:
            pos: self.pos
            size: self.size
''')


class MetaStrip(BoxLayout):
    pass


# =============================================================================
#  TableHeader — encabezado de tabla oscuro
# =============================================================================
Builder.load_string('''
<TableHeader>:
    size_hint_y: None
    height: 42
    spacing: 2
    canvas.before:
        Color:
            rgba: 0.106, 0.082, 0.071, 1
        Rectangle:
            pos: self.pos
            size: self.size
''')


class TableHeader(BoxLayout):
    pass


# =============================================================================
#  EmptyState — estado vacío ilustrado para listas sin resultados
# =============================================================================
Builder.load_string('''
<EmptyState>:
    orientation: 'vertical'
    size_hint_y: None
    height: 180
    spacing: 6
    padding: [0, 28]
    Label:
        text: root.icon_text
        font_size: 40
        color: 0.906, 0.863, 0.812, 1
        size_hint_y: None
        height: 56
        halign: 'center'
        text_size: self.size
    Label:
        text: root.message
        font_name: 'Jakarta'
        font_size: 14
        bold: True
        color: 0.549, 0.502, 0.467, 1
        halign: 'center'
        text_size: self.size
        size_hint_y: None
        height: 28
    Label:
        text: root.subtitle
        font_name: 'Jakarta'
        font_size: 11
        color: 0.753, 0.710, 0.675, 1
        halign: 'center'
        text_size: self.size
        size_hint_y: None
        height: 20
''')


class EmptyState(BoxLayout):
    icon_text = StringProperty('○')
    message   = StringProperty('Sin resultados')
    subtitle  = StringProperty('')


# =============================================================================
#  HoverRow — fila de tabla que resalta al pasar el cursor
# =============================================================================
Builder.load_string('''
<HoverRow>:
    canvas.before:
        Color:
            rgba: self.hover_color if self._hover else self.base_color
        Rectangle:
            pos: self.pos
            size: self.size
''')


class HoverRow(BoxLayout):
    base_color  = ColorProperty((1, 1, 1, 1))
    hover_color = ColorProperty(STAGE)
    _hover      = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(parent=self._on_parent_change)

    def _on_parent_change(self, instance, parent):
        from kivy.core.window import Window
        if parent:
            Window.bind(mouse_pos=self._on_mouse_pos)
        else:
            Window.unbind(mouse_pos=self._on_mouse_pos)

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window():
            return
        try:
            inside = self.collide_point(*self.to_widget(*pos))
            if inside != self._hover:
                self._hover = inside
        except Exception:
            pass


# =============================================================================
#  Toast — notificación flotante que aparece y desaparece sola
# =============================================================================
Builder.load_string('''
<Toast>:
    size_hint: None, None
    size: 380, 48
    padding: [20, 0]
    canvas.before:
        Color:
            rgba: 0.106, 0.082, 0.071, 0.94
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [24]
    Label:
        text: root.message
        font_name: 'Jakarta'
        font_size: 13
        color: 1, 1, 1, 1
        halign: 'center'
        text_size: self.size
''')


class Toast(BoxLayout):
    message = StringProperty('')

    def show(self, duration=2.5):
        from kivy.animation import Animation
        from kivy.core.window import Window
        self.size = (380, 48)
        self.pos = (Window.width / 2 - 190, Window.height * 0.07)
        self.opacity = 0
        Window.add_widget(self)
        anim = (Animation(opacity=1, duration=0.2)
                + Animation(duration=duration)
                + Animation(opacity=0, duration=0.3))
        anim.bind(on_complete=lambda *_: Window.remove_widget(self))
        anim.start(self)


def show_toast(message, duration=2.5):
    """Muestra una notificación flotante en el centro-inferior de la ventana."""
    Toast(message=message).show(duration)


# =============================================================================
#  Helpers
# =============================================================================
def make_header_label(text, size_hint_x, font_size=11, padding_left=4):
    """Crea un Label ya configurado para usar dentro de TableHeader."""
    lbl = Label(
        text=text,
        bold=True,
        color=(0.906, 0.863, 0.812, 1),
        size_hint_x=size_hint_x,
        font_size=font_size,
        halign='left',
        valign='middle',
    )
    lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - padding_left, v[1])))
    return lbl
