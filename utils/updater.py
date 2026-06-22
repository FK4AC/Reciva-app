import json
import os
import subprocess
import tempfile
import threading
import urllib.request

from kivy.clock import Clock

try:
    from version import APP_VERSION
except ImportError:
    APP_VERSION = '1.0.0'


def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip('v').split('.') if x.isdigit())


def iniciar_verificacion():
    """Lanza la verificación de actualizaciones 6 segundos después de llamar."""
    from config import GITHUB_REPO
    if not GITHUB_REPO:
        return
    Clock.schedule_once(
        lambda *_: threading.Thread(
            target=lambda: _verificar(GITHUB_REPO), daemon=True
        ).start(),
        6,
    )


def _verificar(repo: str):
    try:
        url = f'https://api.github.com/repos/{repo}/releases/latest'
        req = urllib.request.Request(url, headers={'User-Agent': 'Reciva-App'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        latest_tag = data.get('tag_name', '0.0.0')
        if _parse_version(latest_tag) <= _parse_version(APP_VERSION):
            return
        download_url = next(
            (a['browser_download_url'] for a in data.get('assets', [])
             if a['name'].lower().endswith('.exe')),
            None,
        )
        if download_url:
            Clock.schedule_once(
                lambda *_: _mostrar_popup(latest_tag, download_url), 0
            )
    except Exception:
        pass


def _mostrar_popup(version: str, download_url: str):
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, Rectangle
    from widgets.components import PillButton
    from theme import TINTA, CARD, STAGE, LINE, MUTED, SUCCESS

    def _mk_bg(widget, col):
        with widget.canvas.before:
            Color(*col)
            r = Rectangle(pos=widget.pos, size=widget.size)
        widget.bind(pos=lambda _, v, _r=r: setattr(_r, 'pos', v),
                    size=lambda _, v, _r=r: setattr(_r, 'size', v))

    content = BoxLayout(orientation='vertical', spacing=0)
    _mk_bg(content, CARD)

    # ── Header ────────────────────────────────────────────
    top = BoxLayout(orientation='vertical', size_hint_y=None, height=80, padding=[22, 10])
    _mk_bg(top, TINTA)
    t_row = BoxLayout(size_hint_y=None, height=38)
    ico = Label(text='⬆', font_size=20, color=(1, 1, 1, 1),
                size_hint_x=None, width=32, halign='left', valign='middle')
    ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
    tit = Label(text='Actualización disponible', bold=True, font_size=16,
                color=(1, 1, 1, 1), halign='left', valign='middle')
    tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
    t_row.add_widget(ico)
    t_row.add_widget(tit)
    top.add_widget(t_row)
    sub = Label(text=f'Versión {version} lista para instalar',
                font_size=11, color=(0.78, 0.82, 0.87, 1),
                halign='left', valign='middle', size_hint_y=None, height=24)
    sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
    top.add_widget(sub)
    content.add_widget(top)

    # ── Body ──────────────────────────────────────────────
    body = BoxLayout(orientation='vertical', size_hint_y=1, padding=[22, 18], spacing=8)
    lbl_info = Label(
        text=('Hay una nueva versión de Reciva disponible.\n\n'
              'Al actualizar, la app se cerrará, aplicará la\n'
              'actualización y podrás abrirla de nuevo.'),
        font_name='Jakarta', font_size=13, color=TINTA,
        halign='left', valign='top',
    )
    lbl_info.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
    body.add_widget(lbl_info)
    lbl_estado = Label(text='', font_size=12, color=MUTED,
                       size_hint_y=None, height=20, halign='left', valign='middle')
    lbl_estado.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
    body.add_widget(lbl_estado)
    body.add_widget(Widget())
    content.add_widget(body)

    # ── Footer ────────────────────────────────────────────
    footer = BoxLayout(size_hint_y=None, height=56, spacing=10, padding=[18, 10])
    _mk_bg(footer, STAGE)

    popup = Popup(title='', content=content, size_hint=(0.44, 0.52),
                  background_color=CARD, separator_height=0)

    btn_later  = PillButton(text='Más tarde', bg_color=LINE, fg_color=TINTA,
                            pressed_color=STAGE, font_size=13, pill_radius=20,
                            size_hint_x=None, width=110)
    btn_update = PillButton(text='Actualizar ahora', bg_color=SUCCESS,
                            pressed_color=(0.09, 0.40, 0.16, 1),
                            font_size=13, pill_radius=20)

    def _actualizar(_):
        btn_update.disabled = True
        btn_later.disabled  = True
        lbl_estado.text  = 'Descargando…'
        lbl_estado.color = MUTED
        threading.Thread(
            target=lambda: _descargar(download_url, lbl_estado), daemon=True
        ).start()

    btn_later.bind(on_press=popup.dismiss)
    btn_update.bind(on_press=_actualizar)
    footer.add_widget(Widget())
    footer.add_widget(btn_later)
    footer.add_widget(btn_update)
    content.add_widget(footer)
    popup.open()


def _descargar(url: str, lbl_estado):
    try:
        tmp = os.path.join(tempfile.gettempdir(), 'Reciva_Setup_update.exe')

        def _progress(count, block, total):
            if total > 0:
                pct = min(int(count * block * 100 / total), 100)
                Clock.schedule_once(
                    lambda *_, p=pct: setattr(lbl_estado, 'text', f'Descargando… {p}%'), 0
                )

        urllib.request.urlretrieve(url, tmp, reporthook=_progress)
        Clock.schedule_once(lambda *_: setattr(lbl_estado, 'text', 'Instalando…'), 0)
        subprocess.Popen([tmp, '/SILENT', '/CLOSEAPPLICATIONS'])
        from kivy.app import App
        Clock.schedule_once(lambda *_: App.get_running_app().stop(), 1.5)
    except Exception as e:
        Clock.schedule_once(
            lambda *_, err=str(e): setattr(lbl_estado, 'text', f'Error: {err}'), 0
        )
