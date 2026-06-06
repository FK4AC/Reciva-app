import pandas as pd
from db.connection import get_connection

# Filas por query SQL. 500 = buen balance entre latencia y tamaño de paquete.
_BATCH = 500

# Columnas mínimas para identificar cada tipo de archivo
_COLS_CATASTRO    = {'SUSCCODI', 'NOMBRE', 'ESTADO_SUMINISTRO'}
_COLS_FACTURACION = {'NUMERO_FACTURA', 'SUSCCODI', 'VALOR_RECIBO'}
_COLS_RECAUDO     = {'SUSCCODI', 'FECHA_RECAUDO', 'VALOR_RECIBO'}


def _verificar_columnas(cols, requeridas):
    """Devuelve string de error si faltan columnas, None si todo está bien."""
    faltantes = sorted(requeridas - cols)
    if faltantes:
        return f"Faltan columnas requeridas:\n  • " + "\n  • ".join(faltantes)
    return None


def _read_file(filepath):
    """Lee Excel o CSV pipe-delimitado y devuelve DataFrame con columnas normalizadas."""
    if filepath.lower().endswith('.csv'):
        try:
            df = pd.read_csv(filepath, sep='|', encoding='latin-1')
        except Exception:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        df.columns = [c.strip().strip('"').upper() for c in df.columns]
    else:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    return df


def _get_ano(row):
    """Lee el año tolerando variantes de codificación de Ñ (AÑO, A?O, ANO)."""
    for key in row.keys():
        if key.upper().replace('Ñ', 'N').replace('?', 'N') == 'ANO':
            try:
                return int(float(str(row[key])))
            except Exception:
                pass
    return 0


def _normalizar_mes(raw):
    """'01' → '1', '3.0' → '3', evita que mes='01' y mes='1' sean distintos."""
    try:
        return str(int(float(str(raw))))
    except Exception:
        return str(raw or '')


def _periodos_en_df(df):
    """Devuelve set de (año_int, mes_str) únicos presentes en un DataFrame."""
    periodos = set()
    for _, row in df.iterrows():
        año = _get_ano(row)
        mes = _normalizar_mes(row.get('MES', ''))
        if año and mes:
            periodos.add((año, mes))
    return periodos


def _periodos_con_datos(cursor, tabla, periodos):
    """
    Para cada (año, mes) del set 'periodos', consulta cuántos registros
    existen en 'tabla'. Devuelve lista de (periodo_str, count) con count > 0.
    """
    resultado = []
    for año, mes in sorted(periodos):
        cursor.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE año=%s AND mes=%s", (año, mes)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            resultado.append((f'{mes}/{año}', int(count)))
    return resultado


def _bulk_exec(cursor, conn, sql_prefix, ph, suffix, rows):
    """
    Ejecuta un INSERT multi-fila en lotes de _BATCH.
    sql_prefix : "INSERT [IGNORE] INTO tabla (cols) VALUES "
    ph         : "(%s,%s,...)"  — un placeholder por fila
    suffix     : " ON DUPLICATE KEY UPDATE ..."  o  ""
    Devuelve el rowcount acumulado.
    """
    total_rc = 0
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        sql   = sql_prefix + ', '.join([ph] * len(batch)) + suffix
        flat  = [v for row in batch for v in row]
        cursor.execute(sql, flat)
        conn.commit()
        total_rc += cursor.rowcount
    return total_rc


# ─────────────────────────────────────────────────────────────────────────────
#  CATASTRO
#  Estrategia: INSERT … ON DUPLICATE KEY UPDATE  (upsert multi-fila)
#  → Una sola consulta SQL por cada 500 filas, sin importar si son nuevas o no.
#  → rowcount = N_insertados + 2×N_actualizados  (comportamiento MySQL/TiDB)
# ─────────────────────────────────────────────────────────────────────────────
_CAT_PREFIX = """
    INSERT INTO suscriptores
    (susccodi, cuenta, nombre, direccion, municipio, barrio,
     subcategoria, estrato, estado_suministro, territorial,
     departamento, sufijo, desc_servicio, periodo)
    VALUES """
_CAT_PH     = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
_CAT_SUFFIX = """
     ON DUPLICATE KEY UPDATE
       cuenta=VALUES(cuenta), nombre=VALUES(nombre),
       direccion=VALUES(direccion), municipio=VALUES(municipio),
       barrio=VALUES(barrio), subcategoria=VALUES(subcategoria),
       estrato=VALUES(estrato), estado_suministro=VALUES(estado_suministro),
       territorial=VALUES(territorial), departamento=VALUES(departamento),
       sufijo=VALUES(sufijo), desc_servicio=VALUES(desc_servicio),
       periodo=VALUES(periodo)"""


