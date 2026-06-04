from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from db.connection import get_connection


class DashboardScreen(Screen):
    usuario_nombre    = StringProperty('')
    total_suscriptores = StringProperty('...')
    total_facturado   = StringProperty('...')
    total_recaudado   = StringProperty('...')
    deuda_total       = StringProperty('...')
    sus_con_deuda     = StringProperty('...')
    pqr_abiertas      = StringProperty('...')

    def on_enter(self):
        app = self.manager.app
        if app.current_user:
            self.usuario_nombre = app.current_user['nombre']
        self._cargar_stats()

    def _cargar_stats(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM suscriptores")
            self.total_suscriptores = f"{cursor.fetchone()[0]:,}"

            cursor.execute("SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas")
            total_fac = float(cursor.fetchone()[0])
            self.total_facturado = f'${total_fac:,.0f}'

            cursor.execute("SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos")
            total_rec = float(cursor.fetchone()[0])
            self.total_recaudado = f'${total_rec:,.0f}'
            self.deuda_total = f'${max(0, total_fac - total_rec):,.0f}'

            cursor.execute("""
                SELECT COUNT(DISTINCT cuenta_contrato) FROM facturas f
                WHERE NOT EXISTS (
                    SELECT 1 FROM recaudos r
                    WHERE r.cuenta_contrato = f.cuenta_contrato
                    AND r.año = f.año AND r.mes = f.mes
                )
            """)
            self.sus_con_deuda = f"{cursor.fetchone()[0]:,}"

            cursor.execute("SELECT COUNT(*) FROM pqr WHERE estado != 'Resuelto'")
            self.pqr_abiertas = str(cursor.fetchone()[0])

        except Exception as e:
            print(f'Error stats dashboard: {e}')
        finally:
            cursor.close()
            conn.close()
