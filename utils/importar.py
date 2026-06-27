import pandas as pd
from db.connection import get_connection

# Filas por query SQL. 500 = buen balance entre latencia y tamaño de paquete.
_BATCH = 500

# Columnas mínimas para identificar cada tipo de archivo
_COLS_CATASTRO    = {'CUENTA', 'NOMBRE', 'ESTADO_SUMINISTRO'}
_COLS_FACTURACION = set()
_COLS_RECAUDO     = {'FECHA_RECAUDO', 'VALOR_RECIBO'}


def _verificar_columnas(cols, requeridas):
    """Devuelve string de error si faltan columnas, None si todo está bien."""
    faltantes = sorted(requeridas - cols)
    if faltantes:
        return f"Faltan columnas requeridas:\n  • " + "\n  • ".join(faltantes)
    return None


def _parse_fecha(val):
    """Convierte un valor de fecha a date.
    - Timestamps de Excel: usa .date() directo (ya parseado, sin riesgo de inversion).
    - Strings ISO (YYYY-MM-DD): parsea sin dayfirst para no invertir mes/dia.
    - Strings DD/MM/YYYY: dayfirst=True como fallback."""
    if val is None or (isinstance(val, float) and __import__('math').isnan(val)):
        return None
    if hasattr(val, 'date'):
        return val.date()
    s = str(val).strip()
    try:
        return pd.to_datetime(s, dayfirst=False).date()
    except Exception:
        pass
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


def _read_file(filepath):
    """Lee Excel o CSV (|, ;, ,) y devuelve DataFrame con columnas normalizadas."""
    if filepath.lower().endswith('.csv'):
        df = None
        for sep in ('|', ';', ','):
            try:
                tmp = pd.read_csv(filepath, sep=sep, encoding='latin-1')
                # Si solo queda 1 columna, el separador fue incorrecto
                if len(tmp.columns) > 1:
                    df = tmp
                    break
            except Exception:
                pass
        if df is None:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        df.columns = [c.strip().strip('"').upper() for c in df.columns]
    else:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    return df


def _parse_float(val):
    """Convierte a float tolerando coma decimal ('7.980,0' → 7980.0)."""
    try:
        return float(str(val or 0).replace(',', '.'))
    except Exception:
        try:
            # Formato europeo: '7.980,50' → quitar puntos de miles, coma → punto
            return float(str(val).replace('.', '').replace(',', '.'))
        except Exception:
            return 0.0


def _get_ano(row):
    """Lee el año tolerando AÑO/A?O/ANO o columna PERIODO (YYYYMM)."""
    for key in row.keys():
        if key.upper().replace('Ñ', 'N').replace('?', 'N') == 'ANO':
            try:
                return int(float(str(row[key])))
            except Exception:
                pass
    # Fallback: columna PERIODO con formato YYYYMM
    periodo = str(row.get('PERIODO', '') or '')
    if len(periodo) == 6 and periodo.isdigit():
        return int(periodo[:4])
    return 0


def _get_mes(row):
    """Lee el mes desde MES o desde PERIODO (YYYYMM)."""
    mes = row.get('MES', None)
    if mes is not None and str(mes).strip():
        return _normalizar_mes(mes)
    periodo = str(row.get('PERIODO', '') or '')
    if len(periodo) == 6 and periodo.isdigit():
        return str(int(periodo[4:6]))
    return ''


def _normalizar_mes(raw):
    """'01' → '1', '3.0' → '3', evita que mes='01' y mes='1' sean distintos."""
    try:
        return str(int(float(str(raw))))
    except Exception:
        return str(raw or '')


def get_file_columns(filepath):
    try:
        df = _read_file(filepath)
        return True, list(df.columns)
    except Exception as e:
        return False, str(e)


def _extraer_estrato(subcategoria):
    """
    '1 - ESTRATO 1'               → '1'
    '1 - COMERCIAL'               → 'COMERCIAL'
    '3 - OFICIAL'                 → 'OFICIAL'
    '5 - ALUMBRADO PÚBLICO'       → 'ALUMBRADO PÚBLICO'
    '13 - OFICIAL EDUCACION'      → 'OFICIAL EDUCACION'
    """
    if not subcategoria:
        return ''
    partes = str(subcategoria).split(' - ', 1)
    if len(partes) < 2:
        return subcategoria.strip()
    texto = partes[1].strip()
    import re
    if re.match(r'^ESTRATO\s+\d+$', texto, re.IGNORECASE):
        return partes[0].strip()   # solo el número
    return texto                   # nombre completo