def importar_catastro(filepath):
    try:
        df = _read_file(filepath)
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
        # Susccodi existentes antes de la importación
        cursor.execute("SELECT susccodi FROM suscriptores")
        existentes_db = {row[0] for row in cursor.fetchall()}

        all_rows   = []
        en_archivo = set()
        omitidos   = 0

        for _, row in df.iterrows():
            try:
                susccodi = int(row.get('SUSCCODI', 0) or 0)
                if not susccodi:
                    omitidos += 1
                    continue
                en_archivo.add(susccodi)
                subcategoria = str(
                    row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or ''
                )
                all_rows.append((
                    susccodi,
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
                ))
            except Exception:
                omitidos += 1

        if not all_rows:
            return False, "No se encontraron filas válidas en el archivo."

        # Upsert masivo
        rc = _bulk_exec(cursor, conn, _CAT_PREFIX, _CAT_PH, _CAT_SUFFIX, all_rows)

        # rowcount MySQL: 1 por insert, 2 por update con cambios, 0 si sin cambios
        n_total        = len(all_rows)
        n_actualizados = rc - n_total
        n_nuevos       = n_total - n_actualizados

        # Suscriptores que ya no aparecen en el catastro → RETIRADO
        retirados_ids = list(existentes_db - en_archivo)
        if retirados_ids:
            for i in range(0, len(retirados_ids), _BATCH):
                lote = retirados_ids[i:i + _BATCH]
                ph   = ', '.join(['%s'] * len(lote))
                cursor.execute(
                    f"UPDATE suscriptores SET estado_suministro='RETIRADO' "
                    f"WHERE susccodi IN ({ph})",
                    lote
                )
            conn.commit()

        return True, (f"Catastro importado: {n_nuevos} nuevos, "
                      f"{n_actualizados} actualizados, "
                      f"{len(retirados_ids)} retirados, "
                      f"{omitidos} omitidos")

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  FACTURACIÓN
#  Estrategia: INSERT IGNORE multi-fila en lotes.
#  El chequeo de duplicados lo maneja el índice único de la tabla (más rápido
#  que cargar todo el set en Python). rowcount indica cuántas se insertaron.
# ─────────────────────────────────────────────────────────────────────────────
_FAC_PREFIX = """
    INSERT IGNORE INTO facturas
    (numero_factura, susccodi, cuenta_contrato, fecha_facturacion,
     subcategoria, estrato_contrato, codigo_concepto, concepto,
     importe, valor_recibo, operacion, sector, municipio, año, mes)
    VALUES """
_FAC_PH = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"


def importar_facturacion(filepath, modo='nuevo'):
    try:
        df = _read_file(filepath)
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
        # Si modo=reemplazar, borrar períodos detectados antes de insertar
        if modo == 'reemplazar':
            for año, mes in _periodos_en_df(df):
                cursor.execute(
                    "DELETE FROM facturas WHERE año=%s AND mes=%s", (año, mes)
                )
            conn.commit()

        para_insertar = []
        omitidos      = 0
        vistos        = set()   # dedup dentro del mismo archivo

        for _, row in df.iterrows():
            try:
                numero_factura = int(
                    float(str(row.get('NUMERO_FACTURA', 0)).replace('E', 'e'))
                )
                susccodi = int(float(str(row.get('SUSCCODI', 0))))
                if not numero_factura or not susccodi or numero_factura in vistos:
                    omitidos += 1
                    continue
                vistos.add(numero_factura)

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
                    _get_ano(row),
                    _normalizar_mes(row.get('MES', '')),
                ))
            except Exception:
                omitidos += 1

        if not para_insertar:
            return True, f"Facturación: sin filas nuevas ({omitidos} omitidas)"

        # INSERT IGNORE: el índice único en numero_factura rechaza duplicados
        insertadas = _bulk_exec(cursor, conn, _FAC_PREFIX, _FAC_PH, '', para_insertar)
        duplicadas = len(para_insertar) - insertadas
        return True, (f"Facturación importada: {insertadas} nuevas, "
                      f"{duplicadas + omitidos} omitidas/duplicadas")

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  RECAUDO
#  Estrategia: dedup en Python (tabla no tiene clave única uniforme),
#  luego INSERT multi-fila en lotes.
# ─────────────────────────────────────────────────────────────────────────────
_REC_PREFIX = """
    INSERT INTO recaudos
    (susccodi, cuenta_contrato, numero_factura, fecha_facturacion,
     fecha_recaudo, subcategoria, estrato_contrato, codigo_concepto,
     concepto, importe, valor_recibo, sector, municipio, año, mes)
    VALUES """
_REC_PH = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"


