# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para Reciva — Kivy 2.x + Windows
# Compilar con: pyinstaller Reciva.spec

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, collect_all

# collect_all('kivy') falla porque kivy.garden es un namespace package
# con __path__ personalizado que rompe pkgutil.iter_modules.
kivy_datas    = collect_data_files('kivy')
kivy_binaries = collect_dynamic_libs('kivy')

# Solo los subpaquetes que la app realmente usa.
# Se omiten kivy.modules (debug) y kivy.network (no usado).
kivy_hiddenimports = (
    collect_submodules('kivy.uix') +
    collect_submodules('kivy.graphics') +
    collect_submodules('kivy.core') +
    collect_submodules('kivy.input') +
    collect_submodules('kivy.lang') +
    collect_submodules('kivy.modules') +
    [
        'kivy', 'kivy.app', 'kivy.animation', 'kivy.atlas',
        'kivy.base', 'kivy.cache', 'kivy.clock', 'kivy.compat',
        'kivy.config', 'kivy.context', 'kivy.event', 'kivy.factory',
        'kivy.geometry', 'kivy.logger', 'kivy.metrics', 'kivy.parser',
        'kivy.properties', 'kivy.resources', 'kivy.setupconfig',
        'kivy.support', 'kivy.utils', 'kivy.vector', 'kivy.weakmethod',
    ]
)

# Estas librerias tienen data files y submodules dinamicos que
# collect_all incluye y que los hiddenimports manuales omiten.
pd_datas,   pd_bins,   pd_hidden   = collect_all('pandas')
xl_datas,   xl_bins,   xl_hidden   = collect_all('openpyxl')
np_datas,   np_bins,   np_hidden   = collect_all('numpy')
rl_datas,   rl_bins,   rl_hidden   = collect_all('reportlab')
pil_datas,  pil_bins,  pil_hidden  = collect_all('PIL')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=kivy_binaries + pd_bins + xl_bins + np_bins + rl_bins + pil_bins,
    datas=kivy_datas + pd_datas + xl_datas + np_datas + rl_datas + pil_datas + [
        ('reciva.kv',      '.'),
        ('fonts',          'fonts'),
        ('logo_png',       'logo_png'),
        ('version.py',     '.'),
        # config.py y theme.py NO van aqui: PyInstaller los compila
        # automaticamente al ser modulos importados desde main.py.
        # estados_cuenta SI va: la app escribe PDFs ahi en runtime.
        ('estados_cuenta', 'estados_cuenta'),
    ],
    hiddenimports=kivy_hiddenimports + pd_hidden + xl_hidden + np_hidden + rl_hidden + pil_hidden + [
        # Base de datos
        'pymysql',
        'pymysql.cursors',
        # Kivy PIL image provider (no incluido por collect_all('PIL'))
        'kivy.core.image.img_pil',
        # SSL para pymysql
        'ssl',
        '_ssl',
        # Stdlib usado explicitamente
        'hashlib',
        'threading',
        'csv',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        # Dependencias opcionales de pandas que no se usan
        'scipy',
        'matplotlib',
        'matplotlib.backends',

        'IPython',
        'jupyter',
        'notebook',
        'numba',
        'sqlalchemy',
        'boto3',
        'botocore',
        'pyarrow',
        'fastparquet',
        'tables',
        'blosc',
        'bottleneck',
        'numexpr',
        'statsmodels',
        'sklearn',
        'skimage',
        'cv2',
        'gi',
        'wx',
        # Kivy server/tools — no usados en produccion
        'kivy.network',
        'kivy.tools',
        # Documentacion y herramientas de desarrollo
        'docutils',
        'sphinx',
        'pygments',
        'babel',
        'jinja2',
        # Setuptools interno (no necesario en runtime)
        'setuptools',
        'pkg_resources',
        'pip',
        'wheel',
        # Otros innecesarios
        'xmlrpc',
        'pydoc',
        'pdb',
        'profile',
        'cProfile',
        'ftplib',
        'telnetlib',
        'imaplib',
        'poplib',
        'nntplib',
        'antigravity',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Reciva',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='logo_png/08-app-icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Reciva',
)
