from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
import threading
import utils.overlay as overlay

_NINGUNA = '(Ninguna)'

_FAC_FIELDS = [
    ('NUMERO_FACTURA',    'N° Factura *',         True),
    ('CUENTA_CONTRATO',   'NIC / Suscriptor *',   True),
    ('VALOR_RECIBO',      'Valor facturado *',    True),
    ('FECHA_FACTURACION', 'Fecha facturación',    False),
    ('AÑO',               'Año',                  False),
    ('MES',               'Mes',                  False),
    ('PERIODO',           'Período YYYYMM',       False),
]

_REC_FIELDS = [
    ('CUENTA_CONTRATO',   'NIC / Suscriptor *',   True),
    ('FECHA_RECAUDO',     'Fecha de pago *',      True),
    ('VALOR_RECIBO',      'Valor pagado *',       True),
    ('NUMERO_FACTURA',    'N° Factura',           False),
    ('FECHA_FACTURACION', 'Fecha facturación',    False),
    ('AÑO',               'Año',                  False),
    ('MES',               'Mes',                  False),
]

_ALIASES = {
    'NUMERO_FACTURA':    ['NUMERO_FACTURA', 'FACTURA', 'CODIGO_FACTURA', 'NRO_FACTURA'],
    'CUENTA_CONTRATO':   ['CUENTA_CONTRATO', 'CUENTA'],
    'VALOR_RECIBO':      ['VALOR_RECIBO', 'VALOR_FACTURADO_TERCEROS', 'RECAUDO_VALOR', 'RECAUDO_TERCEROS'],
    'FECHA_FACTURACION': ['FECHA_FACTURACION', 'FECHA_FACT', 'FECHA'],
    'FECHA_RECAUDO':     ['FECHA_RECAUDO', 'F_PAGO', 'FECHA_PAGO'],
    'AÑO':               ['AÑO', 'ANO'],
    'MES':               ['MES'],
    'PERIODO':           ['PERIODO'],
}


