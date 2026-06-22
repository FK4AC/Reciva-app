"""
Gestión dinámica de roles y permisos.
Tablas: roles (id, nombre, inmutable), permisos (rol_id, pantalla, puede_ver, puede_editar).
El rol 'superadmin' es inmutable y tiene todos los permisos sin excepción.
"""

PANTALLAS = [
    'dashboard', 'suscriptores', 'facturacion', 'tickets',
    'importar', 'estadisticas', 'volcado', 'usuarios', 'roles',
]

PANTALLAS_LABELS = {
    'dashboard':    'Dashboard',
    'suscriptores': 'Suscriptores',
    'facturacion':  'Facturación',
    'tickets':      'Tickets / PQR',
    'importar':     'Importar',
    'estadisticas': 'Estadísticas',
    'volcado':      'Volcado',
    'usuarios':     'Usuarios',
    'roles':        'Gestión de Roles',
}

_PERMISOS_DEFAULTS = {
    'admin': {
        'dashboard':    (True,  True),
        'suscriptores': (True,  True),
        'facturacion':  (True,  True),
        'tickets':      (True,  True),
        'importar':     (True,  True),
        'estadisticas': (True,  True),
        'volcado':      (True,  True),
        'usuarios':     (False, False),
        'roles':        (False, False),
    },
    'operador': {
        'dashboard':    (False, False),
        'suscriptores': (False, False),
        'facturacion':  (False, False),
        'tickets':      (True,  True),
        'importar':     (False, False),
        'estadisticas': (False, False),
        'volcado':      (False, False),
        'usuarios':     (False, False),
        'roles':        (False, False),
    },
}


def setup_tablas_roles(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id   INT AUTO_INCREMENT PRIMARY KEY,
            nombre    VARCHAR(50) NOT NULL UNIQUE,
            inmutable TINYINT(1)  NOT NULL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS permisos_roles (
            rol_id      INT         NOT NULL,
            pantalla    VARCHAR(50) NOT NULL,
            puede_ver   TINYINT(1)  NOT NULL DEFAULT 0,
            puede_editar TINYINT(1) NOT NULL DEFAULT 0,
            PRIMARY KEY (rol_id, pantalla),
            FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        INSERT IGNORE INTO roles (nombre, inmutable)
        VALUES ('superadmin', 1), ('admin', 0), ('operador', 0)
    """)
    conn.commit()

    # Convert usuarios.rol from ENUM to VARCHAR so dynamic roles can be assigned
    try:
        cur.execute("""
            ALTER TABLE usuarios
            MODIFY COLUMN rol VARCHAR(50) NOT NULL DEFAULT 'operador'
        """)
        conn.commit()
    except Exception:
        pass

    for rol_nombre, defaults in _PERMISOS_DEFAULTS.items():
        cur.execute("SELECT id FROM roles WHERE nombre=%s", (rol_nombre,))
        row = cur.fetchone()
        if not row:
            continue
        rol_id = row[0]
        for pantalla, (ver, editar) in defaults.items():
            cur.execute("""
                INSERT IGNORE INTO permisos_roles (rol_id, pantalla, puede_ver, puede_editar)
                VALUES (%s, %s, %s, %s)
            """, (rol_id, pantalla, int(ver), int(editar)))
    conn.commit()
    cur.close()


def cargar_permisos(conn, rol_nombre):
    """Devuelve dict pantalla → (puede_ver, puede_editar). Superadmin siempre True."""
    if rol_nombre == 'superadmin':
        return {p: (True, True) for p in PANTALLAS}
    cur = conn.cursor()
    cur.execute("""
        SELECT pr.pantalla, pr.puede_ver, pr.puede_editar
        FROM permisos_roles pr
        JOIN roles r ON r.id = pr.rol_id
        WHERE r.nombre = %s
    """, (rol_nombre,))
    rows = cur.fetchall()
    cur.close()
    result = {p: (False, False) for p in PANTALLAS}
    for pantalla, ver, editar in rows:
        if pantalla in result:
            result[pantalla] = (bool(ver), bool(editar))
    return result


def listar_roles(conn):
    """Devuelve lista de dicts: id, nombre, inmutable, n_usuarios."""
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.nombre, r.inmutable,
               (SELECT COUNT(*) FROM usuarios u WHERE BINARY u.rol = BINARY r.nombre) AS n_usuarios
        FROM roles r
        ORDER BY r.id
    """)
    rows = cur.fetchall()
    cur.close()
    return [{'id': r[0], 'nombre': r[1], 'inmutable': bool(r[2]), 'n_usuarios': r[3]}
            for r in rows]


def listar_permisos_rol(conn, rol_id):
    """Devuelve dict pantalla → (puede_ver, puede_editar) para un rol por ID."""
    cur = conn.cursor()
    cur.execute(
        "SELECT pantalla, puede_ver, puede_editar FROM permisos_roles WHERE rol_id=%s",
        (rol_id,)
    )
    rows = cur.fetchall()
    cur.close()
    result = {p: (False, False) for p in PANTALLAS}
    for pantalla, ver, editar in rows:
        if pantalla in result:
            result[pantalla] = (bool(ver), bool(editar))
    return result


def guardar_permisos_rol(conn, rol_id, permisos_dict):
    """Reemplaza todos los permisos de un rol. permisos_dict: pantalla → (ver, editar)."""
    cur = conn.cursor()
    cur.execute("DELETE FROM permisos_roles WHERE rol_id=%s", (rol_id,))
    for pantalla, (ver, editar) in permisos_dict.items():
        cur.execute("""
            INSERT INTO permisos_roles (rol_id, pantalla, puede_ver, puede_editar)
            VALUES (%s, %s, %s, %s)
        """, (rol_id, pantalla, int(ver), int(editar)))
    conn.commit()
    cur.close()


def crear_rol(conn, nombre):
    """Crea un rol nuevo sin permisos. Devuelve (ok, id_o_error)."""
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO roles (nombre, inmutable) VALUES (%s, 0)", (nombre,))
        conn.commit()
        return True, cur.lastrowid
    except Exception as e:
        return False, str(e)
    finally:
        cur.close()


def eliminar_rol(conn, rol_id):
    """Elimina un rol (falla si tiene usuarios asignados o es inmutable)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT nombre, inmutable FROM roles WHERE id=%s", (rol_id,))
        row = cur.fetchone()
        if not row:
            return False, 'Rol no encontrado'
        nombre, inmutable = row
        if inmutable:
            return False, f'El rol "{nombre}" es inmutable y no puede eliminarse'
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE rol=%s", (nombre,))
        n = cur.fetchone()[0]
        if n > 0:
            return False, f'Hay {n} usuario(s) con este rol. Cambia su rol antes de eliminar.'
        cur.execute("DELETE FROM roles WHERE id=%s", (rol_id,))
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        cur.close()