def importar_recaudo(filepath, modo='nuevo'):
    try:
        df = _read_file(filepath)
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
        periodos = _periodos_en_df(df)

        # Si modo=reemplazar, limpiar los períodos antes de insertar
        if modo == 'reemplazar':
            for año, mes in periodos:
                cursor.execute(
                    "DELETE FROM recaudos WHERE año=%s AND mes=%s", (año, mes)
                )
            conn.commit()

        para_insertar = []
        omitidos      = 0

        def s(val, maxlen=100):
            return str(val or '')[:maxlen]

        for _, row in df.iterrows():
            try:
                susccodi = int(float(str(row.get('SUSCCODI', 0))))
                if not susccodi:
                    omitidos += 1
                    continue

                try:
                    fecha_fac = pd.to_datetime(str(row.get('FECHA_FACTURACION', ''))).date()
                except Exception:
                    fecha_fac = None
                try:
                    fecha_rec = pd.to_datetime(str(row.get('FECHA_RECAUDO', ''))).date()
                except Exception:
                    fecha_rec = None

                numero_factura = row.get('NUMERO_FACTURA', None)
                if numero_factura:
                    try:
                        numero_factura = int(float(str(numero_factura)))
                    except Exception:
                        numero_factura = None

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
                    _get_ano(row),
                    _normalizar_mes(row.get('MES', '')),
                ))
            except Exception:
                omitidos += 1

        if not para_insertar:
            return True, f"Recaudo: sin registros nuevos ({omitidos} omitidos)"

        # INSERT IGNORE: el índice único (cuenta_contrato, año, mes) rechaza duplicados
        _REC_IGNORE = _REC_PREFIX.replace('INSERT INTO recaudos', 'INSERT IGNORE INTO recaudos')
        insertadas = _bulk_exec(cursor, conn, _REC_IGNORE, _REC_PH, '', para_insertar)
        duplicadas = len(para_insertar) - insertadas
        return True, (f"Recaudo importado: {insertadas} registros"
                      + (f", {duplicadas} omitidos/duplicados" if duplicadas else ""))

    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────
#  PREVISUALIZACIONES (dry-run sin escribir en la base de datos)
# ──────────────────────────────────────────────────────────────────

def previsualizar_catastro(filepath):
    try:
        df = _read_file(filepath)
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' in cols:
        return False, "Este archivo es un RECAUDO, no un catastro."
    if 'NUMERO_FACTURA' in cols and 'ESTADO_SUMINISTRO' not in cols:
        return False, "Este archivo parece ser una FACTURACIÓN, no un catastro."

    err = _verificar_columnas(cols, _COLS_CATASTRO)
    if err:
        return False, err

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT susccodi FROM suscriptores")
        existentes = {row[0] for row in cursor.fetchall()}
    except Exception as e:
        return False, f"Error DB: {e}"
    finally:
        cursor.close()
        conn.close()

    total = nuevos = actualizados = omitidos = 0
    en_archivo = set()
    muestra_n, muestra_a = [], []

    for _, row in df.iterrows():
        try:
            susccodi = int(row.get('SUSCCODI', 0) or 0)
            if not susccodi:
                omitidos += 1
                continue
            total += 1
            en_archivo.add(susccodi)
            nombre = str(row.get('NOMBRE', '') or '')
            barrio = str(row.get('BARRIO', '') or '')
            subcategoria = str(row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or '')
            estrato = subcategoria.split('-')[0].strip()
            estado = str(row.get('ESTADO_SUMINISTRO', '') or '')

            if susccodi in existentes:
                actualizados += 1
                if len(muestra_a) < 4:
                    muestra_a.append((str(susccodi), nombre[:25], barrio[:15], estrato, estado, 'Actualizar'))
            else:
                nuevos += 1
                if len(muestra_n) < 4:
                    muestra_n.append((str(susccodi), nombre[:25], barrio[:15], estrato, estado, 'Nuevo'))
        except Exception:
            omitidos += 1

    retirados = len(existentes - en_archivo)

    return True, {
        'tipo': 'Catastro',
        'total': total,
        'nuevas': nuevos,
        'actualizados': actualizados,
        'retirados': retirados,
        'omitidas': omitidos,
        'periodos': [],
        'columnas': ['Susccodi', 'Nombre', 'Barrio', 'Estrato', 'Estado', 'Acción'],
        'muestra': (muestra_n + muestra_a)[:8],
    }


def _sort_periodo(p):
    try:
        mes, año = p.split('/')
        return (int(año), int(mes))
    except Exception:
        return (0, 0)


