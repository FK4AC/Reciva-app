import os
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from kivy.clock import Clock

from db.connection import get_connection
import utils.overlay as overlay
from utils.volcado import (
    USO_ORDEN, TARIFAS_DEFAULT,
    setup_tablas, cargar_config, guardar_config, guardar_email_config,
    cargar_tarifas, guardar_tarifas,
    generar_volcado_bd, validar_volcado_bd,
    generar_xlsx_precios, nombre_mes, periodo_actual, periodo_siguiente,
    guardar_barrios_excluidos,
)
from utils.email_smtp import enviar_volcado
from theme import (TINTA, BG, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, TEXT_SEC, SUCCESS, WARNING, DANGER)
from widgets.components import PillButton
from config import AIRE_EMAIL

# ── Helpers visuales ──────────────────────────────────────────────────────────

def _lbl(text, size=12, bold=False, color=None, halign='left', height=26):
    lbl = Label(
        text=text, font_name='Jakarta', font_size=size, bold=bold,
        color=color or TINTA, halign=halign, valign='middle',
        size_hint_y=None, height=height,
    )
    lbl.bind(size=lambda w, _: setattr(w, 'text_size', w.size))
    return lbl


def _inp(text='', readonly=False, hint=''):
    bg = STAGE if readonly else CARD
    ti = TextInput(
        text=str(text), hint_text=hint, font_name='Jakarta', font_size=13,
        size_hint_y=None, height=36, multiline=False, readonly=readonly,
        foreground_color=TINTA, background_color=bg,
        cursor_color=VERMILLON, padding=[10, 8],
    )
    return ti


def _fila_bg(widget, idx):
    with widget.canvas.before:
        Color(*(STAGE if idx % 2 == 0 else CARD))
        bg = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda w, v, r=bg: setattr(r, 'pos', v),
                size=lambda w, v, r=bg: setattr(r, 'size', v))


_ETIQUETAS = {
    'valor':        'Valor factura ($)',
    'precio_xlsx':  'Precio XLSX (AIR-E)',
    'sub_val':      'Subsidio / Contribución $',
    'sub_pct':      'Subsidio / Contribución %',
    'tarifa_media': 'Tarifa media',
    'TC': 'TC', 'TLU': 'TLU', 'TBL': 'TBL',
    'TRT': 'TRT', 'TDF': 'TDF', 'TTL': 'TTL',
}
_CAMPOS = list(_ETIQUETAS.keys())


# ── Screen ────────────────────────────────────────────────────────────────────

