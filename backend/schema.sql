CREATE TABLE IF NOT EXISTS uebungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    status      TEXT DEFAULT 'vorbereitung',
    start_zeit  DATETIME,
    end_zeit    DATETIME,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geraete (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    uebung_id     INTEGER REFERENCES uebungen(id),
    name          TEXT NOT NULL,
    typ           TEXT NOT NULL,
    staerke_alpha   REAL DEFAULT 0.0,
    staerke_beta    REAL DEFAULT 0.0,
    staerke_gamma   REAL DEFAULT 0.0,
    gesamtdosis   REAL DEFAULT 0.0,
    mcu_adresse   TEXT,
    letzter_kontakt DATETIME,
    status TEXT,
    akku REAL,
    mac_adresse TEXT
);

CREATE TABLE IF NOT EXISTS messungen (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    geraet_id INTEGER REFERENCES geraete(id),
    uebung_id INTEGER REFERENCES uebungen(id),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    cps       REAL,
    dosis     REAL
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
    rolle         TEXT DEFAULT 'teilnehmer'  -- 'admin', 'uebungsleiter', 'teilnehmer'
);