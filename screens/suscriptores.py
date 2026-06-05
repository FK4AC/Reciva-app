import os

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from db.connection import get_connection
from utils.estado_cuenta import generar_estado_cuenta
from theme import (TINTA, BG, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, TEXT_SEC, SUCCESS, WARNING, DANGER, SIDEBAR_BTN)

MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}


class SuscriptoresScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self.ids.lista_suscriptores.clear_widgets()
        self.mensaje = 'Usa el buscador o presiona "Mostrar todos"'

    def buscar(self, texto):
        self._cargar_lista(texto.strip())

    def mostrar_todos(self):
        self._cargar_lista('')

    def _cargar_lista(self, filtro=''):
        lista = self.ids.lista_suscriptores
        lista.clear_widgets()
        self.mensaje = 'Cargando...'

        conn = get_connection()
        if not conn:
            self.mensaje = 'Error de conexión a la base de datos'
            return

        cursor = conn.cursor()
        try:
            if filtro:
                like = f'%{filtro}%'
                cursor.execute("""
                    SELECT cuenta, nombre, barrio, estrato, estado_suministro
                    FROM suscriptores
                    WHERE nombre LIKE %s OR CAST(cuenta AS CHAR) LIKE %s
                    ORDER BY nombre
                    LIMIT 300
                """, (like, like))
            else:
                cursor.execute("""
                    SELECT cuenta, nombre, barrio, estrato, estado_suministro
                    FROM suscriptores
                    ORDER BY nombre
                    LIMIT 300
                """)

            rows = cursor.fetchall()
            total = len(rows)
            self.mensaje = f'{total} suscriptores encontrados' + (' (máx. 300)' if total == 300 else '')

            for i, (cuenta, nombre, barrio, estrato, estado) in enumerate(rows):
                lista.add_widget(self._fila(cuenta, nombre, barrio, estrato, estado, i))

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    def _fila(self, cuenta, nombre, barrio, estrato, estado, idx=0):
        fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=2)
        bg = CARD if idx % 2 == 0 else STAGE

        with fila.canvas.before:
            Color(*bg)
            rect = Rectangle(pos=fila.pos, size=fila.size)

        fila.bind(pos=lambda _, v, r=rect: setattr(r, 'pos', v))
        fila.bind(size=lambda _, v, r=rect: setattr(r, 'size', v))

        datos = [
            (str(cuenta),           0.18),
            ((nombre or '')[:35],   0.36),
            ((barrio or '-')[:20],  0.18),
            (str(estrato or '-'),   0.09),
            (str(estado or '-'),    0.12),
        ]
        for texto, sx in datos:
            lbl = Label(text=texto, size_hint_x=sx, font_size=13,
                        color=TINTA, halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
            fila.add_widget(lbl)

        btn = Button(text='Ver', size_hint_x=0.07, font_size=12,
                     background_normal='', background_color=VERMILLON, color=(1,1,1,1))
        btn.bind(on_press=lambda x, c=cuenta: self._ver_detalle(c))
        fila.add_widget(btn)

        return fila

    def _ver_detalle(self, cuenta):
        conn = get_connection()
        if not conn:
            return

        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT cuenta, nombre, direccion, barrio, estrato,
                       estado_suministro, municipio, susccodi
                FROM suscriptores WHERE cuenta = %s LIMIT 1
            """, (cuenta,))
            info = cursor.fetchone()

            cursor.execute("""
                SELECT año, mes, SUM(valor_recibo)
                FROM facturas WHERE cuenta_contrato = %s
                GROUP BY año, mes ORDER BY año, mes
            """, (cuenta,))
            facturas = {(int(r[0]), int(r[1])): float(r[2]) for r in cursor.fetchall()}

            cursor.execute("""
                SELECT año, mes, SUM(valor_recibo)
                FROM recaudos WHERE cuenta_contrato = %s
                GROUP BY año, mes ORDER BY año, mes
            """, (cuenta,))
            recaudos = {(int(r[0]), int(r[1])): float(r[2]) for r in cursor.fetchall()}

            cursor.execute("""
                SELECT id, tipo, asunto, estado, fecha_creacion
                FROM pqr WHERE cuenta_contrato = %s
                ORDER BY fecha_creacion DESC
            """, (cuenta,))
            pqr_list = cursor.fetchall()

        except Exception as e:
            self.mensaje = f'Error al cargar detalle: {e}'
            return
        finally:
            cursor.close()
            conn.close()

        self._popup_detalle(info, facturas, recaudos, pqr_list)

    def _popup_detalle(self, info, facturas, recaudos, pqr_list):
        if not info:
            return

        cuenta, nombre, direccion, barrio, estrato, estado_sum, municipio, susccodi = info

        total_facturado = sum(facturas.values())
        total_pagado    = sum(recaudos.values())
        deuda_total     = max(0, total_facturado - total_pagado)

        meses_sin_pagar = [
            (a, m) for (a, m), v in sorted(facturas.items())
            if recaudos.get((a, m), 0) < v * 0.95
        ]
        consecutivos = 0
        for (a, m), v in sorted(facturas.items(), reverse=True):
            if recaudos.get((a, m), 0) < v * 0.95:
                consecutivos += 1
            else:
                break

        n_sin = len(meses_sin_pagar)
        if n_sin == 0:
            color_estado = SUCCESS
            texto_estado = 'Al día'
        elif n_sin <= 2:
            color_estado = WARNING
            texto_estado = f'{n_sin} mes{"" if n_sin == 1 else "es"} sin pagar'
        else:
            color_estado = DANGER
            texto_estado = f'{n_sin} meses sin pagar'

        # ── Root ──
        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            _bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(_bg, 'pos', v),
                     size=lambda _, v: setattr(_bg, 'size', v))

        # ── Franja superior TINTA ──
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=80,
                        padding=[18, 8])
        with top.canvas.before:
            Color(*TINTA)
            _top = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=lambda _, v: setattr(_top, 'pos', v),
                 size=lambda _, v: setattr(_top, 'size', v))

        name_row = BoxLayout(size_hint_y=None, height=36)
        name_row.add_widget(Label(
            text=nombre or '—', bold=True, font_size=17,
            color=(1, 1, 1, 1), halign='left', valign='middle', size_hint_x=0.62,
        ))
        chip_wrap = BoxLayout(size_hint_x=0.38, padding=[10, 4, 0, 4])
        chip = BoxLayout()
        with chip.canvas.before:
            Color(*color_estado)
            _chip = RoundedRectangle(pos=chip.pos, size=chip.size, radius=[13])
        chip.bind(pos=lambda _, v, r=_chip: setattr(r, 'pos', v),
                  size=lambda _, v, r=_chip: setattr(r, 'size', v))
        chip.add_widget(Label(text=texto_estado, color=(1, 1, 1, 1), bold=True, font_size=11))
        chip_wrap.add_widget(chip)
        name_row.add_widget(chip_wrap)
        top.add_widget(name_row)

        meta_parts = [f'#{cuenta}', barrio or '—',
                      f'Estrato {estrato or "—"}', estado_sum or '—']
        top.add_widget(Label(
            text='  ·  '.join(meta_parts), font_size=11,
            color=LINE, halign='left', valign='middle',
            size_hint_y=None, height=26,
        ))
        content.add_widget(top)

        # ── 3 fichas financieras ──
        fichas = BoxLayout(size_hint_y=None, height=68, spacing=1)
        for lbl_t, val_t, col in [
            ('Total Facturado', f'${total_facturado:,.0f}', TEXT_SEC),
            ('Total Pagado',    f'${total_pagado:,.0f}',    SUCCESS),
            ('Deuda Total',     f'${deuda_total:,.0f}',     DANGER if deuda_total > 0 else MUTED),
        ]:
            f = BoxLayout(orientation='vertical', padding=[0, 10])
            with f.canvas.before:
                Color(*STAGE)
                _fr = Rectangle(pos=f.pos, size=f.size)
            f.bind(pos=lambda _, v, r=_fr: setattr(r, 'pos', v),
                   size=lambda _, v, r=_fr: setattr(r, 'size', v))
            f.add_widget(Label(text=val_t, font_size=17, bold=True, color=col))
            f.add_widget(Label(text=lbl_t, font_size=10, color=MUTED))
            fichas.add_widget(f)
        content.add_widget(fichas)

        # ── Encabezado tabla ──
        hdr = BoxLayout(size_hint_y=None, height=30, spacing=2)
        with hdr.canvas.before:
            Color(*TINTA)
            _hdr = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda _, v: setattr(_hdr, 'pos', v),
                 size=lambda _, v: setattr(_hdr, 'size', v))
        for txt, sx in [('Año', 0.12), ('Mes', 0.18), ('Facturado', 0.23),
                         ('Pagado', 0.23), ('Estado', 0.24)]:
            hdr.add_widget(Label(text=txt, bold=True, size_hint_x=sx,
                                 font_size=11, color=LINE))
        content.add_widget(hdr)

        # ── Tabla scrollable ──
        scroll = ScrollView()
        tabla = GridLayout(cols=5, size_hint_y=None,
                           row_default_height=30, row_force_default=True, spacing=1)
        tabla.bind(minimum_height=tabla.setter('height'))

        all_months = sorted(set(list(facturas.keys()) + list(recaudos.keys())))
        for i, (a, m) in enumerate(all_months):
            fac_val = facturas.get((a, m), 0)
            rec_val = recaudos.get((a, m), 0)
            row_bg  = CARD if i % 2 == 0 else STAGE

            if fac_val > 0 and rec_val >= fac_val * 0.95:
                est_txt, est_col = 'Pagado', SUCCESS
            elif fac_val > 0:
                est_txt, est_col = 'Pendiente', DANGER
            else:
                est_txt, est_col = 'Sin factura', MUTED

            for val, col in [
                (str(a),                   TINTA),
                (MESES.get(m, str(m))[:5], TINTA),
                (f'${fac_val:,.0f}',       TEXT_SEC),
                (f'${rec_val:,.0f}',       SUCCESS if rec_val > 0 else MUTED),
                (est_txt,                  est_col),
            ]:
                lbl = Label(text=val, color=col, font_size=12)
                with lbl.canvas.before:
                    Color(*row_bg)
                    _r = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(pos=lambda inst, v, r=_r: setattr(r, 'pos', v),
                         size=lambda inst, v, r=_r: setattr(r, 'size', v))
                tabla.add_widget(lbl)

        scroll.add_widget(tabla)
        content.add_widget(scroll)

        # ── Pie ──
        pie = BoxLayout(size_hint_y=None, height=52, spacing=10, padding=[14, 8])
        with pie.canvas.before:
            Color(*STAGE)
            _pie = Rectangle(pos=pie.pos, size=pie.size)
        pie.bind(pos=lambda _, v: setattr(_pie, 'pos', v),
                 size=lambda _, v: setattr(_pie, 'size', v))

        pie.add_widget(Label(
            text=f'{consecutivos} mes(es) consecutivo(s) sin pagar',
            font_size=11, color=MUTED, halign='left',
        ))
        lbl_pdf = Label(text='', font_size=11, color=SUCCESS,
                        size_hint_x=None, width=180)
        pie.add_widget(lbl_pdf)

        def _pill(text, bg, fg=(1, 1, 1, 1), w=115):
            b = Button(
                text=text, size_hint_x=None, width=w, font_size=12,
                color=fg, background_color=(0, 0, 0, 0),
                background_normal='', background_down='',
            )
            with b.canvas.before:
                Color(*bg)
                rr = RoundedRectangle(pos=b.pos, size=b.size, radius=[20])
            b.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v),
                   size=lambda _, v, r=rr: setattr(r, 'size', v))
            return b

        btn_editar = _pill('Editar',      WARNING)
        btn_pdf    = _pill('Generar PDF', TINTA, w=130)
        btn_cerrar = _pill('Cerrar',      LINE,  fg=TINTA)

        pie.add_widget(btn_editar)
        pie.add_widget(btn_pdf)
        pie.add_widget(btn_cerrar)
        content.add_widget(pie)

        popup = Popup(
            title=f'Suscriptor — {nombre}',
            content=content,
            size_hint=(0.82, 0.88),
            background_color=VERMILLON,
            title_color=(1, 1, 1, 1),
            separator_color=LINE,
        )

        def generar_pdf(_):
            try:
                ruta = generar_estado_cuenta(info, facturas, recaudos, pqr_list)
                lbl_pdf.text = 'PDF guardado'
                os.startfile(ruta)
            except Exception as e:
                lbl_pdf.text = f'Error: {e}'
                lbl_pdf.color = DANGER

        def abrir_editor(_):
            popup.dismiss()
            self._popup_formulario(cuenta_editar=cuenta)

        btn_editar.bind(on_press=abrir_editor)
        btn_pdf.bind(on_press=generar_pdf)
        btn_cerrar.bind(on_press=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------------
    #  Popup compartido: Nuevo / Editar suscriptor
    # ------------------------------------------------------------------
    def nuevo_suscriptor(self):
        self._popup_formulario(cuenta_editar=None)

    def _popup_formulario(self, cuenta_editar=None):
        es_edicion = cuenta_editar is not None
        datos_actuales = {}

        if es_edicion:
            conn = get_connection()
            if not conn:
                return
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT cuenta, susccodi, nombre, direccion, municipio,
                           barrio, subcategoria, estrato, estado_suministro
                    FROM suscriptores WHERE cuenta = %s LIMIT 1
                """, (cuenta_editar,))
                row = cur.fetchone()
                if row:
                    keys = ['cuenta', 'susccodi', 'nombre', 'direccion',
                            'municipio', 'barrio', 'subcategoria',
                            'estrato', 'estado_suministro']
                    datos_actuales = {k: (str(v) if v is not None else '')
                                      for k, v in zip(keys, row)}
            finally:
                cur.close()
                conn.close()

        content = BoxLayout(orientation='vertical', spacing=10, padding=15)
        with content.canvas.before:
            Color(*CARD)
            _cbg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(_cbg, 'pos', v),
                     size=lambda _, v: setattr(_cbg, 'size', v))

        form = GridLayout(cols=2, size_hint_y=None, spacing=8, padding=[0, 4])
        form.bind(minimum_height=form.setter('height'))

        campos = [
            ('Cuenta *',          'cuenta',           not es_edicion),
            ('SUSCCODI',          'susccodi',          not es_edicion),
            ('Nombre *',          'nombre',            True),
            ('Dirección',         'direccion',         True),
            ('Municipio',         'municipio',         True),
            ('Barrio',            'barrio',            True),
            ('Subcategoría',      'subcategoria',      True),
            ('Estrato',           'estrato',           True),
            ('Estado suministro', 'estado_suministro', True),
        ]

        inputs = {}
        for label_txt, key, editable in campos:
            lbl = Label(
                text=label_txt, color=VERMILLON,
                bold=True, halign='right', size_hint_y=None, height=38,
            )
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0], v[1])))
            form.add_widget(lbl)

            inp = TextInput(
                text=datos_actuales.get(key, ''),
                multiline=False,
                size_hint_y=None, height=38,
                readonly=not editable,
                background_color=STAGE if not editable else CARD,
                foreground_color=MUTED  if not editable else TINTA,
                cursor_color=VERMILLON,
                padding=[8, 10],
            )
            form.add_widget(inp)
            inputs[key] = inp

        scroll = ScrollView(size_hint_y=1)
        scroll.add_widget(form)
        content.add_widget(scroll)

        lbl_err = Label(text='', color=DANGER, size_hint_y=None, height=26)
        content.add_widget(lbl_err)

        btns = BoxLayout(size_hint_y=None, height=44, spacing=12)
        lbl_ok = Label(text='', color=SUCCESS, font_size=12)

        def _pill_f(text, bg, fg=(1, 1, 1, 1)):
            b = Button(
                text=text, font_size=12, color=fg,
                background_color=(0, 0, 0, 0),
                background_normal='', background_down='',
            )
            with b.canvas.before:
                Color(*bg)
                rr = RoundedRectangle(pos=b.pos, size=b.size, radius=[20])
            b.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v),
                   size=lambda _, v, r=rr: setattr(r, 'size', v))
            return b

        btn_guardar  = _pill_f('Guardar',  SUCCESS)
        btn_cancelar = _pill_f('Cancelar', LINE, fg=TINTA)

        btns.add_widget(lbl_ok)
        btns.add_widget(btn_guardar)
        btns.add_widget(btn_cancelar)
        content.add_widget(btns)

        titulo = f'Editar Suscriptor — {cuenta_editar}' if es_edicion else 'Nuevo Suscriptor'
        popup = Popup(
            title=titulo, content=content, size_hint=(0.55, 0.82),
            background_color=VERMILLON, title_color=(1, 1, 1, 1),
            separator_color=LINE,
        )

        def guardar(_):
            nombre_val = inputs['nombre'].text.strip()
            if not nombre_val:
                lbl_err.text = 'El nombre es obligatorio'
                return

            conn = get_connection()
            if not conn:
                lbl_err.text = 'Error de conexión'
                return
            cur = conn.cursor()
            try:
                if es_edicion:
                    cur.execute("""
                        UPDATE suscriptores
                        SET nombre=%s, direccion=%s, municipio=%s, barrio=%s,
                            subcategoria=%s, estrato=%s, estado_suministro=%s
                        WHERE cuenta=%s
                    """, (
                        nombre_val,
                        inputs['direccion'].text.strip() or None,
                        inputs['municipio'].text.strip() or None,
                        inputs['barrio'].text.strip() or None,
                        inputs['subcategoria'].text.strip() or None,
                        inputs['estrato'].text.strip() or None,
                        inputs['estado_suministro'].text.strip() or None,
                        cuenta_editar,
                    ))
                else:
                    cuenta_val = inputs['cuenta'].text.strip()
                    susccodi_val = inputs['susccodi'].text.strip()
                    if not cuenta_val:
                        lbl_err.text = 'El número de cuenta es obligatorio'
                        cur.close(); conn.close()
                        return
                    cur.execute("""
                        INSERT INTO suscriptores
                        (cuenta, susccodi, nombre, direccion, municipio,
                         barrio, subcategoria, estrato, estado_suministro)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        int(cuenta_val),
                        int(susccodi_val) if susccodi_val else None,
                        nombre_val,
                        inputs['direccion'].text.strip() or None,
                        inputs['municipio'].text.strip() or None,
                        inputs['barrio'].text.strip() or None,
                        inputs['subcategoria'].text.strip() or None,
                        inputs['estrato'].text.strip() or None,
                        inputs['estado_suministro'].text.strip() or None,
                    ))
                conn.commit()
                lbl_ok.text = 'Guardado correctamente'
                lbl_err.text = ''
                self._cargar_lista('')
            except Exception as e:
                conn.rollback()
                lbl_err.text = f'Error: {e}'
            finally:
                cur.close()
                conn.close()

        btn_guardar.bind(on_press=guardar)
        btn_cancelar.bind(on_press=popup.dismiss)
        popup.open()
