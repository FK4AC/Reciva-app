import os

import os

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty
from db.connection import get_connection
from utils.estado_cuenta import generar_estado_cuenta

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

            for cuenta, nombre, barrio, estrato, estado in rows:
                lista.add_widget(self._fila(cuenta, nombre, barrio, estrato, estado))

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    def _fila(self, cuenta, nombre, barrio, estrato, estado):
        fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=2)

        with fila.canvas.before:
            Color(0.11, 0.11, 0.20, 1)
            rect = Rectangle(pos=fila.pos, size=fila.size)

        fila.bind(pos=lambda inst, v, r=rect: setattr(r, 'pos', v))
        fila.bind(size=lambda inst, v, r=rect: setattr(r, 'size', v))

        datos = [
            (str(cuenta),           0.18),
            ((nombre or '')[:35],   0.36),
            ((barrio or '-')[:20],  0.18),
            (str(estrato or '-'),   0.09),
            (str(estado or '-'),    0.12),
        ]
        for texto, sx in datos:
            lbl = Label(text=texto, size_hint_x=sx, font_size=13,
                        color=(0.9, 0.9, 0.9, 1), halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
            fila.add_widget(lbl)

        btn = Button(text='Ver', size_hint_x=0.07, font_size=12,
                     background_color=(0.2, 0.6, 1, 1))
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

        # --- Cálculo de estado de pago ---
        total_facturado = sum(facturas.values())
        total_pagado = sum(recaudos.values())
        deuda_total = max(0, total_facturado - total_pagado)

        meses_sin_pagar = [(a, m, v) for (a, m), v in sorted(facturas.items())
                           if recaudos.get((a, m), 0) < v * 0.95]

        # Meses consecutivos sin pagar desde el más reciente
        consecutivos = 0
        for (a, m), v in sorted(facturas.items(), reverse=True):
            if recaudos.get((a, m), 0) < v * 0.95:
                consecutivos += 1
            else:
                break

        n_sin = len(meses_sin_pagar)
        if n_sin == 0:
            color_estado = (0.1, 0.85, 0.3, 1)
            texto_estado = 'AL DÍA'
        elif n_sin <= 2:
            color_estado = (0.95, 0.65, 0.1, 1)
            texto_estado = f'{n_sin} mes(es) sin pagar'
        else:
            color_estado = (0.95, 0.2, 0.2, 1)
            texto_estado = f'{n_sin} meses sin pagar'

        # --- Construcción del popup ---
        content = BoxLayout(orientation='vertical', spacing=8, padding=10)

        # Información del suscriptor
        info_grid = GridLayout(cols=4, size_hint_y=None, height=75, spacing=6)
        for lbl_txt, val_txt in [
            ('Cuenta:', str(cuenta)),
            ('SUSCCODI:', str(susccodi)),
            ('Nombre:', nombre or '-'),
            ('Municipio:', municipio or '-'),
            ('Dirección:', direccion or '-'),
            ('Barrio:', barrio or '-'),
            ('Estrato:', str(estrato or '-')),
            ('Estado sum.:', estado_sum or '-'),
        ]:
            info_grid.add_widget(Label(text=lbl_txt, bold=True, font_size=12,
                                       color=(0.5, 0.75, 1, 1), halign='right'))
            info_grid.add_widget(Label(text=val_txt, font_size=12,
                                       color=(1, 1, 1, 1), halign='left'))
        content.add_widget(info_grid)

        # Barra de estado de pago
        barra = BoxLayout(size_hint_y=None, height=52, spacing=12)
        barra.add_widget(Label(text=texto_estado, bold=True, font_size=17,
                                color=color_estado))
        barra.add_widget(Label(text=f'Consecutivos: {consecutivos} mes(es)',
                                font_size=13, color=(0.85, 0.85, 0.85, 1)))
        barra.add_widget(Label(text=f'Deuda: ${deuda_total:,.0f}',
                                bold=True, font_size=15, color=(1, 0.8, 0.2, 1)))
        content.add_widget(barra)

        # Encabezado de tabla
        header = BoxLayout(size_hint_y=None, height=28, spacing=2)
        for txt, sx in [('Año', 0.13), ('Mes', 0.18), ('Facturado', 0.23),
                         ('Pagado', 0.23), ('Estado', 0.23)]:
            header.add_widget(Label(text=txt, bold=True, size_hint_x=sx,
                                     font_size=12, color=(0.2, 0.6, 1, 1)))
        content.add_widget(header)

        # Tabla scrollable
        scroll = ScrollView()
        tabla = GridLayout(cols=5, size_hint_y=None,
                           row_default_height=28, row_force_default=True, spacing=2)
        tabla.bind(minimum_height=tabla.setter('height'))

        all_months = sorted(set(list(facturas.keys()) + list(recaudos.keys())))
        for (a, m) in all_months:
            fac_val = facturas.get((a, m), 0)
            rec_val = recaudos.get((a, m), 0)

            if fac_val > 0 and rec_val >= fac_val * 0.95:
                est_txt, est_color = 'Pagado', (0.1, 0.9, 0.3, 1)
            elif fac_val > 0:
                est_txt, est_color = 'Pendiente', (1, 0.3, 0.3, 1)
            else:
                est_txt, est_color = 'Sin factura', (0.7, 0.7, 0.7, 1)

            for val, color in [
                (str(a),                      (0.85, 0.85, 0.85, 1)),
                (MESES.get(m, str(m))[:5],    (0.85, 0.85, 0.85, 1)),
                (f'${fac_val:,.0f}',          (0.85, 0.85, 0.85, 1)),
                (f'${rec_val:,.0f}',          (0.2, 0.9, 0.5, 1) if rec_val > 0 else (0.6, 0.6, 0.6, 1)),
                (est_txt,                     est_color),
            ]:
                tabla.add_widget(Label(text=val, color=color, font_size=12))

        scroll.add_widget(tabla)
        content.add_widget(scroll)

        # Pie con totales y botones
        pie = BoxLayout(size_hint_y=None, height=42, spacing=10)
        pie.add_widget(Label(text=f'Facturado: ${total_facturado:,.0f}',
                              font_size=12, color=(0.8, 0.8, 0.8, 1)))
        pie.add_widget(Label(text=f'Pagado: ${total_pagado:,.0f}',
                              font_size=12, color=(0.2, 0.9, 0.4, 1)))

        lbl_pdf = Label(text='', font_size=11, color=(0.4, 0.9, 0.4, 1),
                        size_hint_x=None, width=220)
        pie.add_widget(lbl_pdf)

        btn_editar = Button(text='Editar', size_hint_x=None, width=100,
                            background_color=(0.7, 0.45, 0.05, 1))
        btn_pdf    = Button(text='Generar PDF', size_hint_x=None, width=130,
                            background_color=(0.1, 0.55, 0.9, 1))
        btn_cerrar = Button(text='Cerrar', size_hint_x=None, width=100,
                            background_color=(0.35, 0.35, 0.35, 1))
        pie.add_widget(btn_editar)
        pie.add_widget(btn_pdf)
        pie.add_widget(btn_cerrar)
        content.add_widget(pie)

        popup = Popup(title=f'Suscriptor — {nombre}',
                      content=content, size_hint=(0.82, 0.88))

        def generar_pdf(_):
            try:
                ruta = generar_estado_cuenta(info, facturas, recaudos, pqr_list)
                lbl_pdf.text = 'PDF guardado'
                os.startfile(ruta)
            except Exception as e:
                lbl_pdf.text = f'Error: {e}'
                lbl_pdf.color = (1, 0.3, 0.3, 1)

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

        form = GridLayout(cols=2, size_hint_y=None, spacing=8, padding=[0, 4])
        form.bind(minimum_height=form.setter('height'))

        campos = [
            ('Cuenta *',         'cuenta',          not es_edicion),
            ('SUSCCODI',         'susccodi',         not es_edicion),
            ('Nombre *',         'nombre',           True),
            ('Dirección',        'direccion',        True),
            ('Municipio',        'municipio',        True),
            ('Barrio',           'barrio',           True),
            ('Subcategoría',     'subcategoria',     True),
            ('Estrato',          'estrato',          True),
            ('Estado suministro','estado_suministro',True),
        ]

        inputs = {}
        for label_txt, key, editable in campos:
            lbl = Label(text=label_txt, color=(0.5, 0.75, 1, 1),
                        bold=True, halign='right', size_hint_y=None, height=38)
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0], v[1])))
            form.add_widget(lbl)

            inp = TextInput(
                text=datos_actuales.get(key, ''),
                multiline=False,
                size_hint_y=None, height=38,
                readonly=not editable,
                foreground_color=(0.5, 0.5, 0.5, 1) if not editable else (1, 1, 1, 1),
                background_color=(0.15, 0.15, 0.2, 1) if not editable else (0.12, 0.12, 0.22, 1),
            )
            form.add_widget(inp)
            inputs[key] = inp

        scroll = ScrollView(size_hint_y=1)
        scroll.add_widget(form)
        content.add_widget(scroll)

        lbl_err = Label(text='', color=(1, 0.3, 0.3, 1),
                        size_hint_y=None, height=26)
        content.add_widget(lbl_err)

        btns = BoxLayout(size_hint_y=None, height=44, spacing=12)
        lbl_ok     = Label(text='', color=(0.2, 0.9, 0.4, 1), font_size=12)
        btn_guardar  = Button(text='Guardar', background_color=(0.1, 0.65, 0.35, 1))
        btn_cancelar = Button(text='Cancelar', background_color=(0.35, 0.35, 0.35, 1))
        btns.add_widget(lbl_ok)
        btns.add_widget(btn_guardar)
        btns.add_widget(btn_cancelar)
        content.add_widget(btns)

        titulo = f'Editar Suscriptor — {cuenta_editar}' if es_edicion else 'Nuevo Suscriptor'
        popup = Popup(title=titulo, content=content, size_hint=(0.55, 0.82))

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