def _apply_col_map(df, col_map):
    if not col_map:
        return df
    rename = {src: tgt for tgt, src in col_map.items()
              if src and src in df.columns and src != tgt}
    return df.rename(columns=rename)


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
            f"SELECT COUNT(*) FROM {tabla} WHERE anno=%s AND mes=%s", (año, mes)
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
    (cuenta, susccodi, nombre, direccion, municipio, barrio,
     subcategoria, estrato, estado_suministro, territorial,
     departamento, sufijo, desc_servicio, periodo)
    VALUES """
_CAT_PH     = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
_CAT_SUFFIX = """
     ON DUPLICATE KEY UPDATE
       susccodi=VALUES(susccodi), nombre=VALUES(nombre),
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
        # NICs existentes antes de la importación
        cursor.execute("SELECT cuenta FROM suscriptores")
        existentes_db = {row[0] for row in cursor.fetchall()}

        all_rows   = []
        en_archivo = set()
        omitidos   = 0

        for _, row in df.iterrows():
            try:
                nic = int(row.get('CUENTA', 0) or 0)
                if not nic:
                    omitidos += 1
                    continue
                en_archivo.add(nic)
                subcategoria = str(
                    row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or ''
                )
                all_rows.append((
                    nic,
                    int(row.get('SUSCCODI', 0) or 0),
                    str(row.get('NOMBRE', '') or ''),
                    str(row.get('DIRECCION', '') or ''),
                    str(row.get('MUNICIPIO', '') or ''),
                    str(row.get('BARRIO', '') or ''),
                    subcategoria,
                    _extraer_estrato(subcategoria),
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
                    f"WHERE cuenta IN ({ph})",
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
     valor_recibo, anno, mes)
    VALUES """
_FAC_PH = "(%s,%s,%s,%s,%s,%s,%s)"


def importar_facturacion(filepath, modo='nuevo', col_map=None):
    try:
        df = _read_file(filepath)
        df = _apply_col_map(df, col_map)
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
                    "DELETE FROM facturas WHERE anno=%s AND mes=%s", (año, mes)
                )
            conn.commit()

        para_insertar = []
        omitidos      = 0
        vistos        = set()   # dedup dentro del mismo archivo

        for _, row in df.iterrows():
            try:
                # NUMERO_FACTURA puede llamarse FACTURA en algunos formatos
                nf_raw = (row.get('NUMERO_FACTURA') or row.get('FACTURA') or 0)
                numero_factura = int(
                    float(str(nf_raw).replace('E', 'e'))
                )
                # NIC: CUENTA_CONTRATO o CUENTA según formato del archivo
                susccodi = int(_parse_float(
                    row.get('CUENTA_CONTRATO') or row.get('CUENTA') or 0
                ))
                if not numero_factura or numero_factura in vistos:
                    omitidos += 1
                    continue
                vistos.add(numero_factura)

                fecha_str = str(row.get('FECHA_FACTURACION', ''))
                try:
                    fecha = pd.to_datetime(fecha_str, dayfirst=True).date()
                except Exception:
                    fecha = None

                # SUSCCODI de INGESAM va como cuenta_contrato
                cuenta_contrato = int(_parse_float(row.get('SUSCCODI', 0) or 0))
                # VALOR_RECIBO puede llamarse VALOR_FACTURADO_TERCEROS
                valor_recibo = _parse_float(
                    row.get('VALOR_RECIBO') if row.get('VALOR_RECIBO') is not None
                    else row.get('VALOR_FACTURADO_TERCEROS', 0)
                )

                para_insertar.append((
                    numero_factura,
                    susccodi,
                    cuenta_contrato,
                    fecha,
                    valor_recibo,
                    _get_ano(row),
                    _get_mes(row),
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
    (numero_factura, susccodi, cuenta_contrato, fecha_facturacion,
     fecha_recaudo, valor_recibo, anno, mes)
    VALUES """
_REC_PH = "(%s,%s,%s,%s,%s,%s,%s,%s)"


def importar_recaudo(filepath, modo='nuevo', col_map=None):
    try:
        df = _read_file(filepath)
        df = _apply_col_map(df, col_map)
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
        # Mapa numero_factura → (año, mes) desde las facturas ya importadas.
        # Permite registrar cada recaudo en el período de su factura original,
        # no en el mes del archivo de recaudo.
        cursor.execute(
            "SELECT numero_factura, anno, mes FROM facturas WHERE numero_factura IS NOT NULL"
        )
        factura_map = {row[0]: (str(row[1]), str(row[2])) for row in cursor.fetchall()}

        # modo=reemplazar: borrar por numero_factura (no por período del archivo)
        if modo == 'reemplazar':
            nfs = []
            for _, row in df.iterrows():
                raw = row.get('NUMERO_FACTURA', None)
                if raw:
                    try:
                        nfs.append(int(float(str(raw))))
                    except Exception:
                        pass
            for i in range(0, len(nfs), _BATCH):
                lote = nfs[i:i + _BATCH]
                ph = ', '.join(['%s'] * len(lote))
                cursor.execute(
                    f"DELETE FROM recaudos WHERE numero_factura IN ({ph})", lote
                )
            conn.commit()

        para_insertar = []
        omitidos    = 0
        sin_factura = 0   # facturas del archivo que aún no están en DB

        for _, row in df.iterrows():
            try:
                susccodi = int(float(str(
                    row.get('CUENTA_CONTRATO') or row.get('CUENTA') or 0
                )))
                if not susccodi:
                    omitidos += 1
                    continue

                fecha_fac = _parse_fecha(row.get('FECHA_FACTURACION'))
                fecha_rec = _parse_fecha(row.get('FECHA_RECAUDO'))

                numero_factura = row.get('NUMERO_FACTURA', None)
                if numero_factura:
                    try:
                        numero_factura = int(float(str(numero_factura)))
                    except Exception:
                        numero_factura = None

                # Período correcto: el de la factura, no el del archivo
                if numero_factura and numero_factura in factura_map:
                    año_rec, mes_rec = factura_map[numero_factura]
                else:
                    año_rec = str(_get_ano(row))
                    mes_rec = _normalizar_mes(row.get('MES', ''))
                    if numero_factura:
                        sin_factura += 1

                para_insertar.append((
                    numero_factura,
                    susccodi,
                    int(float(str(row.get('SUSCCODI', 0) or 0))),
                    fecha_fac,
                    fecha_rec,
                    float(row.get('VALOR_RECIBO', 0) or 0),
                    año_rec,
                    mes_rec,
                ))
            except Exception:
                omitidos += 1

        if not para_insertar:
            return True, f"Recaudo: sin registros nuevos ({omitidos} omitidos)"

        # Dedup para registros sin numero_factura: el UNIQUE KEY ignora NULLs en MySQL/TiDB,
        # así que INSERT IGNORE no detecta duplicados en esos casos. Se filtra manualmente.
        sin_nf = [r for r in para_insertar if r[0] is None]
        if sin_nf:
            cuentas_nulas = list({r[2] for r in sin_nf if r[2]})
            existentes_nulos = set()
            for i in range(0, len(cuentas_nulas), _BATCH):
                lote = cuentas_nulas[i:i + _BATCH]
                ph = ', '.join(['%s'] * len(lote))
                cursor.execute(
                    f"SELECT cuenta_contrato, DATE(fecha_recaudo), valor_recibo "
                    f"FROM recaudos WHERE numero_factura IS NULL "
                    f"AND cuenta_contrato IN ({ph})", lote
                )
                for cc, fr, vr in cursor.fetchall():
                    existentes_nulos.add((int(cc or 0), str(fr), float(vr or 0)))
            con_nf = [r for r in para_insertar if r[0] is not None]
            filtrados = []
            for r in sin_nf:
                fecha_str = r[4].isoformat() if r[4] else None
                if (r[2], fecha_str, r[5]) not in existentes_nulos:
                    filtrados.append(r)
            para_insertar = con_nf + filtrados

        total_intentados = len(para_insertar)
        _REC_IGNORE = _REC_PREFIX.replace('INSERT INTO recaudos', 'INSERT IGNORE INTO recaudos')
        insertadas  = _bulk_exec(cursor, conn, _REC_IGNORE, _REC_PH, '', para_insertar)
        duplicadas  = total_intentados - insertadas

        partes = [f"Recaudo importado: {insertadas} registros"]
        if sin_factura:
            partes.append(f"{sin_factura} sin factura en DB (se usó período del archivo)")
        if duplicadas:
            partes.append(f"{duplicadas} duplicados omitidos")
        return True, ', '.join(partes)

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
        cursor.execute("SELECT cuenta FROM suscriptores")
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
            nic = int(row.get('CUENTA', 0) or 0)
            if not nic:
                omitidos += 1
                continue
            total += 1
            en_archivo.add(nic)
            nombre = str(row.get('NOMBRE', '') or '')
            barrio = str(row.get('BARRIO', '') or '')
            subcategoria = str(row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or '')
            estrato = subcategoria.split('-')[0].strip()
            estado = str(row.get('ESTADO_SUMINISTRO', '') or '')

            if nic in existentes:
                actualizados += 1
                if len(muestra_a) < 4:
                    muestra_a.append((str(nic), nombre[:25], barrio[:15], estrato, estado, 'Actualizar'))
            else:
                nuevos += 1
                if len(muestra_n) < 4:
                    muestra_n.append((str(nic), nombre[:25], barrio[:15], estrato, estado, 'Nuevo'))
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
        'columnas': ['Cuenta (NIC)', 'Nombre', 'Barrio', 'Estrato', 'Estado', 'Acción'],
        'muestra': (muestra_n + muestra_a)[:8],
    }