class VolcadoScreen(Screen):
    mensaje_tarifas = StringProperty('')

    _config:  dict = {}
    _tarifas: dict = {}
    _tab_activa: str = 'tarifas'
    _tabla_tar_ws: dict = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self):
        overlay.show('Cargando volcado…')
        threading.Thread(target=self._tarea_inicio, daemon=True).start()

    def _tarea_inicio(self):
        conn = get_connection()
        config, tarifas, error = {}, dict(TARIFAS_DEFAULT), None
        if conn:
            try:
                setup_tablas(conn)
                config  = cargar_config(conn)
                tarifas = cargar_tarifas(conn)
            except Exception as e:
                error = str(e)
            finally:
                conn.close()
        self._config  = config
        self._tarifas = tarifas
        Clock.schedule_once(lambda *_: self._post_inicio(error), 0)

    def _post_inicio(self, error):
        overlay.hide()
        if error:
            self.ids.lbl_estado.text = f'BD: {error}'
        carpeta = self._config.get('carpeta_salida', '').strip()
        if not carpeta or not os.path.exists(carpeta):
            carpeta = os.path.join(os.path.expanduser('~'), 'Documents')
            self._config['carpeta_salida'] = carpeta
        self.ids.lbl_salida.text = carpeta
        try:
            self.ids.ti_barrios.text = self._config.get('barrios_excluidos', '')
        except Exception:
            pass

        # Período: próximo mes por defecto
        hoy_aaaamm = periodo_actual()
        prox = periodo_siguiente(hoy_aaaamm)
        self.ids.inp_periodo.text = prox

        self.cambiar_tab(self._tab_activa)
        self._construir_tabla_tarifas()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def cambiar_tab(self, tab):
        self._tab_activa = tab
        tabs   = {'tarifas': self.ids.tab_tarifas,
                  'exportar': self.ids.tab_exportar}
        panels = {'tarifas': self.ids.panel_tarifas,
                  'exportar': self.ids.panel_exportar}
        for k, btn in tabs.items():
            btn.is_active = (k == tab)
        for k, pan in panels.items():
            active = (k == tab)
            pan.opacity     = 1 if active else 0
            pan.disabled    = not active
            pan.size_hint_y = 1 if active else None
            if not active:
                pan.height = 0

    # ── Carpeta salida ────────────────────────────────────────────────────────

    def cambiar_carpeta_salida(self):
        import subprocess
        inicial = self._config.get('carpeta_salida', '') or os.path.expanduser('~')
        script = (
            'Add-Type -AssemblyName System.Windows.Forms;'
            '$d=New-Object System.Windows.Forms.FolderBrowserDialog;'
            '$d.Description="Seleccionar carpeta de exportacion del volcado";'
            f'$d.SelectedPath="{inicial}";'
            '$d.ShowNewFolderButton=$true;'
            'if($d.ShowDialog()-eq"OK"){{Write-Output $d.SelectedPath}}'
        )
        def _pick():
            r = subprocess.run(
                ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                capture_output=True, text=True, encoding='utf-8',
            )
            carpeta = r.stdout.strip()
            if carpeta and os.path.isdir(carpeta):
                Clock.schedule_once(lambda *_: self._aplicar_carpeta(carpeta), 0)

        threading.Thread(target=_pick, daemon=True).start()

    def _aplicar_carpeta(self, carpeta):
        self.ids.lbl_salida.text = carpeta
        self._config['carpeta_salida'] = carpeta
        threading.Thread(
            target=lambda: self._guardar_config_bg(carpeta, self._config.get('email_destino', '')),
            daemon=True,
        ).start()

    def guardar_barrios(self):
        ti = getattr(self.ids, 'ti_barrios', None)
        texto = ti.text if ti else ''
        lbl = getattr(self.ids, 'lbl_barrios_estado', None)
        if lbl:
            lbl.text = 'Guardando…'
            lbl.color = MUTED
        def _set_lbl(text, color):
            _lbl = getattr(self.ids, 'lbl_barrios_estado', None)
            if _lbl:
                _lbl.text = text
                _lbl.color = color

        def _bg():
            conn = get_connection()
            if not conn:
                Clock.schedule_once(lambda *_: _set_lbl('Sin conexión', DANGER), 0)
                return
            try:
                guardar_barrios_excluidos(conn, texto)
                self._config['barrios_excluidos'] = texto
                Clock.schedule_once(lambda *_: _set_lbl('Guardado ✓', SUCCESS), 0)
            except Exception as e:
                msg = f'Error: {e}'
                Clock.schedule_once(lambda *_, m=msg: _set_lbl(m, DANGER), 0)
            finally:
                conn.close()
        threading.Thread(target=_bg, daemon=True).start()

    def _guardar_config_bg(self, carpeta_salida, email_destino):
        conn = get_connection()
        if conn:
            try:
                guardar_config(conn, carpeta_salida, email_destino)
            finally:
                conn.close()

    # ── Tab Tarifas ───────────────────────────────────────────────────────────

    def _construir_tabla_tarifas(self):
        contenedor = self.ids.tabla_tarifas
        contenedor.clear_widgets()
        self._tabla_tar_ws = {}
        for idx, uso in enumerate(USO_ORDEN):
            if uso not in self._tarifas:
                continue
            t = self._tarifas[uso]
            fila = BoxLayout(orientation='horizontal', size_hint_y=None,
                             height=44, spacing=0, padding=[12, 0])
            _fila_bg(fila, idx)

            lbl_uso = _lbl(uso, size=12, height=44)
            lbl_uso.size_hint_x = 0.30
            lbl_valor = _lbl(f'${t["valor"]:,}', size=12, height=44, halign='center')
            lbl_valor.size_hint_x = 0.14
            lbl_pct = _lbl(t['sub_pct'], size=12, height=44, halign='center')
            lbl_pct.size_hint_x = 0.14
            lbl_media = _lbl(t['tarifa_media'], size=12, height=44, halign='center')
            lbl_media.size_hint_x = 0.22

            btn_e = PillButton(text='Editar', font_size=11,
                               bg_color=TINTA, pressed_color=LADRILLO,
                               pill_radius=6)
            btn_e.bind(on_press=lambda _, u=uso: self._popup_tarifa(u))
            wrap = BoxLayout(size_hint_x=0.20, padding=[10, 8])
            wrap.add_widget(btn_e)

            for w in [lbl_uso, lbl_valor, lbl_pct, lbl_media, wrap]:
                fila.add_widget(w)
            self._tabla_tar_ws[uso] = {'lbl_valor': lbl_valor,
                                        'lbl_pct': lbl_pct,
                                        'lbl_media': lbl_media}
            contenedor.add_widget(fila)

    def _refrescar_tabla_tarifas(self):
        for uso, ws in self._tabla_tar_ws.items():
            if uso not in self._tarifas:
                continue
            t = self._tarifas[uso]
            ws['lbl_valor'].text = f'${t["valor"]:,}'
            ws['lbl_pct'].text   = t['sub_pct']
            ws['lbl_media'].text = t['tarifa_media']

    def _popup_tarifa(self, uso):
        try:
            self._popup_tarifa_impl(uso)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.ids.lbl_estado.text = f'Error: {e}'

    def _popup_tarifa_impl(self, uso):
        raw     = self._tarifas.get(uso, {})
        default = TARIFAS_DEFAULT.get(uso, {})
        t = {}
        for c in _CAMPOS:
            v = raw.get(c)
            if v is None or v == '':
                v = default.get(c, '')
            t[c] = v

        def _parse(s):
            try:
                return float(str(s).strip().replace('.', '').replace(',', '.'))
            except Exception:
                return 0.0

        def _fmt(v, dec=2):
            s = f'{abs(v):,.{dec}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            return ('-' if v < 0 else '') + s

        _EDITABLES  = ['sub_pct', 'TC', 'TLU', 'TBL', 'TRT', 'TDF', 'TTL']
        _CALCULADOS = ['tarifa_media', 'sub_val', 'valor', 'precio_xlsx']
        AZUL  = (0.200, 0.470, 0.820, 1)
        VERDE = (0.149, 0.600, 0.314, 1)
        NARAN = (0.820, 0.420, 0.098, 1)
        _CALC_META = {
            'tarifa_media': ('TARIFA MEDIA',           TINTA),
            'sub_val':      ('SUBSIDIO / CONTRIBUCIÓN', NARAN),
            'valor':        ('VALOR FACTURA',           VERDE),
            'precio_xlsx':  ('PRECIO XLSX (AIR-E)',     AZUL),
        }
        _COMP_LABEL = {
            'sub_pct': 'Subsidio %',
            'TC': 'TC', 'TLU': 'TLU', 'TBL': 'TBL',
            'TRT': 'TRT', 'TDF': 'TDF', 'TTL': 'TTL',
        }

        inputs   = {}
        lbl_calc = {}

        def _mk_bg(widget, col):
            with widget.canvas.before:
                Color(*col)
                _r = Rectangle(pos=widget.pos, size=widget.size)
            widget.bind(pos=lambda _, v, r=_r: setattr(r, 'pos', v),
                        size=lambda _, v, r=_r: setattr(r, 'size', v))

        def _mk_div(parent):
            div = BoxLayout(size_hint_y=None, height=1)
            with div.canvas.before:
                Color(*LINE)
                _dr = Rectangle(pos=div.pos, size=div.size)
            div.bind(pos=lambda _, v, r=_dr: setattr(r, 'pos', v),
                     size=lambda _, v, r=_dr: setattr(r, 'size', v))
            parent.add_widget(div)

        def _sec_label(txt, parent):
            lbl = Label(text=txt, font_size=10, color=MUTED, bold=True,
                        size_hint_y=None, height=16, halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            parent.add_widget(lbl)

        def _mk_field(campo, val):
            wrap = BoxLayout(size_hint_y=None, height=34)
            with wrap.canvas.before:
                Color(1, 1, 1, 1)
                _wbg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[6])
                Color(*LINE)
                _wbd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[6])
            wrap.bind(
                pos =lambda _, v, a=_wbg, b=_wbd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
                size=lambda _, v, a=_wbg, b=_wbd: (setattr(a, 'size', v), setattr(b, 'size', v)),
            )
            ti = TextInput(
                text=str(val), multiline=False,
                background_normal='', background_active='', background_color=(0, 0, 0, 0),
                foreground_color=TINTA, cursor_color=VERMILLON,
                padding=[10, 8], font_size=13,
            )
            wrap.add_widget(ti)
            inputs[campo] = ti
            return wrap

        # ── Root ──────────────────────────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        _mk_bg(content, CARD)

        # ── Header ────────────────────────────────────────────────────
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=82, padding=[22, 10])
        _mk_bg(top, TINTA)

        t_row = BoxLayout(size_hint_y=None, height=38)
        ico = Label(text='📋', font_size=20, color=(1, 1, 1, 1),
                    size_hint_x=None, width=32, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        lbl_tit = Label(text=uso, bold=True, font_size=16, color=(1, 1, 1, 1),
                        halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        t_row.add_widget(ico)
        t_row.add_widget(lbl_tit)
        top.add_widget(t_row)

        s_row = BoxLayout(size_hint_y=None, height=24)
        lbl_sub = Label(text='Configuración de tarifa de facturación', font_size=11,
                        color=(0.780, 0.820, 0.867, 1), halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        s_row.add_widget(lbl_sub)
        top.add_widget(s_row)
        content.add_widget(top)

        # ── Body (dos columnas) ───────────────────────────────────────
        body = BoxLayout(orientation='horizontal', size_hint_y=1,
                         padding=[16, 14], spacing=18)

        # ── Columna izquierda: campos editables ───────────────────────
        left = BoxLayout(orientation='vertical', size_hint_x=0.54, spacing=6)

        _sec_label('COMPONENTES', left)
        _mk_div(left)

        # sub_pct — fila destacada
        row_sp = BoxLayout(size_hint_y=None, height=34, spacing=8)
        lbl_sp = Label(text='Subsidio %', font_size=11, color=MUTED,
                       size_hint_x=0.46, halign='right', valign='middle')
        lbl_sp.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        row_sp.add_widget(lbl_sp)
        row_sp.add_widget(_mk_field('sub_pct', t.get('sub_pct', '')))
        left.add_widget(row_sp)

        _mk_div(left)

        for campo in ['TC', 'TLU', 'TBL', 'TRT', 'TDF', 'TTL']:
            row = BoxLayout(size_hint_y=None, height=34, spacing=8)
            lbl_c = Label(text=campo, font_size=11, color=MUTED, bold=True,
                          size_hint_x=0.28, halign='right', valign='middle')
            lbl_c.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            row.add_widget(lbl_c)
            row.add_widget(_mk_field(campo, t.get(campo, '')))
            left.add_widget(row)

        left.add_widget(Widget())
        body.add_widget(left)

        # ── Columna derecha: resultados calculados ────────────────────
        right = BoxLayout(orientation='vertical', size_hint_x=0.46, spacing=10)

        _sec_label('RESULTADO', right)
        _mk_div(right)

        for campo in _CALCULADOS:
            etiq, accent = _CALC_META[campo]
            card = BoxLayout(orientation='vertical', padding=[14, 8], spacing=2,
                             size_hint_y=None, height=70)
            with card.canvas.before:
                Color(0, 0, 0, 0.04)
                _sh  = RoundedRectangle(pos=card.pos, size=card.size, radius=[8])
                Color(1, 1, 1, 1)
                _cbg = RoundedRectangle(pos=card.pos, size=card.size, radius=[8])
                Color(*accent)
                _bar = Rectangle(pos=card.pos, size=(4, 0))
            def _upd(inst, v, sh=_sh, bg=_cbg, bar=_bar):
                sh.pos  = (inst.x + 2, inst.y - 2)
                sh.size = inst.size
                bg.pos  = inst.pos
                bg.size = inst.size
                bar.pos  = (inst.x, inst.y)
                bar.size = (4, inst.height)
            card.bind(pos=_upd, size=_upd)

            lbl_et = Label(text=etiq, font_size=9, color=MUTED, bold=True,
                           halign='left', valign='middle',
                           size_hint_y=None, height=16)
            lbl_et.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            card.add_widget(lbl_et)

            lbl_v = Label(text='—', font_size=20, bold=True, color=accent,
                          halign='left', valign='middle',
                          size_hint_y=None, height=30)
            lbl_v.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            card.add_widget(lbl_v)

            lbl_calc[campo] = lbl_v
            right.add_widget(card)

        right.add_widget(Widget())
        body.add_widget(right)
        content.add_widget(body)

        # ── Footer fijo ───────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _mk_bg(footer, STAGE)

        lbl_err_tar = Label(text='', font_size=12, color=DANGER,
                            halign='left', valign='middle')
        lbl_err_tar.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        footer.add_widget(lbl_err_tar)

        btn_can = PillButton(text='Cancelar', bg_color=LINE, fg_color=TINTA,
                             pressed_color=STAGE, font_size=13, pill_radius=20,
                             size_hint_x=None, width=110)
        btn_ok  = PillButton(text='Guardar cambios', bg_color=SUCCESS,
                             pressed_color=(0.09, 0.40, 0.16, 1),
                             font_size=13, pill_radius=20,
                             size_hint_x=None, width=160)
        footer.add_widget(btn_can)
        footer.add_widget(btn_ok)
        content.add_widget(footer)

        popup = Popup(title='', content=content, size_hint=(0.58, 0.86),
                      background_color=CARD, separator_height=0)

        def recalcular(*_):
            try:
                tm  = sum(_parse(inputs[c].text) for c in ['TC', 'TLU', 'TBL', 'TRT', 'TDF', 'TTL'])
                pct = _parse(inputs['sub_pct'].text) / 100
                sv  = tm * pct
                val = tm + sv
                prefix = '+' if sv >= 0 else ''
                lbl_calc['tarifa_media'].text = _fmt(tm)
                lbl_calc['sub_val'].text      = prefix + _fmt(sv)
                lbl_calc['valor'].text        = f'${int(round(val)):,}'
                lbl_calc['precio_xlsx'].text  = _fmt(val)
            except Exception:
                pass

        for campo in _EDITABLES:
            inputs[campo].bind(text=recalcular)
        recalcular()

        def guardar(_):
            try:
                tm  = sum(_parse(inputs[c].text) for c in ['TC', 'TLU', 'TBL', 'TRT', 'TDF', 'TTL'])
                pct = _parse(inputs['sub_pct'].text) / 100
                sv  = tm * pct
                val = tm + sv
                prefix = '+' if sv >= 0 else ''
                nueva = {
                    'valor':        int(round(val)),
                    'precio_xlsx':  round(val, 2),
                    'sub_pct':      inputs['sub_pct'].text.strip(),
                    'sub_val':      prefix + _fmt(sv),
                    'tarifa_media': _fmt(tm),
                    'TC':  inputs['TC'].text.strip(),
                    'TLU': inputs['TLU'].text.strip(),
                    'TBL': inputs['TBL'].text.strip(),
                    'TRT': inputs['TRT'].text.strip(),
                    'TDF': inputs['TDF'].text.strip(),
                    'TTL': inputs['TTL'].text.strip(),
                }
                self._tarifas[uso] = nueva
                self._refrescar_tabla_tarifas()
                lbl_err_tar.text  = 'Guardando…'
                lbl_err_tar.color = MUTED
                btn_ok.disabled   = True
                threading.Thread(
                    target=lambda n=dict(nueva): self._guardar_tarifa_bg(uso, n, popup, lbl_err_tar, btn_ok),
                    daemon=True,
                ).start()
            except Exception as e:
                lbl_err_tar.text  = f'Error: {e}'
                lbl_err_tar.color = DANGER

        btn_can.bind(on_press=popup.dismiss)
        btn_ok.bind(on_press=guardar)
        popup.open()

    def _guardar_tarifa_bg(self, uso, nueva, popup, lbl_err, btn_ok):
        conn = get_connection()
        if not conn:
            Clock.schedule_once(lambda *_: (
                setattr(lbl_err, 'text', 'Sin conexión a BD'),
                setattr(lbl_err, 'color', DANGER),
                setattr(btn_ok, 'disabled', False),
            ), 0)
            return
        try:
            guardar_tarifas(conn, {uso: nueva})
            Clock.schedule_once(lambda *_: popup.dismiss(), 0)
        except Exception as e:
            msg = f'Error BD: {e}'
            Clock.schedule_once(lambda *_, m=msg: (
                setattr(lbl_err, 'text', m),
                setattr(lbl_err, 'color', DANGER),
                setattr(btn_ok, 'disabled', False),
            ), 0)
        finally:
            conn.close()

    def guardar_bd_tarifas(self):
        self.mensaje_tarifas = 'Guardando…'
        tarifas = dict(self._tarifas)
        threading.Thread(target=lambda: self._tarea_guardar_tarifas(tarifas),
                         daemon=True).start()

    def _tarea_guardar_tarifas(self, tarifas):
        conn = get_connection()
        if not conn:
            Clock.schedule_once(
                lambda *_: setattr(self, 'mensaje_tarifas', 'Sin conexión'), 0)
            return
        try:
            guardar_tarifas(conn, tarifas)
            msg = 'Tarifas guardadas ✓'
        except Exception as e:
            msg = f'Error: {e}'
        finally:
            conn.close()
        Clock.schedule_once(lambda *_, m=msg: setattr(self, 'mensaje_tarifas', m), 0)

    # ── Tab Exportar ──────────────────────────────────────────────────────────

    def validar(self):
        periodo = self.ids.inp_periodo.text.strip()
        if len(periodo) != 6 or not periodo.isdigit():
            self.ids.lbl_validacion.text = 'Período inválido (formato AAAAMM)'
            return
        ti = getattr(self.ids, 'ti_barrios', None)
        barrios = ti.text if ti else ''
        self.ids.lbl_validacion.text = 'Validando…'
        threading.Thread(target=lambda: self._tarea_validar(periodo, barrios), daemon=True).start()

    def _tarea_validar(self, periodo, barrios):
        conn = get_connection()
        if not conn:
            Clock.schedule_once(
                lambda *_: setattr(self.ids.lbl_validacion, 'text', 'Sin conexión'), 0)
            return
        try:
            errores = validar_volcado_bd(conn, self._tarifas, periodo, barrios)
            excluidos_list = [b.strip() for b in barrios.splitlines() if b.strip()]
            cur = conn.cursor()
            # Total incluidos (con filtro de barrios)
            if excluidos_list:
                ph = ','.join(['%s'] * len(excluidos_list))
                cur.execute(f"""
                    SELECT COUNT(*) FROM suscriptores
                    WHERE uso_volcado IS NOT NULL AND uso_volcado != ''
                      AND (barrio IS NULL OR barrio NOT IN ({ph}))
                """, excluidos_list)
                total = cur.fetchone()[0]
                cur.execute(f"""
                    SELECT uso_volcado, COUNT(*) FROM suscriptores
                    WHERE uso_volcado IS NOT NULL AND uso_volcado != ''
                      AND (barrio IS NULL OR barrio NOT IN ({ph}))
                    GROUP BY uso_volcado ORDER BY 2 DESC
                """, excluidos_list)
                dist = cur.fetchall()
                cur.execute(f"""
                    SELECT COUNT(*) FROM suscriptores
                    WHERE uso_volcado IS NOT NULL AND uso_volcado != ''
                      AND barrio IN ({ph})
                """, excluidos_list)
                n_excluidos = cur.fetchone()[0]
            else:
                cur.execute("SELECT COUNT(*) FROM suscriptores WHERE uso_volcado IS NOT NULL AND uso_volcado != ''")
                total = cur.fetchone()[0]
                cur.execute("SELECT uso_volcado, COUNT(*) FROM suscriptores WHERE uso_volcado IS NOT NULL GROUP BY uso_volcado ORDER BY 2 DESC")
                dist = cur.fetchall()
                n_excluidos = 0
            cur.close()
            if errores:
                msg = f'{len(errores)} error(es):\n' + '\n'.join(f'  • {e}' for e in errores[:8])
            else:
                excl_txt = f'  ({n_excluidos} excluidos por barrio)' if n_excluidos else ''
                lineas = [f'Sin errores  ✓   {total} suscriptores listos para {nombre_mes(periodo)}{excl_txt}']
                for uso, cnt in dist:
                    lineas.append(f'  • {uso}: {cnt}')
                msg = '\n'.join(lineas)
        except Exception as e:
            msg = f'Error: {e}'
        finally:
            conn.close()
        Clock.schedule_once(lambda *_, m=msg: setattr(self.ids.lbl_validacion, 'text', m), 0)

    def exportar(self):
        periodo = self.ids.inp_periodo.text.strip()
        if len(periodo) != 6 or not periodo.isdigit():
            self.ids.lbl_export_estado.text = 'Período inválido (formato AAAAMM)'
            return
        salida = self._config.get('carpeta_salida', '').strip()
        if not salida or not os.path.exists(salida):
            salida = os.path.join(os.path.expanduser('~'), 'Documents')
            self._config['carpeta_salida'] = salida
            self.ids.lbl_salida.text = salida
        ti = getattr(self.ids, 'ti_barrios', None)
        barrios = ti.text if ti else ''
        self.ids.lbl_export_estado.text = 'Generando…'
        overlay.show('Generando volcado…')
        threading.Thread(
            target=lambda: self._tarea_exportar(periodo, salida, barrios), daemon=True,
        ).start()

    def _tarea_exportar(self, periodo, salida, barrios):
        conn = get_connection()
        if not conn:
            Clock.schedule_once(
                lambda *_: self._post_exportar('Sin conexión a BD', None, None), 0)
            return
        try:
            totales, errores = generar_volcado_bd(conn, self._tarifas, salida, periodo, barrios)
            n_prin = totales.get('principal', 0)
            n_h1   = totales.get('hoja1', 0)
            msg = (f'5 archivos generados  •  {n_prin} principal + {n_h1} hoja1'
                   + (f'  •  {len(errores)} advertencias' if errores else ''))
        except Exception as e:
            msg = f'Error: {e}'
            salida = None
            errores = []
        finally:
            conn.close()
        Clock.schedule_once(
            lambda *_, m=msg, s=salida, p=periodo: self._post_exportar(m, s, p), 0)

    def _post_exportar(self, msg, carpeta_salida, periodo):
        overlay.hide()
        self.ids.lbl_export_estado.text = msg
        if carpeta_salida and 'Error' not in msg and periodo:
            archivos = [
                os.path.join(carpeta_salida, f'INGESAM_VOLCADO_2087_{periodo}.txt'),
                os.path.join(carpeta_salida, f'INFO_ADICIONAL_INGESAM_2087_{periodo}.txt'),
                os.path.join(carpeta_salida, f'Hoja1_INGESAM_VOLCADO_2087_{periodo}.txt'),
                os.path.join(carpeta_salida, f'Hoja1_INFO_ADICIONAL_INGESAM_2087_{periodo}.txt'),
                os.path.join(carpeta_salida, 'TABLA_PRECIOS_ASEO.xlsx'),
            ]
            self._popup_enviar(archivos, periodo)

    # ── Config correo ─────────────────────────────────────────────────────────

    def popup_config_email(self):
        AZUL = (0.200, 0.470, 0.820, 1)
        PURP = (0.502, 0.251, 0.671, 1)

        def _mk_bg(widget, col):
            with widget.canvas.before:
                Color(*col)
                _r = Rectangle(pos=widget.pos, size=widget.size)
            widget.bind(pos=lambda _, v, r=_r: setattr(r, 'pos', v),
                        size=lambda _, v, r=_r: setattr(r, 'size', v))

        def _section(txt, parent):
            lbl = Label(text=txt, font_size=10, color=MUTED, bold=True,
                        size_hint_y=None, height=18, halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            parent.add_widget(lbl)

        def _field_wrap(parent, accent=TINTA):
            wrap = BoxLayout(size_hint_y=None, height=44)
            with wrap.canvas.before:
                Color(1, 1, 1, 1)
                _wbg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
                Color(*LINE)
                _wbd = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[8])
                Color(*accent)
                _bar = Rectangle(pos=wrap.pos, size=(3, 0))
            def _upd(inst, v, a=_wbg, b=_wbd, c=_bar):
                a.pos, a.size = inst.pos, inst.size
                b.pos, b.size = inst.pos, inst.size
                c.pos, c.size = (inst.x, inst.y), (3, inst.height)
            wrap.bind(pos=_upd, size=_upd)
            parent.add_widget(wrap)
            return wrap

        def _mk_div(parent):
            div = BoxLayout(size_hint_y=None, height=1)
            with div.canvas.before:
                Color(*LINE)
                _dr = Rectangle(pos=div.pos, size=div.size)
            div.bind(pos=lambda _, v, r=_dr: setattr(r, 'pos', v),
                     size=lambda _, v, r=_dr: setattr(r, 'size', v))
            parent.add_widget(div)

        # ── Root ──────────────────────────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        _mk_bg(content, CARD)

        # ── Header ────────────────────────────────────────────────────
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=82, padding=[22, 10])
        _mk_bg(top, TINTA)
        t_row = BoxLayout(size_hint_y=None, height=38)
        ico = Label(text='✉', font_size=20, color=(1, 1, 1, 1),
                    size_hint_x=None, width=32, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        lbl_tit = Label(text='Configuración de correo', bold=True, font_size=17,
                        color=(1, 1, 1, 1), halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        t_row.add_widget(ico); t_row.add_widget(lbl_tit)
        top.add_widget(t_row)
        s_row = BoxLayout(size_hint_y=None, height=24)
        lbl_sub = Label(text='Remitente SMTP y destinatarios del volcado',
                        font_size=11, color=(0.780, 0.820, 0.867, 1),
                        halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        s_row.add_widget(lbl_sub)
        top.add_widget(s_row)
        content.add_widget(top)

        # ── Body ──────────────────────────────────────────────────────
        body = BoxLayout(orientation='vertical', size_hint_y=1,
                         padding=[20, 14], spacing=8)

        # — Correo emisor
        _section('CORREO EMISOR (remitente)', body)
        wrap_user = _field_wrap(body, AZUL)
        ti_user = TextInput(
            text=self._config.get('smtp_user', ''),
            hint_text='correo@gmail.com', multiline=False,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=AZUL,
            hint_text_color=MUTED, padding=[14, 12], font_size=13,
        )
        wrap_user.add_widget(ti_user)

        # — Contraseña de aplicación (con toggle mostrar/ocultar)
        _section('CONTRASEÑA DE APLICACIÓN (Google App Password)', body)
        wrap_pw = BoxLayout(size_hint_y=None, height=44, spacing=6)
        field_pw = _field_wrap(wrap_pw, PURP)
        ti_pw = TextInput(
            text=self._config.get('smtp_password', ''),
            hint_text='xxxx xxxx xxxx xxxx', multiline=False, password=True,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=PURP,
            hint_text_color=MUTED, padding=[14, 12], font_size=13,
        )
        field_pw.add_widget(ti_pw)
        btn_show = PillButton(text='Ver', size_hint_x=None, width=52, font_size=11,
                              bg_color=LINE, fg_color=TINTA, pressed_color=STAGE,
                              pill_radius=8)
        def _toggle_pw(_):
            ti_pw.password = not ti_pw.password
            btn_show.text = 'Ocultar' if not ti_pw.password else 'Ver'
        btn_show.bind(on_press=_toggle_pw)
        wrap_pw.add_widget(btn_show)
        body.add_widget(wrap_pw)

        # — Destinatarios volcado
        _mk_div(body)
        _section('DESTINATARIOS DEL VOLCADO  (uno por línea)', body)

        dest_raw = self._config.get('smtp_destinatarios', '') \
                   or self._config.get('email_destino', '') or AIRE_EMAIL

        wrap_dest = BoxLayout(size_hint_y=None, height=90)
        with wrap_dest.canvas.before:
            Color(1, 1, 1, 1)
            _dbg = RoundedRectangle(pos=wrap_dest.pos, size=wrap_dest.size, radius=[8])
            Color(*LINE)
            _dbd = RoundedRectangle(pos=wrap_dest.pos, size=wrap_dest.size, radius=[8])
        wrap_dest.bind(
            pos =lambda _, v, a=_dbg, b=_dbd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
            size=lambda _, v, a=_dbg, b=_dbd: (setattr(a, 'size', v), setattr(b, 'size', v)),
        )
        dest_txt = dest_raw.replace(',', '\n')
        ti_dest = TextInput(
            text=dest_txt,
            hint_text='correo1@ejemplo.com\ncorreo2@ejemplo.com',
            multiline=True,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=TINTA,
            hint_text_color=MUTED, padding=[14, 10], font_size=12,
        )
        wrap_dest.add_widget(ti_dest)
        body.add_widget(wrap_dest)

        lbl_err = Label(text='', font_size=11, color=DANGER,
                        size_hint_y=None, height=18, halign='left', valign='middle')
        lbl_err.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_err)

        body.add_widget(Widget())
        content.add_widget(body)

        # ── Footer ────────────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _mk_bg(footer, STAGE)

        popup = Popup(title='', content=content, size_hint=(0.50, 0.80),
                      background_color=CARD, separator_height=0)

        def _guardar(_):
            user = ti_user.text.strip()
            pw   = ti_pw.text.strip()
            dest = ti_dest.text.strip()
            if not user or '@' not in user:
                lbl_err.text = '⚠  Ingresa un correo emisor válido'
                return
            if not pw:
                lbl_err.text = '⚠  Ingresa la contraseña de aplicación'
                return
            self._config['smtp_user']          = user
            self._config['smtp_password']       = pw
            self._config['smtp_destinatarios']  = dest
            lbl_err.color = MUTED
            lbl_err.text  = 'Guardando…'
            btn_ok.disabled = True

            def _bg():
                conn = get_connection()
                if not conn:
                    Clock.schedule_once(lambda *_: (
                        setattr(lbl_err, 'color', DANGER),
                        setattr(lbl_err, 'text', '⚠  Sin conexión — configuración no guardada en BD'),
                        setattr(btn_ok, 'disabled', False),
                    ), 0)
                    return
                try:
                    guardar_email_config(conn, user, pw, dest)
                    Clock.schedule_once(lambda *_: popup.dismiss(), 0)
                except Exception as e:
                    msg = f'⚠  Error al guardar: {e}'
                    Clock.schedule_once(lambda *_, m=msg: (
                        setattr(lbl_err, 'color', DANGER),
                        setattr(lbl_err, 'text', m),
                        setattr(btn_ok, 'disabled', False),
                    ), 0)
                finally:
                    conn.close()

            threading.Thread(target=_bg, daemon=True).start()

        btn_can = PillButton(text='Cancelar', bg_color=LINE, fg_color=TINTA,
                             pressed_color=STAGE, font_size=13, pill_radius=20,
                             size_hint_x=None, width=110)
        btn_ok  = PillButton(text='Guardar', bg_color=SUCCESS,
                             pressed_color=(0.09, 0.40, 0.16, 1),
                             font_size=13, pill_radius=20,
                             size_hint_x=None, width=120)
        footer.add_widget(Widget())
        footer.add_widget(btn_can)
        footer.add_widget(btn_ok)
        btn_can.bind(on_press=popup.dismiss)
        btn_ok.bind(on_press=_guardar)
        content.add_widget(footer)
        popup.open()

    def _popup_enviar(self, archivos, periodo):
        nombres = [os.path.basename(a) for a in archivos]
        periodo_txt = nombre_mes(periodo)

        # Destinatarios configurados (uno por línea → lista)
        dest_raw = (self._config.get('smtp_destinatarios', '')
                    or self._config.get('email_destino', '') or AIRE_EMAIL)
        dest_txt = dest_raw.replace(',', '\n')

        def _mk_bg(widget, col):
            with widget.canvas.before:
                Color(*col)
                _r = Rectangle(pos=widget.pos, size=widget.size)
            widget.bind(pos=lambda _, v, r=_r: setattr(r, 'pos', v),
                        size=lambda _, v, r=_r: setattr(r, 'size', v))

        content = BoxLayout(orientation='vertical', spacing=0)
        _mk_bg(content, CARD)

        # Header
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=82, padding=[22, 10])
        _mk_bg(top, TINTA)
        t_row = BoxLayout(size_hint_y=None, height=38)
        ico = Label(text='✉', font_size=20, color=(1, 1, 1, 1),
                    size_hint_x=None, width=32, halign='left', valign='middle')
        ico.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        lbl_tit = Label(text=f'Enviar volcado — {periodo_txt}', bold=True,
                        font_size=15, color=(1, 1, 1, 1), halign='left', valign='middle')
        lbl_tit.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        t_row.add_widget(ico); t_row.add_widget(lbl_tit)
        top.add_widget(t_row)
        s_row = BoxLayout(size_hint_y=None, height=24)
        lbl_sub = Label(text=f'{len(nombres)} archivos adjuntos',
                        font_size=11, color=(0.780, 0.820, 0.867, 1),
                        halign='left', valign='middle')
        lbl_sub.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        s_row.add_widget(lbl_sub)
        top.add_widget(s_row)
        content.add_widget(top)

        # Body
        body = BoxLayout(orientation='vertical', size_hint_y=1, padding=[20, 14], spacing=8)

        arch_lbl = Label(
            text='\n'.join(f'  • {n}' for n in nombres),
            font_size=11, color=MUTED, halign='left', valign='top',
            size_hint_y=None, height=max(18 * len(nombres), 18),
        )
        arch_lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(arch_lbl)

        sec = Label(text='DESTINATARIOS  (uno por línea)', font_size=10, color=MUTED,
                    bold=True, size_hint_y=None, height=18, halign='left', valign='middle')
        sec.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(sec)

        wrap_dest = BoxLayout(size_hint_y=None, height=80)
        with wrap_dest.canvas.before:
            Color(1, 1, 1, 1)
            _dbg = RoundedRectangle(pos=wrap_dest.pos, size=wrap_dest.size, radius=[8])
            Color(*LINE)
            _dbd = RoundedRectangle(pos=wrap_dest.pos, size=wrap_dest.size, radius=[8])
        wrap_dest.bind(
            pos =lambda _, v, a=_dbg, b=_dbd: (setattr(a, 'pos', v), setattr(b, 'pos', v)),
            size=lambda _, v, a=_dbg, b=_dbd: (setattr(a, 'size', v), setattr(b, 'size', v)),
        )
        ti_dest = TextInput(
            text=dest_txt, multiline=True,
            background_normal='', background_active='', background_color=(0, 0, 0, 0),
            foreground_color=TINTA, cursor_color=VERMILLON,
            hint_text_color=MUTED, padding=[14, 10], font_size=12,
        )
        wrap_dest.add_widget(ti_dest)
        body.add_widget(wrap_dest)

        lbl_est = Label(text='', font_size=12, color=SUCCESS,
                        size_hint_y=None, height=22, halign='left', valign='middle')
        lbl_est.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_est)
        body.add_widget(Widget())
        content.add_widget(body)

        # Footer
        footer = BoxLayout(size_hint_y=None, height=58, spacing=10, padding=[18, 10])
        _mk_bg(footer, STAGE)
        btn_can = PillButton(text='Cerrar', bg_color=LINE, fg_color=TINTA,
                             pressed_color=STAGE, font_size=13, pill_radius=20,
                             size_hint_x=None, width=100)
        btn_env = PillButton(text='✉  Enviar', bg_color=VERMILLON, pressed_color=LADRILLO,
                             font_size=13, pill_radius=20,
                             size_hint_x=None, width=130)
        footer.add_widget(Widget())
        footer.add_widget(btn_can)
        footer.add_widget(btn_env)
        content.add_widget(footer)

        popup = Popup(title='', content=content,
                      size_hint=(0.50, 0.68), background_color=CARD, separator_height=0)

        def enviar(_):
            dest_lines = [d.strip() for d in ti_dest.text.splitlines() if d.strip()]
            if not dest_lines:
                lbl_est.text  = '⚠  Agrega al menos un destinatario'
                lbl_est.color = DANGER
                return
            btn_env.disabled = True
            lbl_est.color = MUTED
            lbl_est.text  = 'Enviando…'
            smtp_cfg = {
                'user':     self._config.get('smtp_user', ''),
                'password': self._config.get('smtp_password', ''),
            }
            threading.Thread(
                target=lambda: self._tarea_enviar(
                    dest_lines, periodo_txt, archivos, lbl_est, btn_env, smtp_cfg),
                daemon=True,
            ).start()

        btn_can.bind(on_press=popup.dismiss)
        btn_env.bind(on_press=enviar)
        popup.open()

    def _tarea_enviar(self, dest_lines, periodo, archivos, lbl, btn, smtp_cfg):
        ok, msg = enviar_volcado(dest_lines, periodo, archivos, smtp_cfg=smtp_cfg)
        def act(*_):
            btn.disabled = False
            lbl.color = SUCCESS if ok else DANGER
            lbl.text  = (f'Enviado a {len(dest_lines)} destinatario(s) ✓' if ok else msg)
        Clock.schedule_once(act, 0)
