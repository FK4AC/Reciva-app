from datetime import datetime

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty

from db.connection import get_connection

TIPOS  = ['Petición', 'Queja', 'Recurso']
ESTADOS = ['Abierto', 'En Proceso', 'Resuelto']

COLOR_ESTADO = {
    'Abierto':    (0.90, 0.20, 0.20, 1),
    'En Proceso': (0.90, 0.60, 0.10, 1),
    'Resuelto':   (0.10, 0.80, 0.30, 1),
}
COLOR_TIPO = {
    'Petición': (0.20, 0.55, 0.90, 1),
    'Queja':    (0.90, 0.30, 0.30, 1),
    'Recurso':  (0.80, 0.50, 0.10, 1),
}


class TicketsScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self.cargar_lista()

    def cargar_lista(self):
        lista = self.ids.lista_pqr
        lista.clear_widgets()

        estado = self.ids.filtro_estado.text
        tipo   = self.ids.filtro_tipo.text

        conn = get_connection()
        if not conn:
            self.mensaje = 'Error de conexión'
            return

        cursor = conn.cursor()
        try:
            where, params = [], []
            if estado != 'Todos':
                where.append("estado=%s");  params.append(estado)
            if tipo != 'Todos':
                where.append("tipo=%s");    params.append(tipo)

            sql = ("SELECT id, nombre_suscriptor, tipo, asunto, estado, "
                   "DATE(fecha_creacion) FROM pqr")
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY fecha_creacion DESC LIMIT 200"

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            self.mensaje = f'{len(rows)} PQR encontradas'

            for row in rows:
                lista.add_widget(self._fila(*row))

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    def _fila(self, pqr_id, nombre, tipo, asunto, estado, fecha):
        fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=2)
        with fila.canvas.before:
            Color(0.11, 0.11, 0.20, 1)
            rect = Rectangle(pos=fila.pos, size=fila.size)
        fila.bind(pos=lambda inst, v, r=rect: setattr(r, 'pos', v))
        fila.bind(size=lambda inst, v, r=rect: setattr(r, 'size', v))

        col_e = COLOR_ESTADO.get(estado, (0.7, 0.7, 0.7, 1))
        col_t = COLOR_TIPO.get(tipo,   (0.7, 0.7, 0.7, 1))

        for txt, sx, col in [
            (f'#{pqr_id}',           0.06, (0.5, 0.5, 0.5, 1)),
            ((nombre or '-')[:25],   0.25, (0.9, 0.9, 0.9, 1)),
            (tipo or '-',            0.12, col_t),
            ((asunto or '-')[:28],   0.26, (0.8, 0.8, 0.8, 1)),
            (estado or '-',          0.13, col_e),
            (str(fecha),             0.11, (0.6, 0.6, 0.6, 1)),
        ]:
            lbl = Label(text=txt, size_hint_x=sx, font_size=12, color=col,
                        halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
            fila.add_widget(lbl)

        btn = Button(text='Ver', size_hint_x=0.07, font_size=12,
                     background_color=(0.2, 0.6, 1, 1))
        btn.bind(on_press=lambda _, pid=pqr_id: self._ver_pqr(pid))
        fila.add_widget(btn)
        return fila

    # ------------------------------------------------------------------
    #  Popup: Nueva PQR
    # ------------------------------------------------------------------
    def nueva_pqr(self):
        content = BoxLayout(orientation='vertical', spacing=8, padding=15)

        content.add_widget(Label(
            text='Buscar suscriptor (opcional)',
            bold=True, color=(0.5, 0.75, 1, 1),
            size_hint_y=None, height=26
        ))

        buscar_box = BoxLayout(size_hint_y=None, height=40, spacing=8)
        inp_buscar = TextInput(hint_text='Cuenta o nombre...', multiline=False, size_hint_x=0.72)
        btn_buscar = Button(text='Buscar', size_hint_x=0.28,
                            background_color=(0.2, 0.6, 1, 1))
        buscar_box.add_widget(inp_buscar)
        buscar_box.add_widget(btn_buscar)
        content.add_widget(buscar_box)

        res_scroll = ScrollView(size_hint_y=None, height=88)
        res_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        res_box.bind(minimum_height=res_box.setter('height'))
        res_scroll.add_widget(res_box)
        content.add_widget(res_scroll)

        lbl_sel = Label(
            text='Sin suscriptor seleccionado',
            color=(0.55, 0.55, 0.55, 1), italic=True,
            size_hint_y=None, height=26
        )
        content.add_widget(lbl_sel)

        form = GridLayout(cols=2, size_hint_y=None, height=170, spacing=8)
        form.add_widget(Label(text='Tipo *', color=(0.5, 0.75, 1, 1), halign='right'))
        sp_tipo = Spinner(text='Queja', values=TIPOS)
        form.add_widget(sp_tipo)

        form.add_widget(Label(text='Asunto *', color=(0.5, 0.75, 1, 1), halign='right'))
        inp_asunto = TextInput(hint_text='Describe el asunto brevemente...', multiline=False)
        form.add_widget(inp_asunto)

        form.add_widget(Label(text='Descripción', color=(0.5, 0.75, 1, 1), halign='right'))
        inp_desc = TextInput(hint_text='Detalle adicional...', multiline=True)
        form.add_widget(inp_desc)
        content.add_widget(form)

        lbl_err = Label(text='', color=(1, 0.3, 0.3, 1), size_hint_y=None, height=24)
        content.add_widget(lbl_err)

        btns = BoxLayout(size_hint_y=None, height=42, spacing=10)
        btn_guardar  = Button(text='Guardar PQR',  background_color=(0.1, 0.7, 0.4, 1))
        btn_cancelar = Button(text='Cancelar', background_color=(0.35, 0.35, 0.35, 1))
        btns.add_widget(btn_guardar)
        btns.add_widget(btn_cancelar)
        content.add_widget(btns)

        popup = Popup(title='Nueva PQR', content=content, size_hint=(0.68, 0.88))
        state = {'cuenta': None, 'nombre': None}

        def buscar(_):
            res_box.clear_widgets()
            texto = inp_buscar.text.strip()
            if not texto:
                return
            conn = get_connection()
            if not conn:
                return
            cur = conn.cursor()
            try:
                like = f'%{texto}%'
                cur.execute("""
                    SELECT cuenta, nombre FROM suscriptores
                    WHERE nombre LIKE %s OR CAST(cuenta AS CHAR) LIKE %s
                    LIMIT 8
                """, (like, like))
                for cuenta, nombre in cur.fetchall():
                    b = Button(
                        text=f'{cuenta}  —  {nombre}',
                        size_hint_y=None, height=30,
                        background_color=(0.15, 0.15, 0.3, 1), font_size=12
                    )
                    def seleccionar(_, c=cuenta, n=nombre):
                        state['cuenta'] = c
                        state['nombre'] = n
                        lbl_sel.text = f'Seleccionado: {c} — {n}'
                        lbl_sel.color = (0.1, 0.9, 0.3, 1)
                    b.bind(on_press=seleccionar)
                    res_box.add_widget(b)
            finally:
                cur.close()
                conn.close()

        btn_buscar.bind(on_press=buscar)
        inp_buscar.bind(on_text_validate=buscar)

        def guardar(_):
            if not inp_asunto.text.strip():
                lbl_err.text = 'El asunto es obligatorio'
                return
            conn = get_connection()
            if not conn:
                lbl_err.text = 'Error de conexión'
                return
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO pqr
                    (cuenta_contrato, nombre_suscriptor, tipo, asunto, descripcion, estado)
                    VALUES (%s, %s, %s, %s, %s, 'Abierto')
                """, (
                    state['cuenta'],
                    state['nombre'] or 'Sin suscriptor',
                    sp_tipo.text,
                    inp_asunto.text.strip(),
                    inp_desc.text.strip() or None,
                ))
                conn.commit()
                popup.dismiss()
                self.cargar_lista()
                self.mensaje = 'PQR creada correctamente'
            except Exception as e:
                lbl_err.text = f'Error: {e}'
            finally:
                cur.close()
                conn.close()

        btn_guardar.bind(on_press=guardar)
        btn_cancelar.bind(on_press=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------------
    #  Popup: Ver / Actualizar PQR
    # ------------------------------------------------------------------
    def _ver_pqr(self, pqr_id):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, cuenta_contrato, nombre_suscriptor, tipo, asunto,
                       descripcion, estado, observaciones,
                       fecha_creacion, fecha_resolucion
                FROM pqr WHERE id=%s
            """, (pqr_id,))
            pqr = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if not pqr:
            return

        pid, cuenta, nombre, tipo, asunto, desc, estado, obs, fecha_c, fecha_r = pqr

        content = BoxLayout(orientation='vertical', spacing=8, padding=15)

        info = GridLayout(cols=2, size_hint_y=None, height=145, spacing=6)
        for lbl_t, val in [
            ('PQR #:',      str(pid)),
            ('Suscriptor:', f'{cuenta} — {nombre}' if cuenta else nombre or '—'),
            ('Tipo:',       tipo),
            ('Estado:',     estado),
            ('Creada:',     str(fecha_c)[:16] if fecha_c else '—'),
            ('Resuelto:',   str(fecha_r)[:16] if fecha_r else '—'),
        ]:
            info.add_widget(Label(text=lbl_t, bold=True, color=(0.5, 0.75, 1, 1),
                                  font_size=13, halign='right'))
            info.add_widget(Label(text=val, color=(1, 1, 1, 1),
                                  font_size=13, halign='left'))
        content.add_widget(info)

        for titulo, valor in [('Asunto:', asunto), ('Descripción:', desc)]:
            if valor:
                content.add_widget(Label(text=titulo, bold=True, color=(0.5, 0.75, 1, 1),
                                         size_hint_y=None, height=24))
                content.add_widget(Label(text=valor, color=(0.85, 0.85, 0.85, 1),
                                         size_hint_y=None, height=40,
                                         text_size=(None, None), halign='left'))

        content.add_widget(Label(text='Actualizar:', bold=True, color=(0.5, 0.75, 1, 1),
                                 size_hint_y=None, height=26))

        update_box = BoxLayout(size_hint_y=None, height=42, spacing=10)
        sp_estado = Spinner(text=estado, values=ESTADOS, size_hint_x=0.4)
        inp_obs   = TextInput(hint_text='Observaciones...', multiline=False,
                              text=obs or '', size_hint_x=0.6)
        update_box.add_widget(sp_estado)
        update_box.add_widget(inp_obs)
        content.add_widget(update_box)

        lbl_err = Label(text='', color=(1, 0.3, 0.3, 1), size_hint_y=None, height=24)
        content.add_widget(lbl_err)

        btns = BoxLayout(size_hint_y=None, height=42, spacing=10)
        btn_act    = Button(text='Actualizar',  background_color=(0.1, 0.7, 0.4, 1))
        btn_cerrar = Button(text='Cerrar', background_color=(0.35, 0.35, 0.35, 1))
        btns.add_widget(btn_act)
        btns.add_widget(btn_cerrar)
        content.add_widget(btns)

        popup = Popup(title=f'PQR #{pid} — {tipo}', content=content, size_hint=(0.62, 0.82))

        def actualizar(_):
            conn2 = get_connection()
            if not conn2:
                lbl_err.text = 'Error de conexión'
                return
            cur2 = conn2.cursor()
            try:
                nuevo_estado = sp_estado.text
                nueva_fecha_r = (datetime.now()
                                 if nuevo_estado == 'Resuelto' and estado != 'Resuelto'
                                 else fecha_r)
                cur2.execute("""
                    UPDATE pqr
                    SET estado=%s, observaciones=%s, fecha_resolucion=%s
                    WHERE id=%s
                """, (nuevo_estado, inp_obs.text.strip() or None, nueva_fecha_r, pid))
                conn2.commit()
                popup.dismiss()
                self.cargar_lista()
                self.mensaje = f'PQR #{pid} actualizada'
            except Exception as e:
                lbl_err.text = f'Error: {e}'
            finally:
                cur2.close()
                conn2.close()

        btn_act.bind(on_press=actualizar)
        btn_cerrar.bind(on_press=popup.dismiss)
        popup.open()
