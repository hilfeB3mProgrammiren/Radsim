CREATE TABLE IF NOT EXISTS uebungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    status      TEXT DEFAULT 'vorbereitung',
    start_zeit  DATETIME,
    end_zeit    DATETIME,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geraete (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    uebung_id           INTEGER REFERENCES uebungen(id),
    name                TEXT NOT NULL,
    typ                 TEXT NOT NULL,
    -- Quellen-Stärken
    staerke_alpha       REAL DEFAULT 0.0,
    staerke_beta        REAL DEFAULT 0.0,
    staerke_gamma       REAL DEFAULT 0.0,
    -- Gesamtdosen Messgerät (mSv)
    gesamtdosis         REAL DEFAULT 0.0,   -- Gamma
    gesamtdosis_alpha   REAL DEFAULT 0.0,
    gesamtdosis_beta    REAL DEFAULT 0.0,
    mcu_adresse         TEXT,
    letzter_kontakt     DATETIME,
    status              TEXT,
    akku                REAL,
    mac_adresse         TEXT,
    -- MQTT-Felder
    mqtt_offset         REAL    DEFAULT 0.0,
    mqtt_reset          INTEGER DEFAULT 0,
    mqtt_status         TEXT    DEFAULT 'aktiv',
    -- Offset-Steuerung
    offset_alpha        REAL    DEFAULT 0.0,
    offset_beta         REAL    DEFAULT 0.0,
    offset_gamma        REAL    DEFAULT 0.0,
    offset_reset        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    geraet_id   INTEGER REFERENCES geraete(id),
    uebung_id   INTEGER REFERENCES uebungen(id),
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- Aktuelle Dosisraten (mSv/h)
    cps         REAL,               -- Legacy / Gamma-Alias
    cps_alpha   REAL DEFAULT 0.0,
    cps_beta    REAL DEFAULT 0.0,
    cps_gamma   REAL DEFAULT 0.0,
    -- Kumulierte Dosen (mSv)
    dosis       REAL,               -- Gamma (bleibt für Kompatibilität)
    dosis_alpha REAL DEFAULT 0.0,
    dosis_beta  REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS konfiguration (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    geraet_id   INTEGER REFERENCES geraete(id),
    parameter   TEXT,
    wert        TEXT,
    status      TEXT DEFAULT 'ausstehend',
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rolle         TEXT DEFAULT 'teilnehmer'
);
