import pandas as pd
from db.connection import get_connection


def importar_catastro(filepath):
    try:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' in cols:
        return False, "Error: este archivo es un RECAUDO, no un catastro."
    if 'NUMERO_FACTURA' in cols and 'ESTADO_SUMINISTRO' not in cols:
        return False, "Error: este archivo parece ser una FACTURACIÓN, no un catastro."

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT susccodi FROM suscriptores")
        existentes = {row[0] for row in cursor.fetchall()}

        para_insertar = []
        para_actualizar = []

        for _, row in df.iterrows():
            susccodi = int(row.get('SUSCCODI', 0) or 0)
            if not susccodi:
                continue

            subcategoria = str(row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or '')
            datos = (
                int(row.get('CUENTA', 0) or 0),
                str(row.get('NOMBRE', '') or ''),
                str(row.get('DIRECCION', '') or ''),
                str(row.get('MUNICIPIO', '') or ''),
                str(row.get('BARRIO', '') or ''),
                subcategoria,
                subcategoria.split('-')[0].strip(),
                str(row.get('ESTADO_SUMINISTRO', '') or ''),
                str(row.get('TERRITORIAL', '') or ''),
                str(row.get('DEPARTAMENTO', '') or ''),
                str(row.get('SUFIJO', '') or ''),
                str(row.get('DESC_SERVICIO', '') or ''),
                str(row.get('PERIODO', '') or ''),
            )

            if susccodi in existentes:
                para_actualizar.append(datos + (susccodi,))
            else:
                para_insertar.append((susccodi,) + datos)

        if para_insertar:
            cursor.executemany("""
                INSERT INTO suscriptores
                (susccodi, cuenta, nombre, direccion, municipio, barrio,
                 subcategoria, estrato, estado_suministro, territorial,
                 departamento, sufijo, desc_servicio, periodo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, para_insertar)

        if para_actualizar:
            cursor.executemany("""
                UPDATE suscriptores SET
                    cuenta=%s, nombre=%s, direccion=%s, municipio=%s,
                    barrio=%s, subcategoria=%s, estrato=%s,
                    estado_suministro=%s, territorial=%s, departamento=%s,
                    sufijo=%s, desc_servicio=%s, periodo=%s
                WHERE susccodi=%s
            """, para_actualizar)

        conn.commit()
        return True, f"Catastro importado: {len(para_insertar)} nuevos, {len(para_actualizar)} actualizados"

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


def importar_facturacion(filepath):
    try:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' in cols:
        return False, "Error: este archivo es un RECAUDO, no una facturación."
    if 'ESTADO_SUMINISTRO' in cols:
        return False, "Error: este archivo es un CATASTRO, no una facturación."

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT numero_factura FROM facturas")
        existentes = {row[0] for row in cursor.fetchall()}

        para_insertar = []
        omitidos = 0

        for _, row in df.iterrows():
            try:
                numero_factura = int(float(str(row.get('NUMERO_FACTURA', 0)).replace('E', 'e')))
                susccodi = int(float(str(row.get('SUSCCODI', 0))))
                if not numero_factura or not susccodi:
                    omitidos += 1
                    continue

                if numero_factura in existentes:
                    omitidos += 1
                    continue

                fecha_str = str(row.get('FECHA_FACTURACION', ''))
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except Exception:
                    fecha = None

                para_insertar.append((
                    numero_factura,
                    susccodi,
                    int(float(str(row.get('CUENTA_CONTRATO', 0) or 0))),
                    fecha,
                    str(row.get('SUBCATEGORIA', '') or ''),
                    str(row.get('ESTRATO_CONTRATO', '') or ''),
                    str(row.get('CODIGO_CONCEPTO', '') or ''),
                    str(row.get('CONCEPTO', '') or ''),
                    float(row.get('IMPORTE', 0) or 0),
                    float(row.get('VALOR_RECIBO', 0) or 0),
                    str(row.get('OPERACIÓN', '') or row.get('OPERACION', '') or ''),
                    str(row.get('SECTOR', '') or ''),
                    str(row.get('MUNICIPIO', '') or ''),
                    int(row.get('AÑO', 0) or 0),
                    str(row.get('MES', '') or ''),
                ))
                existentes.add(numero_factura)

            except Exception:
                omitidos += 1

        if para_insertar:
            cursor.executemany("""
                INSERT IGNORE INTO facturas
                (numero_factura, susccodi, cuenta_contrato, fecha_facturacion,
                 subcategoria, estrato_contrato, codigo_concepto, concepto,
                 importe, valor_recibo, operacion, sector, municipio, año, mes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, para_insertar)

        conn.commit()
        return True, f"Facturación importada: {len(para_insertar)} nuevas, {omitidos} omitidas"

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


def importar_recaudo(filepath):
    try:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' not in cols:
        if 'ESTADO_SUMINISTRO' in cols:
            return False, "Error: este archivo es un CATASTRO, no un recaudo."
        return False, "Error: este archivo no parece un recaudo (falta columna FECHA_RECAUDO)."

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"

    cursor = conn.cursor()
    try:
        # Cargamos claves existentes para prevenir reimportación del mismo archivo
        # Claves con numero_factura
        cursor.execute("SELECT numero_factura, fecha_recaudo FROM recaudos WHERE numero_factura IS NOT NULL")
        existentes_nf = {(row[0], str(row[1])) for row in cursor.fetchall()}

        # Claves alternativas para recaudos sin numero_factura
        cursor.execute("""
            SELECT susccodi, cuenta_contrato, año, mes, valor_recibo
            FROM recaudos WHERE numero_factura IS NULL
        """)
        existentes_alt = {
            (row[0], row[1], row[2], str(row[3]), float(row[4]))
            for row in cursor.fetchall()
        }

        para_insertar = []
        omitidos = 0

        def s(val, maxlen=100):
            return str(val or '')[:maxlen]

        for _, row in df.iterrows():
            try:
                susccodi = int(float(str(row.get('SUSCCODI', 0))))
                if not susccodi:
                    omitidos += 1
                    continue

                fecha_fac_str = str(row.get('FECHA_FACTURACION', ''))
                fecha_rec_str = str(row.get('FECHA_RECAUDO', ''))
                try:
                    fecha_fac = pd.to_datetime(fecha_fac_str).date()
                except Exception:
                    fecha_fac = None
                try:
                    fecha_rec = pd.to_datetime(fecha_rec_str).date()
                except Exception:
                    fecha_rec = None

                numero_factura = row.get('NUMERO_FACTURA', None)
                if numero_factura:
                    try:
                        numero_factura = int(float(str(numero_factura)))
                    except Exception:
                        numero_factura = None

                if numero_factura:
                    clave = (numero_factura, str(fecha_rec))
                    if clave in existentes_nf:
                        omitidos += 1
                        continue
                else:
                    cuenta = int(float(str(row.get('CUENTA_CONTRATO', 0) or 0)))
                    año_val = int(row.get('AÑO', 0) or 0)
                    mes_val = s(row.get('MES'), 20)
                    valor   = float(row.get('VALOR_RECIBO', 0) or 0)
                    clave_alt = (susccodi, cuenta, año_val, mes_val, valor)
                    if clave_alt in existentes_alt:
                        omitidos += 1
                        continue

                para_insertar.append((
                    susccodi,
                    int(float(str(row.get('CUENTA_CONTRATO', 0) or 0))),
                    numero_factura,
                    fecha_fac,
                    fecha_rec,
                    s(row.get('SUBCATEGORIA')),
                    s(row.get('ESTRATO_CONTRATO'), 20),
                    s(row.get('CODIGO_CONCEPTO'), 20),
                    s(row.get('CONCEPTO'), 200),
                    float(row.get('IMPORTE', 0) or 0),
                    float(row.get('VALOR_RECIBO', 0) or 0),
                    s(row.get('SECTOR'), 50),
                    s(row.get('MUNICIPIO'), 100),
                    int(row.get('AÑO', 0) or 0),
                    s(row.get('MES'), 20),
                ))
                if numero_factura:
                    existentes_nf.add(clave)
                else:
                    existentes_alt.add(clave_alt)

            except Exception:
                omitidos += 1

        if para_insertar:
            cursor.executemany("""
                INSERT INTO recaudos
                (susccodi, cuenta_contrato, numero_factura, fecha_facturacion,
                 fecha_recaudo, subcategoria, estrato_contrato, codigo_concepto,
                 concepto, importe, valor_recibo, sector, municipio, año, mes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, para_insertar)

        conn.commit()
        return True, f"Recaudo importado: {len(para_insertar)} registros, {omitidos} omitidos"

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()