def previsualizar_facturacion(filepath):
    try:
        df = _read_file(filepath)
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' in cols:
        return False, "Este archivo es un RECAUDO, no una facturación."
    if 'ESTADO_SUMINISTRO' in cols:
        return False, "Este archivo es un CATASTRO, no una facturación."

    err = _verificar_columnas(cols, _COLS_FACTURACION)
    if err:
        return False, err

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"
    cursor = conn.cursor()
    existentes          = set()
    periodos_existentes = []
    try:
        cursor.execute("SELECT numero_factura FROM facturas")
        existentes = {row[0] for row in cursor.fetchall()}
        # Detectar períodos del archivo que ya tienen datos
        periodos_existentes = _periodos_con_datos(cursor, 'facturas',
                                                   _periodos_en_df(df))
    except Exception as e:
        return False, f"Error DB: {e}"
    finally:
        cursor.close()
        conn.close()

    total = nuevas = omitidas = 0
    periodos = set()
    muestra  = []

    for _, row in df.iterrows():
        try:
            nf   = int(float(str(row.get('NUMERO_FACTURA', 0)).replace('E', 'e')))
            susc = int(float(str(row.get('SUSCCODI', 0))))
            if not nf or not susc:
                omitidas += 1
                continue
            total += 1
            año = _get_ano(row)
            mes = _normalizar_mes(row.get('MES', ''))
            if año and mes:
                periodos.add(f'{mes}/{año}')
            if nf in existentes:
                omitidas += 1
            else:
                nuevas += 1
                if len(muestra) < 8:
                    cuenta = int(float(str(row.get('CUENTA_CONTRATO', 0) or 0)))
                    valor  = float(row.get('VALOR_RECIBO', 0) or 0)
                    muestra.append((str(nf), str(cuenta), f'{mes}/{año}', f'${valor:,.0f}'))
        except Exception:
            omitidas += 1

    return True, {
        'tipo': 'Facturación',
        'total': total,
        'nuevas': nuevas,
        'omitidas': omitidas,
        'periodos': sorted(periodos, key=_sort_periodo),
        'periodos_existentes': periodos_existentes,
        'columnas': ['N° Factura', 'Cuenta', 'Período', 'Valor'],
        'muestra': muestra,
    }


def previsualizar_recaudo(filepath):
    try:
        df = _read_file(filepath)
    except Exception as e:
        return False, f"Error al leer archivo: {e}"

    cols = set(df.columns)
    if 'FECHA_RECAUDO' not in cols:
        if 'ESTADO_SUMINISTRO' in cols:
            return False, "Este archivo es un CATASTRO, no un recaudo."
        return False, "Este archivo no parece un recaudo (falta columna FECHA_RECAUDO)."

    err = _verificar_columnas(cols, _COLS_RECAUDO)
    if err:
        return False, err

    conn = get_connection()
    if not conn:
        return False, "Error de conexión"
    cursor = conn.cursor()
    periodos_existentes = []
    try:
        # Detectar períodos del archivo que ya tienen datos en DB
        periodos_existentes = _periodos_con_datos(cursor, 'recaudos',
                                                   _periodos_en_df(df))
    except Exception as e:
        return False, f"Error DB: {e}"
    finally:
        cursor.close()
        conn.close()

    total = nuevas = omitidas = 0
    periodos = set()
    muestra  = []

    for _, row in df.iterrows():
        try:
            susccodi = int(float(str(row.get('SUSCCODI', 0))))
            if not susccodi:
                omitidas += 1
                continue
            total += 1

            try:
                fecha_rec = pd.to_datetime(str(row.get('FECHA_RECAUDO', ''))).date()
            except Exception:
                fecha_rec = None

            numero_factura = row.get('NUMERO_FACTURA', None)
            if numero_factura:
                try:
                    numero_factura = int(float(str(numero_factura)))
                except Exception:
                    numero_factura = None

            año  = _get_ano(row)
            mes  = _normalizar_mes(row.get('MES', ''))
            valor = float(row.get('VALOR_RECIBO', 0) or 0)

            if año and mes:
                periodos.add(f'{mes}/{año}')

            nuevas += 1
            if len(muestra) < 8:
                nf_str     = str(numero_factura) if numero_factura else '—'
                cuenta_str = str(int(float(str(row.get('CUENTA_CONTRATO', 0) or 0))))
                muestra.append((nf_str, cuenta_str,
                                 str(fecha_rec) if fecha_rec else '—',
                                 f'${valor:,.0f}'))
        except Exception:
            omitidas += 1

    return True, {
        'tipo': 'Recaudo',
        'total': total,
        'nuevas': nuevas,
        'omitidas': omitidas,
        'periodos': sorted(periodos, key=_sort_periodo),
        'periodos_existentes': periodos_existentes,
        'columnas': ['N° Factura', 'Cuenta', 'Fecha Recaudo', 'Valor'],
        'muestra': muestra,
    }
