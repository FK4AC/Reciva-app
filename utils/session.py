import json
import os
from datetime import datetime, timedelta

_EXPIRY_DAYS = 30


def _session_path() -> str:
    base = os.getenv('APPDATA') or os.path.expanduser('~')
    folder = os.path.join(base, 'Reciva')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, 'session.json')


def guardar_sesion(user: dict):
    data = {
        'id':        user.get('id'),
        'nombre':    user.get('nombre', ''),
        'email':     user.get('email', ''),
        'rol':       user.get('rol', 'operador'),
        'logged_at': datetime.now().isoformat(),
    }
    try:
        with open(_session_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def cargar_sesion() -> dict | None:
    try:
        with open(_session_path(), encoding='utf-8') as f:
            data = json.load(f)
        logged_at = datetime.fromisoformat(data['logged_at'])
        if datetime.now() - logged_at > timedelta(days=_EXPIRY_DAYS):
            borrar_sesion()
            return None
        return data
    except Exception:
        return None


def borrar_sesion():
    try:
        os.remove(_session_path())
    except Exception:
        pass