def _sort_periodo(p):
    try:
        mes, año = p.split('/')
        return (int(año), int(mes))
    except Exception:
        return (0, 0)


def previsualizar_facturacion(filepath, col_map=None):
    try:
        df = _read_file(filepath)
        df = _apply_col_map(df, col_map)
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
            nf   = int(float(str(row.get('NUMERO_FACTURA') or row.get('FACTURA') or 0).replace('E', 'e')))
            susc = int(float(str(row.get('CUENTA_CONTRATO') or row.get('CUENTA') or 0)))
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


def previsualizar_recaudo(filepath, col_map=None):
    try:
        df = _read_file(filepath)
        df = _apply_col_map(df, col_map)
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
    factura_map         = {}
    periodos_existentes = []
    try:
        cursor.execute(
            "SELECT numero_factura, anno, mes FROM facturas WHERE numero_factura IS NOT NULL"
        )
        factura_map = {row[0]: (str(row[1]), str(row[2])) for row in cursor.fetchall()}

        # Períodos reales = los de las facturas, no el mes del archivo
        periodos_reales = set()
        for _, row in df.iterrows():
            raw = row.get('NUMERO_FACTURA', None)
            if raw:
                try:
                    nf = int(float(str(raw)))
                    if nf in factura_map:
                        periodos_reales.add(factura_map[nf])
                except Exception:
                    pass
        periodos_existentes = _periodos_con_datos(cursor, 'recaudos', periodos_reales)
    except Exception as e:
        return False, f"Error DB: {e}"
    finally:
        cursor.close()
        conn.close()

    total = nuevas = omitidas = sin_factura = 0
    periodos = set()
    muestra  = []

    for _, row in df.iterrows():
        try:
            susccodi = int(float(str(
                row.get('CUENTA_CONTRATO') or row.get('CUENTA') or 0
            )))
            if not susccodi:
                omitidas += 1
                continue
            total += 1

            fecha_rec = _parse_fecha(row.get('FECHA_RECAUDO'))

            numero_factura = row.get('NUMERO_FACTURA', None)
            if numero_factura:
                try:
                    numero_factura = int(float(str(numero_factura)))
                except Exception:
                    numero_factura = None

            valor = float(row.get('VALOR_RECIBO', 0) or 0)

            if numero_factura and numero_factura in factura_map:
                año, mes = factura_map[numero_factura]
            else:
                año = str(_get_ano(row))
                mes = _normalizar_mes(row.get('MES', ''))
                if numero_factura:
                    sin_factura += 1

            if año and mes:
                periodos.add(f'{mes}/{año}')

            nuevas += 1
            if len(muestra) < 8:
                nf_str     = str(numero_factura) if numero_factura else '—'
                cuenta_str = str(int(float(str(row.get('CUENTA_CONTRATO', 0) or 0))))
                muestra.append((nf_str, cuenta_str, f'{mes}/{año}', f'${valor:,.0f}'))
        except Exception:
            omitidas += 1

    return True, {
        'tipo': 'Recaudo',
        'total': total,
        'nuevas': nuevas,
        'omitidas': omitidas,
        'sin_factura': sin_factura,
        'periodos': sorted(periodos, key=_sort_periodo),
        'periodos_existentes': periodos_existentes,
        'columnas': ['N° Factura', 'Cuenta', 'Período factura', 'Valor'],
        'muestra': muestra,
    }
