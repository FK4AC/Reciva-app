from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
import threading
import utils.overlay as overlay


class ImportarScreen(Screen):
    mensaje   = StringProperty('')
    color_msg = ListProperty([0.2, 0.9, 0.4, 1])

    def seleccionar_archivo(self, tipo):
        from plyer import filechooser
        try:
            archivos = filechooser.open_file(
                title=f'Seleccionar archivo {tipo}',
                filters=[('Excel / CSV', '*.xlsx', '*.xls', '*.csv')]
            )
            if archivos:
                self._iniciar_previsualizacion(archivos[0], tipo)
        except Exception as e:
            self.mensaje = f'Error al abrir selector: {e}'

    # ------------------------------------------------------------------
    # Previsualización (thread → popup en hilo principal)
    # ------------------------------------------------------------------
    def _iniciar_previsualizacion(self, filepath, tipo):
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
                    ok, datos = previsualizar_facturacion(filepath)
                else:
                    ok, datos = previsualizar_recaudo(filepath)
            except Exception as e:
                ok, datos = False, f'Error inesperado: {e}'
            Clock.schedule_once(
                lambda _: self._mostrar_popup_preview(ok, datos, filepath, tipo), 0
            )

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_popup_preview(self, ok, datos, filepath, tipo):
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

        # ── Root con fondo CARD ──────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            r_root = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(r_root, 'pos', v))
        content.bind(size=lambda _, v: setattr(r_root, 'size', v))

        # ── Franja TINTA ─────────────────────────────────────────
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

        # ── Cuerpo ────────────────────────────────────────────────
        body = BoxLayout(orientation='vertical', padding=[16, 12], spacing=10)
        content.add_widget(body)

        # Tiles: total / nuevas / actualizados o omitidas / retirados (solo catastro)
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

        # Períodos detectados
        if d['periodos']:
            periodos_txt = '  ·  '.join(d['periodos'][:10])
            body.add_widget(Label(
                text=f"Períodos detectados: {periodos_txt}",
                font_size=11, color=MUTED,
                size_hint_y=None, height=18,
                halign='left', text_size=(700, 18)
            ))

        # Encabezado mini tabla
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

        # Filas de muestra (hasta 8)
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

        # ── Footer ────────────────────────────────────────────────
        footer = BoxLayout(size_hint_y=None, height=56, spacing=10, padding=[16, 10])
        with footer.canvas.before:
            Color(*STAGE)
            r_ft = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(r_ft, 'pos', v))
        footer.bind(size=lambda _, v: setattr(r_ft, 'size', v))

        popup = Popup(title='', content=content, size_hint=(0.60, 0.76),
                      background_color=CARD, separator_height=0)

        def _confirmar(_):
            popup.dismiss()
            self.procesar(filepath, tipo)

        btn_cancelar = Button(
            text='Cancelar',
            background_normal='', background_color=LINE,
            color=TINTA, font_size=12,
            size_hint=(0.32, None), height=36
        )
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
        else:
            lbl_ok = (f"Confirmar — insertar {d['nuevas']:,} registros"
                      if d['nuevas'] > 0 else 'Nada nuevo que insertar')
        btn_confirmar = Button(
            text=lbl_ok,
            background_normal='', background_color=SUCCESS,
            color=(1, 1, 1, 1), font_size=12,
            size_hint=(0.68, None), height=36,
            disabled=(not hay_cambios)
        )
        btn_cancelar.bind(on_press=popup.dismiss)
        btn_confirmar.bind(on_press=_confirmar)

        footer.add_widget(btn_cancelar)
        footer.add_widget(btn_confirmar)
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

        # Cabecera roja
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

        # Cuerpo
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

        # Footer
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
    def procesar(self, filepath, tipo):
        self.mensaje = ''
        overlay.show('Importando…')

        def tarea():
            try:
                from utils.importar import importar_catastro, importar_facturacion, importar_recaudo
                if tipo == 'catastro':
                    ok, msg = importar_catastro(filepath)
                elif tipo == 'facturacion':
                    ok, msg = importar_facturacion(filepath)
                elif tipo == 'recaudo':
                    ok, msg = importar_recaudo(filepath)
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
