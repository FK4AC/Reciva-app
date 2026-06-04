-- ============================================================
--  RECIVA — Script de creación de base de datos
--  Ejecutar una sola vez en MySQL Workbench o consola MySQL
-- ============================================================

CREATE DATABASE IF NOT EXISTS reciva_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE reciva_db;

-- ------------------------------------------------------------
--  Usuarios del sistema (login)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    nombre   VARCHAR(100)  NOT NULL,
    email    VARCHAR(150)  NOT NULL UNIQUE,
    password VARCHAR(64)   NOT NULL,   -- SHA-256 en hex
    activo   TINYINT(1)    NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Usuario por defecto: admin@reciva.com / 123456
-- (cambia la contraseña después del primer acceso)
INSERT IGNORE INTO usuarios (nombre, email, password, activo) VALUES (
    'Administrador',
    'admin@reciva.com',
    '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92',
    1
);

-- ------------------------------------------------------------
--  Suscriptores — importados desde catastro Excel
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suscriptores (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    susccodi          BIGINT       NOT NULL UNIQUE,   -- clave del archivo
    cuenta            BIGINT,                         -- = CUENTA_CONTRATO en facturas/recaudos
    nombre            VARCHAR(200),
    direccion         VARCHAR(300),
    municipio         VARCHAR(100),
    barrio            VARCHAR(100),
    subcategoria      VARCHAR(100),
    estrato           VARCHAR(50),
    estado_suministro VARCHAR(50),
    territorial       VARCHAR(100),
    departamento      VARCHAR(100),
    sufijo            VARCHAR(20),
    desc_servicio     VARCHAR(200),
    periodo           VARCHAR(20),
    INDEX idx_cuenta (cuenta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
--  Facturas — importadas desde facturación Excel
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facturas (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura   BIGINT        NOT NULL UNIQUE,
    susccodi         BIGINT,
    cuenta_contrato  BIGINT,
    fecha_facturacion DATE,
    subcategoria     VARCHAR(100),
    estrato_contrato VARCHAR(50),
    codigo_concepto  VARCHAR(20),
    concepto         VARCHAR(300),
    importe          DECIMAL(14,2) NOT NULL DEFAULT 0,
    valor_recibo     DECIMAL(14,2) NOT NULL DEFAULT 0,
    operacion        VARCHAR(50),
    sector           VARCHAR(50),
    municipio        VARCHAR(100),
    año              SMALLINT,
    mes              VARCHAR(20),
    INDEX idx_cuenta_contrato (cuenta_contrato),
    INDEX idx_año_mes (año, mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
--  Recaudos — importados desde recaudo Excel
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recaudos (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    susccodi          BIGINT,
    cuenta_contrato   BIGINT,
    numero_factura    BIGINT,
    fecha_facturacion DATE,
    fecha_recaudo     DATE,
    subcategoria      VARCHAR(100),
    estrato_contrato  VARCHAR(50),
    codigo_concepto   VARCHAR(20),
    concepto          VARCHAR(300),
    importe           DECIMAL(14,2) NOT NULL DEFAULT 0,
    valor_recibo      DECIMAL(14,2) NOT NULL DEFAULT 0,
    sector            VARCHAR(50),
    municipio         VARCHAR(100),
    año               SMALLINT,
    mes               VARCHAR(20),
    INDEX idx_cuenta_contrato (cuenta_contrato),
    INDEX idx_numero_factura  (numero_factura),
    INDEX idx_año_mes         (año, mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
--  PQR — Peticiones, Quejas y Recursos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pqr (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    cuenta_contrato    BIGINT,
    nombre_suscriptor  VARCHAR(200),
    tipo               VARCHAR(20)  NOT NULL DEFAULT 'Queja',
    asunto             VARCHAR(200) NOT NULL,
    descripcion        TEXT,
    estado             VARCHAR(20)  NOT NULL DEFAULT 'Abierto',
    observaciones      TEXT,
    fecha_creacion     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion   DATETIME,
    INDEX idx_estado          (estado),
    INDEX idx_tipo            (tipo),
    INDEX idx_cuenta_contrato (cuenta_contrato)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