class ImportarScreen(Screen):
    mensaje   = StringProperty('')
    color_msg = ListProperty([0.2, 0.9, 0.4, 1])

    def seleccionar_archivo(self, tipo):
        def _abrir():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', True)
                archivo = filedialog.askopenfilename(
                    title=f'Seleccionar archivo — {tipo}',
                    filetypes=[('Excel / CSV', '*.xlsx *.xls *.csv'), ('Todos', '*.*')]
                )
                root.destroy()
            except Exception as e:
                msg = f'Error al abrir selector: {e}'
                Clock.schedule_once(
                    lambda _, m=msg: setattr(self, 'mensaje', m), 0)
                return
            if archivo:
                if tipo == 'catastro':
                    Clock.schedule_once(
                        lambda _: self._iniciar_previsualizacion(archivo, tipo), 0)
                else:
                    Clock.schedule_once(
                        lambda _: self._iniciar_mapeo(archivo, tipo), 0)

        threading.Thread(target=_abrir, daemon=True).start()

    # ------------------------------------------------------------------
    # Mapeo de columnas
    # ------------------------------------------------------------------
    def _iniciar_mapeo(self, filepath, tipo):
        self.mensaje = ''
        overlay.show('Leyendo columnas…')

        def tarea():
            from utils.importar import get_file_columns
            ok, resultado = get_file_columns(filepath)
            Clock.schedule_once(
                lambda _: self._on_columnas(ok, resultado, filepath, tipo), 0
            )
        threading.Thread(target=tarea, daemon=True).start()

    def _on_columnas(self, ok, resultado, filepath, tipo):
        overlay.hide()
        if not ok:
            self._mostrar_popup_error(resultado)
            return
        self._mostrar_popup_mapeo(filepath, tipo, resultado)

    def _mostrar_popup_mapeo(self, filepath, tipo, columnas_archivo):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.spinner import Spinner
        from kivy.uix.scrollview import ScrollView
        from kivy.graphics import Color, Rectangle
        from theme import TINTA, STAGE, CARD, LINE, MUTED, SUCCESS, VERMILLON

        fields   = _FAC_FIELDS if tipo == 'facturacion' else _REC_FIELDS
        tipo_str = 'Facturación' if tipo == 'facturacion' else 'Recaudo'
        valores_sp = [_NINGUNA] + columnas_archivo

        def auto_detect(target):
            for alias in _ALIASES.get(target, [target]):
                if alias in columnas_archivo:
                    return alias
            return _NINGUNA

        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            rc = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(rc, 'pos', v),
                     size=lambda _, v: setattr(rc, 'size', v))

        header = BoxLayout(size_hint_y=None, height=52, padding=[16, 0])
        with header.canvas.before:
            Color(*TINTA)
            rh = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda _, v: setattr(rh, 'pos', v),
                    size=lambda _, v: setattr(rh, 'size', v))
        header.add_widget(Label(
            text=f'Mapeo de columnas — {tipo_str}',
            bold=True, font_size=15, color=(1, 1, 1, 1),
            halign='left', valign='middle', text_size=(500, 52)
        ))
        content.add_widget(header)

        body = BoxLayout(orientation='vertical', padding=[16, 10], spacing=8)
        content.add_widget(body)

        body.add_widget(Label(
            text=f'{len(columnas_archivo)} columnas detectadas en el archivo  ·  * campo obligatorio',
            font_size=11, color=MUTED,
            size_hint_y=None, height=20,
            halign='left', text_size=(600, 20)
        ))

        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=2, size_hint_y=None, spacing=[8, 4],
            row_default_height=40, row_force_default=True,
            padding=[0, 4]
        )
        grid.bind(minimum_height=grid.setter('height'))

        spinners = {}
        for target, label_txt, required in fields:
            lbl = Label(
                text=label_txt,
                font_size=12,
                color=TINTA if required else MUTED,
                halign='left', valign='middle',
                size_hint_x=0.42,
            )
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            grid.add_widget(lbl)

            sp = Spinner(
                text=auto_detect(target),
                values=valores_sp,
                size_hint_x=0.58,
                size_hint_y=None, height=36,
                background_normal='',
                background_color=STAGE,
                color=TINTA,
                font_size=12,
            )
            spinners[target] = sp
            grid.add_widget(sp)

        scroll.add_widget(grid)
        body.add_widget(scroll)

        footer = BoxLayout(size_hint_y=None, height=56, spacing=8, padding=[16, 10])
        with footer.canvas.before:
            Color(*STAGE)
            rf = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(rf, 'pos', v),
                    size=lambda _, v: setattr(rf, 'size', v))

        popup = Popup(title='', content=content, size_hint=(0.65, 0.82),
                      background_color=CARD, separator_height=0)

        btn_cancelar = Button(
            text='Cancelar',
            background_normal='', background_color=LINE,
            color=TINTA, font_size=12,
            size_hint=(None, None), size=(110, 36),
        )
        btn_cancelar.bind(on_press=popup.dismiss)
        footer.add_widget(btn_cancelar)

        lbl_err = Label(text='', color=VERMILLON, font_size=11, size_hint_x=1)
        footer.add_widget(lbl_err)

        def on_continuar(_):
            col_map = {}
            faltantes = []
            for target, label_txt, required in fields:
                val = spinners[target].text
                if val == _NINGUNA:
                    if required:
                        faltantes.append(label_txt.replace(' *', ''))
                else:
                    col_map[target] = val
            if faltantes:
                lbl_err.text = f'Sin asignar: {", ".join(faltantes)}'
                return
            popup.dismiss()
            self._iniciar_previsualizacion(filepath, tipo, col_map)

        btn_continuar = Button(
            text='Continuar →',
            background_normal='', background_color=SUCCESS,
            color=(1, 1, 1, 1), font_size=12,
            size_hint=(None, None), size=(130, 36),
        )
        btn_continuar.bind(on_press=on_continuar)
        footer.add_widget(btn_continuar)

        content.add_widget(footer)
        popup.open()

    # ------------------------------------------------------------------
    # Previsualización (dry-run sin escribir en la base de datos)
    # ------------------------------------------------------------------
    def _iniciar_previsualizacion(self, filepath, tipo, col_map=None):
        self.mensaje = ''
        overlay.show('Analizando archivo…')

        def tarea():
            try:
                from utils.importar import (previsualizar_catastro,
                                            previsualizar_facturacion,
                                            previsualizar_recaudo)
                if tipo == 'catastro':
                    ok, datos = previsualizar_catastro(filepath)
                elif tipo == 'facturacion':
                    ok, datos = previsualizar_facturacion(filepath, col_map=col_map)
                else:
                    ok, datos = previsualizar_recaudo(filepath, col_map=col_map)
            except Exception as e:
                ok, datos = False, f'Error inesperado: {e}'
            Clock.schedule_once(
                lambda _: self._mostrar_popup_preview(ok, datos, filepath, tipo, col_map), 0
            )

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_popup_preview(self, ok, datos, filepath, tipo, col_map=None):
        overlay.hide()
        if not ok:
            self._mostrar_popup_error(str(datos))
            return

        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.graphics import Color, Rectangle, RoundedRectangle
        from theme import TINTA, STAGE, CARD, LINE, MUTED, SUCCESS, VERMILLON, WARNING

        d = datos

        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            r_root = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(r_root, 'pos', v))
        content.bind(size=lambda _, v: setattr(r_root, 'size', v))

        header = BoxLayout(size_hint_y=None, height=52, padding=[16, 0])
        with header.canvas.before:
            Color(*TINTA)
            r_h = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda _, v: setattr(r_h, 'pos', v))
        header.bind(size=lambda _, v: setattr(r_h, 'size', v))
        header.add_widget(Label(
            text=f"Vista previa — {d['tipo']}",
            bold=True, font_size=15, color=(1, 1, 1, 1),
            halign='left', valign='middle', text_size=(500, 52)
        ))
        content.add_widget(header)

        body = BoxLayout(orientation='vertical', padding=[16, 12], spacing=10)
        content.add_widget(body)

        es_catastro  = d['tipo'] == 'Catastro'
        actualizados = d.get('actualizados', 0)
        retirados    = d.get('retirados', 0)

        if es_catastro:
            tile_datos = [
                (f"{d['total']:,}",    'Filas en archivo',    TINTA),
                (f"{d['nuevas']:,}",   'Nuevos',              SUCCESS),
                (f"{actualizados:,}",  'Se actualizarán',     VERMILLON),
                (f"{retirados:,}",     'Se marcarán RETIRADO',
                 WARNING if retirados > 0 else MUTED),
            ]
        elif d['tipo'] == 'Recaudo':
            sin_fac = d.get('sin_factura', 0)
            tile_datos = [
                (f"{d['total']:,}",    'Filas en archivo',      TINTA),
                (f"{d['nuevas']:,}",   'Se insertarán',         SUCCESS),
                (f"{d['omitidas']:,}", 'Ya existen / vacías',   MUTED),
                (f"{sin_fac:,}",       'Sin factura en DB',
                 WARNING if sin_fac > 0 else MUTED),
            ]
        else:
            tile_datos = [
                (f"{d['total']:,}",    'Filas en archivo',    TINTA),
                (f"{d['nuevas']:,}",   'Se insertarán',       SUCCESS),
                (f"{d['omitidas']:,}", 'Ya existen / vacías', MUTED),
            ]

        tiles = BoxLayout(size_hint_y=None, height=74, spacing=8)
        for val, lbl_txt, col in tile_datos:
            tile = BoxLayout(orientation='vertical', padding=[12, 6])
            with tile.canvas.before:
                Color(*STAGE)
                rr = RoundedRectangle(pos=tile.pos, size=tile.size, radius=[8])
            tile.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v))
            tile.bind(size=lambda _, v, r=rr: setattr(r, 'size', v))
            tile.add_widget(Label(text=val, bold=True, font_size=20, color=col))
            tile.add_widget(Label(text=lbl_txt, font_size=10, color=MUTED))
            tiles.add_widget(tile)
        body.add_widget(tiles)

        if d['periodos']:
            periodos_txt = '  ·  '.join(d['periodos'][:10])
            body.add_widget(Label(
                text=f"Períodos detectados: {periodos_txt}",
                font_size=11, color=MUTED,
                size_hint_y=None, height=18,
                halign='left', text_size=(700, 18)
            ))

        hdr_row = BoxLayout(size_hint_y=None, height=26)
        with hdr_row.canvas.before:
            Color(*TINTA)
            r_hr = Rectangle(pos=hdr_row.pos, size=hdr_row.size)
        hdr_row.bind(pos=lambda _, v: setattr(r_hr, 'pos', v))
        hdr_row.bind(size=lambda _, v: setattr(r_hr, 'size', v))
        for c in d['columnas']:
            hdr_row.add_widget(Label(
                text=c, bold=True, font_size=10,
                color=LINE, halign='left', valign='middle', text_size=(200, 26)
            ))
        body.add_widget(hdr_row)

        n = len(d['muestra'])
        scroll = ScrollView(size_hint_y=None, height=min(n * 28 + 4, 210))
        grid = GridLayout(
            cols=len(d['columnas']), size_hint_y=None,
            row_default_height=28, row_force_default=True, spacing=1
        )
        grid.bind(minimum_height=grid.setter('height'))
        for i, fila in enumerate(d['muestra']):
            bg = CARD if i % 2 == 0 else STAGE
            for cell in fila:
                lbl = Label(text=str(cell), font_size=11, color=TINTA,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
                with lbl.canvas.before:
                    Color(*bg)
                    rr2 = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(pos=lambda _, v, r=rr2: setattr(r, 'pos', v))
                lbl.bind(size=lambda _, v, r=rr2: setattr(r, 'size', v))
                grid.add_widget(lbl)
        scroll.add_widget(grid)
        body.add_widget(scroll)

        if d['nuevas'] > n:
            body.add_widget(Label(
                text=f"… y {d['nuevas'] - n:,} registros nuevos más",
                font_size=10, color=MUTED,
                size_hint_y=None, height=16,
                halign='right', text_size=(700, 16)
            ))

        periodos_existentes = d.get('periodos_existentes', [])
        if periodos_existentes and not es_catastro:
            adv = BoxLayout(orientation='vertical', size_hint_y=None, height=58,
                            padding=[14, 6], spacing=2)
            with adv.canvas.before:
                Color(0.800, 0.500, 0.050, 0.15)
                adv_r = Rectangle(pos=adv.pos, size=adv.size)
            adv.bind(pos=lambda _, v: setattr(adv_r, 'pos', v),
                     size=lambda _, v: setattr(adv_r, 'size', v))
            periodos_txt = ', '.join(
                f"{p} ({c:,} reg.)" for p, c in periodos_existentes
            )
            adv.add_widget(Label(
                text=f'Advertencia — ya existen datos para: {periodos_txt}',
                font_size=11, bold=True, color=(0.6, 0.35, 0.0, 1),
                halign='left', text_size=(700, 20), size_hint_y=None, height=20,
            ))
            adv.add_widget(Label(
                text='Elige "Agregar nuevos" para ignorar duplicados  ·  '
                     '"Reemplazar" para borrar el período y recargar desde el archivo.',
                font_size=10, color=WARNING,
                halign='left', text_size=(700, 18), size_hint_y=None, height=18,
            ))
            body.add_widget(adv)

        footer = BoxLayout(size_hint_y=None, height=56, spacing=8, padding=[16, 10])
        with footer.canvas.before:
            Color(*STAGE)
            r_ft = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(r_ft, 'pos', v))
        footer.bind(size=lambda _, v: setattr(r_ft, 'size', v))

        popup = Popup(title='', content=content, size_hint=(0.60, 0.80),
                      background_color=CARD, separator_height=0)

        btn_cancelar = Button(
            text='Cancelar',
            background_normal='', background_color=LINE,
            color=TINTA, font_size=12,
            size_hint=(None, None), size=(110, 36),
        )
        btn_cancelar.bind(on_press=popup.dismiss)
        footer.add_widget(btn_cancelar)

        hay_cambios = d['nuevas'] > 0 or d.get('actualizados', 0) > 0 or retirados > 0

        if es_catastro:
            if hay_cambios:
                partes = []
                if d['nuevas']:    partes.append(f"{d['nuevas']:,} nuevos")
                if actualizados:   partes.append(f"{actualizados:,} actualizados")
                if retirados:      partes.append(f"{retirados:,} retirados")
                lbl_ok = 'Confirmar — ' + ', '.join(partes)
            else:
                lbl_ok = 'Sin cambios que aplicar'
            btn_ok = Button(
                text=lbl_ok,
                background_normal='', background_color=SUCCESS,
                color=(1, 1, 1, 1), font_size=12,
                size_hint=(1, None), height=36,
                disabled=(not hay_cambios),
            )
            btn_ok.bind(on_press=lambda _: (popup.dismiss(), self.procesar(filepath, tipo)))
            footer.add_widget(btn_ok)

        elif periodos_existentes:
            btn_agregar = Button(
                text=f'Agregar nuevos ({d["nuevas"]:,})',
                background_normal='', background_color=SUCCESS,
                color=(1, 1, 1, 1), font_size=11,
                size_hint=(1, None), height=36,
                disabled=(d['nuevas'] == 0),
            )
            btn_reemplazar = Button(
                text='Reemplazar período',
                background_normal='', background_color=VERMILLON,
                color=(1, 1, 1, 1), font_size=11,
                size_hint=(1, None), height=36,
            )
            btn_agregar.bind(on_press=lambda _: (
                popup.dismiss(), self.procesar(filepath, tipo, 'nuevo', col_map)))
            btn_reemplazar.bind(on_press=lambda _: (
                popup.dismiss(), self.procesar(filepath, tipo, 'reemplazar', col_map)))
            footer.add_widget(btn_agregar)
            footer.add_widget(btn_reemplazar)

        else:
            lbl_ok = (f"Confirmar — insertar {d['nuevas']:,} registros"
                      if d['nuevas'] > 0 else 'Nada nuevo que insertar')
            btn_ok = Button(
                text=lbl_ok,
                background_normal='', background_color=SUCCESS,
                color=(1, 1, 1, 1), font_size=12,
                size_hint=(1, None), height=36,
                disabled=(not hay_cambios),
            )
            btn_ok.bind(on_press=lambda _: (
                popup.dismiss(), self.procesar(filepath, tipo, 'nuevo', col_map)))
            footer.add_widget(btn_ok)

        content.add_widget(footer)
        popup.open()

    def _mostrar_popup_error(self, mensaje):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.graphics import Color, Rectangle
        from theme import TINTA, CARD, STAGE, VERMILLON, MUTED

        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            r = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(r, 'pos', v))
        content.bind(size=lambda _, v: setattr(r, 'size', v))

        header = BoxLayout(size_hint_y=None, height=52, padding=[16, 0])
        with header.canvas.before:
            Color(*VERMILLON)
            rh = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda _, v: setattr(rh, 'pos', v))
        header.bind(size=lambda _, v: setattr(rh, 'size', v))
        header.add_widget(Label(
            text='Archivo incompatible',
            bold=True, font_size=15, color=(1, 1, 1, 1),
            halign='left', valign='middle', text_size=(460, 52)
        ))
        content.add_widget(header)

        body = BoxLayout(orientation='vertical', padding=[20, 16], spacing=12)
        content.add_widget(body)

        n_saltos = mensaje.count('\n')
        body.add_widget(Label(
            text=mensaje,
            font_size=13, color=TINTA,
            halign='left', valign='top',
            text_size=(460, None),
            size_hint_y=None,
            height=max(60, n_saltos * 22 + 60)
        ))
        body.add_widget(Label(
            text='Verifica que el archivo sea correcto y no le falten columnas.',
            font_size=11, color=MUTED,
            halign='left', valign='top',
            text_size=(460, None),
            size_hint_y=None, height=30
        ))

        footer = BoxLayout(size_hint_y=None, height=56, padding=[16, 10])
        with footer.canvas.before:
            Color(*STAGE)
            rf = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(rf, 'pos', v))
        footer.bind(size=lambda _, v: setattr(rf, 'size', v))

        popup = Popup(title='', content=content,
                      size_hint=(0.50, None),
                      height=230 + n_saltos * 22,
                      background_color=CARD, separator_height=0)

        btn = Button(
            text='Entendido',
            background_normal='', background_color=TINTA,
            color=(1, 1, 1, 1), font_size=13,
            size_hint=(1, None), height=36
        )
        btn.bind(on_press=popup.dismiss)
        footer.add_widget(btn)
        content.add_widget(footer)
        popup.open()

    # ------------------------------------------------------------------
    # Importación real (siempre en thread)
    # ------------------------------------------------------------------
    def procesar(self, filepath, tipo, modo='nuevo', col_map=None):
        self.mensaje = ''
        overlay.show('Importando…')

        def tarea():
            try:
                from utils.catastro import importar_catastro as _importar_catastro
                from utils.importar import importar_facturacion, importar_recaudo
                if tipo == 'catastro':
                    res = _importar_catastro(filepath)
                    if res.get('error'):
                        ok, msg = False, res['error']
                    else:
                        sc = res['sin_clasificar']
                        ret = res['retirados']
                        partes = [
                            f"Catastro importado: {res['nuevos']} nuevos, "
                            f"{res['actualizados']} actualizados, "
                            f"{len(ret)} retirados, {res['omitidos']} omitidos"
                        ]
                        if sc:
                            partes.append(f"Sin clasificar ({len(sc)}): "
                                          f"{', '.join(str(x) for x in sc[:5])}"
                                          f"{'…' if len(sc) > 5 else ''}")
                        ok, msg = True, '\n'.join(partes)
                elif tipo == 'facturacion':
                    ok, msg = importar_facturacion(filepath, modo, col_map=col_map)
                elif tipo == 'recaudo':
                    ok, msg = importar_recaudo(filepath, modo, col_map=col_map)
                else:
                    ok, msg = False, 'Tipo desconocido'
            except Exception as e:
                ok, msg = False, f'Error inesperado: {e}'
            Clock.schedule_once(lambda _: self._actualizar_ui(ok, msg), 0)

        threading.Thread(target=tarea, daemon=True).start()

    def _actualizar_ui(self, ok, msg):
        overlay.hide()
        if not ok:
            self._mostrar_popup_error(msg)
        else:
            self.mensaje = msg
            self.color_msg = [0.2, 0.9, 0.4, 1]
