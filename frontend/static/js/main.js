const socket = io();

/* =========================================================
   HILFSFUNKTIONEN
========================================================= */

const doseClasses = ["dose-green", "dose-yellow", "dose-orange", "dose-red", "dose-purple"];

function setDoseColor(element, value) {
    element.classList.remove(...doseClasses);
    if (value < 20)       element.classList.add("dose-green");
    else if (value < 50)  element.classList.add("dose-yellow");
    else if (value < 100) element.classList.add("dose-orange");
    else if (value < 200) element.classList.add("dose-red");
    else                  element.classList.add("dose-purple");
}

function updateDeviceCard(data) {
    const card = document.querySelector(`.device-card[data-id='${data.id}']`);
    if (!card) return;

    // Name
    if (data.name !== undefined) {
        card.dataset.name = data.name;
        const nameEl = card.querySelector(".device-name");
        if (nameEl) nameEl.innerText = data.name;
    }

    // MAC-Adresse
    if (data.mac_adresse !== undefined) {
        card.dataset.mcu = data.mac_adresse || "";
    }

    // Status
    if (data.status !== undefined) {
        card.dataset.status = data.status || "";
    }

    // Akku
    if (data.akku !== undefined) {
        card.dataset.akku = data.akku ?? "";
    }

    // Messwerte (Messgerät)
    const currentEl = card.querySelector(".current-dose");
    const totalEl   = card.querySelector(".total-dose");

    if (currentEl && data.cps !== undefined) {
        const v = parseFloat(data.cps);
        currentEl.innerText = v.toFixed(2) + " mSv/h";
        setDoseColor(currentEl, v);
    }
    if (totalEl && data.gesamtdosis !== undefined) {
        const v = parseFloat(data.gesamtdosis);
        totalEl.innerText = v.toFixed(2) + " mSv";
        setDoseColor(totalEl, v);
        card.dataset.gesamtdosis = v;
    }

    // Strahlungswerte (Quelle)
    const felder = { alpha: ".staerke-alpha", beta: ".staerke-beta", gamma: ".staerke-gamma" };
    for (const [typ, selector] of Object.entries(felder)) {
        const key = "staerke_" + typ;
        const el  = card.querySelector(selector);
        if (el && data[key] !== undefined) {
            const v = parseFloat(data[key]);
            el.innerText = v.toFixed(2) + " mSv/h";
            el.classList.toggle("aktiv", v > 0);
            card.dataset[typ] = v;
        }
    }

    // Falls Detail-Modal für dieses Gerät offen ist – auch dort updaten
    if (activeDeviceId == data.id) {
        fillDetailModal(card);
    }
}

/* =========================================================
   SOCKET EVENTS
========================================================= */

socket.on("measurement", data => {
    const cpsElement = document.getElementById("cps");
    if (cpsElement && data.cps !== undefined) {
        cpsElement.innerText = data.cps;
        updateChart(data.cps);
    }
    updateDeviceCard(data);
});

socket.on("device_updated", data => {
    updateDeviceCard(data);
});

socket.on("new_device", device => {
    const containerId = device.typ === "messgeraet" ? "devices-list" : "sources-list";
    const container   = document.getElementById(containerId);
    if (!container) return;

    // Karte schon vorhanden? Dann nur updaten, nicht doppelt einfügen
    const existing = container.querySelector(`.device-card[data-id='${device.id}']`);
    if (existing) {
        updateDeviceCard(device);
    } else {
        const addCard = container.querySelector(".add-device-card");
        const card    = buildDeviceCard(device);
        if (addCard) container.insertBefore(card, addCard);
        else         container.appendChild(card);
        bindCardClick(card);
    }

    // Sofort aktuelle Messwerte für dieses Gerät laden
    fetch("/measurements/latest")
        .then(r => r.json())
        .then(messungen => messungen.forEach(m => updateDeviceCard(m)));

    // Falls aus Übungs-Detail heraus hinzugefügt → Detail neu laden
    if (typeof aktiveUebungDetailId !== "undefined" && aktiveUebungDetailId) {
        openUebungDetail(aktiveUebungDetailId);
    }
});

/* =========================================================
   ÜBUNG – Live Badge + Dashboard-Reload
========================================================= */

function reloadDashboard(uebungId) {
    // Alle bestehenden Karten (außer Add-Karten) entfernen
    document.querySelectorAll(".device-card:not(.add-device-card)").forEach(c => c.remove());

    if (!uebungId) return;

    // Geräte der neuen Übung laden und Karten neu rendern
    fetch(`/uebung/${uebungId}`)
        .then(r => r.json())
        .then(u => {
            u.geraete.forEach(device => {
                const containerId = device.typ === "messgeraet" ? "devices-list" : "sources-list";
                const container   = document.getElementById(containerId);
                if (!container) return;

                const addCard = container.querySelector(".add-device-card");
                const card    = buildDeviceCard(device);

                if (addCard) container.insertBefore(card, addCard);
                else         container.appendChild(card);
                bindCardClick(card);
            });

            // Letzte Messwerte für alle neuen Karten sofort holen
            fetch("/measurements/latest")
                .then(r => r.json())
                .then(messungen => messungen.forEach(m => updateDeviceCard(m)));
        });
}

function buildDeviceCard(device) {
    const card = document.createElement("div");
    card.classList.add("device-card");
    card.dataset.id     = device.id;
    card.dataset.typ    = device.typ;
    card.dataset.name   = device.name;
    card.dataset.mcu    = device.mac_adresse || "";
    card.dataset.status = device.status || "";
    card.dataset.akku   = device.akku ?? "";

    const icon = device.typ === "messgeraet" ? "geiger_icon.png" : "quelle_icon.png";

    if (device.typ === "messgeraet") {
        card.dataset.gesamtdosis = device.gesamtdosis || 0;
        const v = parseFloat(device.gesamtdosis || 0);
        card.innerHTML = `
            <div class="device-icon"><img src="/static/img/${icon}" alt="${device.name}"></div>
            <div class="device-name">${device.name}</div>
            <div class="device-doses">
                <div class="current-dose dose-green">— mSv/h</div>
                <div class="total-dose ${doseClass(v)}">${v.toFixed(2)} mSv</div>
            </div>`;
    } else {
        card.dataset.alpha = device.staerke_alpha || 0;
        card.dataset.beta  = device.staerke_beta  || 0;
        card.dataset.gamma = device.staerke_gamma || 0;
        card.innerHTML = `
            <div class="device-icon"><img src="/static/img/${icon}" alt="${device.name}"></div>
            <div class="device-name">${device.name}</div>
            <div class="device-source-info">
                <div class="strahlung-zeile">
                    <span class="strahlungsart">α Alpha</span>
                    <span class="staerke-alpha staerke-wert ${parseFloat(device.staerke_alpha) > 0 ? 'aktiv' : ''}">
                        ${parseFloat(device.staerke_alpha || 0).toFixed(2)} mSv/h
                    </span>
                </div>
                <div class="strahlung-zeile">
                    <span class="strahlungsart">β Beta</span>
                    <span class="staerke-beta staerke-wert ${parseFloat(device.staerke_beta) > 0 ? 'aktiv' : ''}">
                        ${parseFloat(device.staerke_beta || 0).toFixed(2)} mSv/h
                    </span>
                </div>
                <div class="strahlung-zeile">
                    <span class="strahlungsart">γ Gamma</span>
                    <span class="staerke-gamma staerke-wert ${parseFloat(device.staerke_gamma) > 0 ? 'aktiv' : ''}">
                        ${parseFloat(device.staerke_gamma || 0).toFixed(2)} mSv/h
                    </span>
                </div>
            </div>`;
    }
    return card;
}

function doseClass(v) {
    if (v < 20)       return "dose-green";
    if (v < 50)       return "dose-yellow";
    if (v < 100)      return "dose-orange";
    if (v < 200)      return "dose-red";
    return "dose-purple";
}

socket.on("uebung_gestartet", data => {
    const badge = document.querySelector(".uebung-badge");
    if (badge) {
        badge.classList.remove("inaktiv");
        badge.classList.add("aktiv");
        badge.innerText = "● " + data.name;
    }
    reloadDashboard(data.id);
});

socket.on("uebung_gestoppt", () => {
    const badge = document.querySelector(".uebung-badge");
    if (badge) {
        badge.classList.remove("aktiv");
        badge.classList.add("inaktiv");
        badge.innerText = "Keine aktive Übung";
    }
    reloadDashboard(null);
});

/* =========================================================
   DETAIL MODAL
========================================================= */

let activeDeviceId  = null;
let activeDeviceTyp = null;

function fillDetailModal(card) {
    const typ  = card.dataset.typ;
    const name = card.dataset.name || card.querySelector(".device-name").innerText;

    // Header
    document.getElementById("detailTitel").innerText    = name;
    document.getElementById("detailTypBadge").innerText = typ;
    document.getElementById("detailIcon").src = typ === "messgeraet"
        ? "/static/img/geiger_icon.png"
        : "/static/img/quelle_icon.png";

    // Infos – input oder span je nach Login-Status
    const nameEl   = document.getElementById("detailName");
    const mcuEl    = document.getElementById("detailMcu");
    const statusEl = document.getElementById("detailStatus");
    const akkuEl   = document.getElementById("detailAkku");

    const setValue = (el, val) => {
        if (!el) return;
        if (el.tagName === "INPUT" || el.tagName === "SELECT") el.value = val || "";
        else el.innerText = val || "—";
    };

    setValue(nameEl,   name);
    setValue(mcuEl,    card.dataset.mcu);
    setValue(statusEl, card.dataset.status);
    setValue(akkuEl,   card.dataset.akku);

    document.getElementById("detailTyp").innerText = typ;

    // Rechte Spalte je nach Typ
    document.getElementById("detailMessgeraet").style.display = "none";
    document.getElementById("detailQuelle").style.display     = "none";

    if (typ === "messgeraet") {
    document.getElementById("detailMessgeraet").style.display = "block";

    const currentDose = card.querySelector(".current-dose")?.innerText || "— mSv/h";
    const totalDose   = parseFloat(card.dataset.gesamtdosis || 0);

    const currentEl = document.getElementById("detailCurrentDose");
    currentEl.innerText = currentDose;
    
    // Farbe für aktuelle Dosis
    const currentWert = parseFloat(currentDose);
    if (!isNaN(currentWert)) {
        setDoseColor(currentEl, currentWert);
    }

    const totalEl = document.getElementById("detailTotalDose");
    totalEl.innerText = totalDose.toFixed(2) + " mSv";
    setDoseColor(totalEl, totalDose);


    } else {
        document.getElementById("detailQuelle").style.display = "block";

        const alphaEl = document.getElementById("detailAlpha");
        const betaEl  = document.getElementById("detailBeta");
        const gammaEl = document.getElementById("detailGamma");

        setValue(alphaEl, parseFloat(card.dataset.alpha || 0).toFixed(2));
        setValue(betaEl,  parseFloat(card.dataset.beta  || 0).toFixed(2));
        setValue(gammaEl, parseFloat(card.dataset.gamma || 0).toFixed(2));
    }
}

function bindCardClick(card) {
    card.addEventListener("click", () => {
        activeDeviceId  = card.dataset.id;
        activeDeviceTyp = card.dataset.typ;
        fillDetailModal(card);
        document.getElementById("detailModal").style.display = "block";
    });
}

function closeDetail() {
    document.getElementById("detailModal").style.display = "none";
    activeDeviceId  = null;
    activeDeviceTyp = null;

    // Edit-Modus zurücksetzen
    const anzeige = document.getElementById("detailTotalDose");
    const input   = document.getElementById("detailTotalDoseInput");
    const btn     = document.getElementById("btnBearbeitenDosis");
    if (anzeige) anzeige.style.display = "block";
    if (input)   input.style.display   = "none";
    if (btn)     btn.innerText         = "✏ Bearbeiten";
    dosisEditAktiv = false;
}

// Allgemeine Infos speichern (Name, MCU, Status, Akku)
function saveDetails() {
    if (!activeDeviceId) return;

    const getName   = document.getElementById("detailName");
    const getMcu    = document.getElementById("detailMcu");
    const getStatus = document.getElementById("detailStatus");
    const getAkku   = document.getElementById("detailAkku");

    const akkuWert = parseFloat(getAkku?.value);
    const akkuFinal = isNaN(akkuWert) ? null : Math.min(100, Math.max(0, akkuWert));
    if (getAkku && akkuFinal !== null) getAkku.value = akkuFinal;

    fetch(`/device/${activeDeviceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name:        getName?.value,
            mac_adresse: getMcu?.value,
            status:      getStatus?.value,
            akku:        akkuFinal
        })
    }).then(r => {
        if (r.ok) {
            // Karte lokal sofort aktualisieren
            const card = document.querySelector(`.device-card[data-id='${activeDeviceId}']`);
            if (card) {
                card.dataset.mcu    = getMcu?.value || "";
                card.dataset.name   = getName?.value || "";
                card.dataset.status = getStatus?.value || "";
                card.dataset.akku   = getAkku?.value || "";
                const nameEl = card.querySelector(".device-name");
                if (nameEl) nameEl.innerText = getName?.value || "";
            }
            closeDetail();
        }
    });
}

// Strahlungswerte speichern (nur Quellen)
function saveStrahlung() {
    if (!activeDeviceId) return;
    fetch(`/device/${activeDeviceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            staerke_alpha: parseFloat(document.getElementById("detailAlpha").value) || 0,
            staerke_beta:  parseFloat(document.getElementById("detailBeta").value)  || 0,
            staerke_gamma: parseFloat(document.getElementById("detailGamma").value) || 0
        })
    }).then(r => { if (r.ok) closeDetail(); });
}

// Dosis bearbeiten – Toggle zwischen Anzeige und Eingabefeld
let dosisEditAktiv = false;

function toggleDosisEdit() {
    const anzeige = document.getElementById("detailTotalDose");
    const input   = document.getElementById("detailTotalDoseInput");
    const btn     = document.getElementById("btnBearbeitenDosis");

    if (!dosisEditAktiv) {
        // Bearbeitungsmodus aktivieren
        const aktuellerWert = parseFloat(anzeige.innerText);
        input.value = isNaN(aktuellerWert) ? 0 : aktuellerWert;
        anzeige.style.display = "none";
        input.style.display   = "block";
        btn.innerText = "✓ Speichern";
        dosisEditAktiv = true;
    } else {
        // Speichern
        const neuerWert = parseFloat(input.value) || 0;
        fetch(`/device/${activeDeviceId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gesamtdosis: neuerWert })
        }).then(r => {
            if (r.ok) {
                anzeige.innerText     = neuerWert.toFixed(2) + " mSv";
                setDoseColor(anzeige, neuerWert);
                anzeige.style.display = "block";
                input.style.display   = "none";
                btn.innerText = "✏ Bearbeiten";
                dosisEditAktiv = false;
            }
        });
    }
}

// Dosis zurücksetzen (nur Messgeräte)
function resetDosis() {
    if (!activeDeviceId) return;
    fetch(`/device/${activeDeviceId}/reset_dosis`, { method: "POST" })
        .then(r => {
            if (r.ok) {
                // Edit-Modus zurücksetzen falls aktiv
                document.getElementById("detailTotalDose").style.display      = "block";
                document.getElementById("detailTotalDoseInput").style.display = "none";
                document.getElementById("btnBearbeitenDosis").innerText       = "✏ Bearbeiten";
                dosisEditAktiv = false;
            }
        });
}

/* =========================================================
   GERÄT LÖSCHEN / AUS ÜBUNG ENTFERNEN
========================================================= */

function removeFromUebung() {
    if (!activeDeviceId) return;
    if (!confirm("Gerät aus der aktiven Übung entfernen?\nDas Gerät bleibt in der Datenbank erhalten.")) return;

    fetch(`/device/${activeDeviceId}/remove_from_uebung`, { method: "POST" })
        .then(r => {
            if (r.ok) {
                const card = document.querySelector(`.device-card[data-id='${activeDeviceId}']`);
                if (card) card.dataset.uebung = "";
                closeDetail();
            } else {
                alert("Fehler beim Entfernen aus der Übung.");
            }
        });
}

function deleteDevice() {
    if (!activeDeviceId) return;
    const name = document.getElementById("detailTitel")?.innerText || "dieses Gerät";
    if (!confirm(`„${name}" dauerhaft aus der Datenbank löschen?\nDiese Aktion kann nicht rückgängig gemacht werden.`)) return;

    fetch(`/device/${activeDeviceId}`, { method: "DELETE" })
        .then(r => {
            if (r.ok) {
                const card = document.querySelector(`.device-card[data-id='${activeDeviceId}']`);
                if (card) card.remove();
                closeDetail();
            } else {
                alert("Fehler beim Löschen des Geräts.");
            }
        });
}

socket.on("device_deleted", data => {
    const card = document.querySelector(`.device-card[data-id='${data.id}']`);
    if (card) card.remove();
});

/* =========================================================
   GERÄT HINZUFÜGEN MODAL
========================================================= */

// Zwischenspeicher für DB-Geräte
let dbGeraeteCache = [];

function openAddDevice(typ) {
    // Felder zurücksetzen
    document.getElementById("addName").value             = "";
    document.getElementById("addMcu").value              = "";
    document.getElementById("addStatus").value           = "aktiv";
    document.getElementById("addAkku").value             = "";
    document.getElementById("addDeviceError").innerText  = "";
    document.getElementById("addSelectedDbId").value     = "";

    document.getElementById("addDeviceTyp").value = typ;

    if (typ === "messgeraet") {
        document.getElementById("addDeviceTitle").innerText          = "Messgerät hinzufügen";
        document.getElementById("addMessgeraetFelder").style.display = "block";
        document.getElementById("addQuelleFelder").style.display     = "none";
        document.getElementById("addGesamtdosis").value = "";
    } else {
        document.getElementById("addDeviceTitle").innerText          = "Strahlungsquelle hinzufügen";
        document.getElementById("addMessgeraetFelder").style.display = "none";
        document.getElementById("addQuelleFelder").style.display     = "block";
        document.getElementById("addAlpha").value = "";
        document.getElementById("addBeta").value  = "";
        document.getElementById("addGamma").value = "";
    }

    // Immer im "neu" Modus starten
    setAddMode("neu");

    document.getElementById("addDeviceModal").style.display = "block";
}

function setAddMode(modus) {
    const isDb = modus === "db";
    const typ  = document.getElementById("addDeviceTyp").value;

    document.getElementById("toggleNeu").classList.toggle("mode-btn-active", !isDb);
    document.getElementById("toggleDb").classList.toggle("mode-btn-active",  isDb);
    document.getElementById("dbAuswahlBereich").style.display = isDb ? "block" : "none";
    document.getElementById("addSubmitBtn").innerText = isDb
        ? "Gerät zur Übung hinzufügen"
        : "Gerät erstellen";

    // Felder leeren wenn Modus wechselt
    document.getElementById("addName").value  = "";
    document.getElementById("addMcu").value   = "";
    document.getElementById("addStatus").value = "aktiv";
    document.getElementById("addAkku").value  = "";
    document.getElementById("addSelectedDbId").value = "";
    if (typ === "messgeraet") document.getElementById("addGesamtdosis").value = "";
    else {
        document.getElementById("addAlpha").value = "";
        document.getElementById("addBeta").value  = "";
        document.getElementById("addGamma").value = "";
    }

    if (isDb) {
        // DB-Geräte laden
        fetch(`/devices/ohne_uebung?typ=${typ}`)
            .then(r => r.json())
            .then(geraete => {
                dbGeraeteCache = geraete;
                const sel = document.getElementById("dbGeraetSelect");
                sel.innerHTML = '<option value="">-- Gerät wählen --</option>';
                geraete.forEach(g => {
                    const opt = document.createElement("option");
                    opt.value = g.id;
                    opt.innerText = g.name + (g.mac_adresse ? ` (${g.mac_adresse})` : "");
                    sel.appendChild(opt);
                });
                if (geraete.length === 0) {
                    document.getElementById("dbAuswahlHinweis").innerText =
                        "Keine nicht zugeordneten Geräte dieses Typs in der Datenbank.";
                } else {
                    document.getElementById("dbAuswahlHinweis").innerText =
                        "Wähle ein Gerät – die Felder werden automatisch befüllt und können angepasst werden.";
                }
            });
    }
}

function onDbGeraetSelect() {
    const id = document.getElementById("dbGeraetSelect").value;
    if (!id) return;

    const g = dbGeraeteCache.find(x => x.id == id);
    if (!g) return;

    // Felder befüllen
    document.getElementById("addSelectedDbId").value = g.id;
    document.getElementById("addName").value          = g.name        || "";
    document.getElementById("addMcu").value           = g.mac_adresse || "";
    document.getElementById("addStatus").value        = g.status      || "aktiv";
    document.getElementById("addAkku").value          = g.akku        || "";

    const typ = document.getElementById("addDeviceTyp").value;
    if (typ === "messgeraet") {
        document.getElementById("addGesamtdosis").value = g.gesamtdosis || "";
    } else {
        document.getElementById("addAlpha").value = g.staerke_alpha || "";
        document.getElementById("addBeta").value  = g.staerke_beta  || "";
        document.getElementById("addGamma").value = g.staerke_gamma || "";
    }
}

function closeAddDevice() {
    document.getElementById("addDeviceModal").style.display = "none";
}

function submitAddDevice() {
    const name      = document.getElementById("addName").value.trim();
    const typ       = document.getElementById("addDeviceTyp").value;
    const dbId      = document.getElementById("addSelectedDbId").value;
    const isDbModus = !!dbId;

    if (!name) {
        document.getElementById("addDeviceError").innerText = "Bitte einen Namen eingeben.";
        return;
    }

    const akkuInput = document.getElementById("addAkku");
    const akkuRaw   = parseFloat(akkuInput.value);
    const akkuFinal = isNaN(akkuRaw) ? 100.0 : Math.min(100, Math.max(0, akkuRaw));
    akkuInput.value = akkuFinal;

    if (isDbModus) {
        // DB-Modus: bestehendes Gerät aktualisieren und zur Übung hinzufügen
        const payload = {
            name:        name,
            mac_adresse: document.getElementById("addMcu").value.trim() || null,
            status:      document.getElementById("addStatus").value,
            akku:        akkuFinal,
        };
        if (typ === "messgeraet") {
            payload.gesamtdosis = parseFloat(document.getElementById("addGesamtdosis").value) || 0.0;
        } else {
            payload.staerke_alpha = parseFloat(document.getElementById("addAlpha").value) || 0.0;
            payload.staerke_beta  = parseFloat(document.getElementById("addBeta").value)  || 0.0;
            payload.staerke_gamma = parseFloat(document.getElementById("addGamma").value) || 0.0;
        }

        // Erst Daten aktualisieren, dann zur Übung hinzufügen
        fetch(`/device/${dbId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(r => {
            if (!r.ok) return Promise.reject();
            const targetId = addDeviceUebungKontext || null;
            const url = targetId
                ? `/device/${dbId}/add_to_specific_uebung/${targetId}`
                : `/device/${dbId}/add_to_uebung`;
            return fetch(url, { method: "POST" });
        })
        .then(r => {
            if (r.ok) {
                closeAddDevice();
                // Der Server sendet "new_device" via Socket – Karte erscheint automatisch
                return;
            }
            document.getElementById("addDeviceError").innerText = "Fehler beim Hinzufügen zur Übung.";
        })
        .catch(() => {
            document.getElementById("addDeviceError").innerText = "Verbindungsfehler.";
        });

    } else {
        // Neu-Modus: neues Gerät anlegen
        const payload = {
            name:        name,
            typ:         typ,
            mac_adresse: document.getElementById("addMcu").value.trim() || null,
            status:      document.getElementById("addStatus").value,
            akku:        akkuFinal,
        };
        if (typ === "messgeraet") {
            payload.gesamtdosis = parseFloat(document.getElementById("addGesamtdosis").value) || 0.0;
        } else {
            payload.staerke_alpha = parseFloat(document.getElementById("addAlpha").value) || 0.0;
            payload.staerke_beta  = parseFloat(document.getElementById("addBeta").value)  || 0.0;
            payload.staerke_gamma = parseFloat(document.getElementById("addGamma").value) || 0.0;
        }

        fetch("/add_device", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).then(r => {
            if (r.ok) {
                closeAddDevice();
            } else {
                r.text().then(t => {
                    document.getElementById("addDeviceError").innerText = "Fehler: " + t;
                });
            }
        }).catch(() => {
            document.getElementById("addDeviceError").innerText = "Verbindungsfehler.";
        });
    }
}

/* =========================================================
   LOGIN
========================================================= */

function openLogin() {
    document.getElementById("loginModal").style.display = "block";
}

function closeLogin() {
    document.getElementById("loginModal").style.display = "none";
}

/* =========================================================
   CHART
========================================================= */

const ctx = document.getElementById("chartCPS")?.getContext("2d");
let chart;

if (ctx) {
    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "Zählrate (Impulse/s)",
                data: [],
                borderColor: "rgba(0, 87, 184, 1)",
                backgroundColor: "rgba(0, 87, 184, 0.2)",
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { title: { display: true, text: "Zeit" } },
                y: { beginAtZero: true, title: { display: true, text: "Impulse/s" } }
            }
        }
    });
}

function updateChart(value) {
    if (!chart) return;
    const time = new Date().toLocaleTimeString();
    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update();
}

/* =========================================================
   INITIALISIERUNG
========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    document.querySelectorAll(".device-card:not(.add-device-card)").forEach(card => {
        const currentEl = card.querySelector(".current-dose");
        const totalEl   = card.querySelector(".total-dose");
        if (currentEl) setDoseColor(currentEl, parseFloat(currentEl.innerText));
        if (totalEl)   setDoseColor(totalEl,   parseFloat(totalEl.innerText));
        bindCardClick(card);
    });

    document.addEventListener("click", e => {
        const loginModal     = document.getElementById("loginModal");
        const detailModal    = document.getElementById("detailModal");
        const addDeviceModal = document.getElementById("addDeviceModal");
        if (loginModal     && e.target === loginModal)     closeLogin();
        if (detailModal    && e.target === detailModal)    closeDetail();
        if (addDeviceModal && e.target === addDeviceModal) closeAddDevice();
    });

    document.addEventListener("keydown", e => {
        if (e.key === "Escape") { closeLogin(); closeDetail(); closeAddDevice(); }
    });

    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        loginForm.addEventListener("submit", function (e) {
            e.preventDefault();
            fetch("/login", { method: "POST", body: new FormData(this) })
                .then(r => {
                    if (r.status === 200) location.reload();
                    else document.getElementById("loginError").innerText = "Login fehlgeschlagen";
                })
                .catch(err => console.error("Fehler:", err));
        });
    }
});

/* =========================================================
   TAB NAVIGATION
========================================================= */

function switchTab(tab) {
    ["dashboard", "uebungen", "live"].forEach(t => {
        document.getElementById("page-" + t).style.display = t === tab ? "block" : "none";
        const link = document.getElementById("tab-" + t);
        if (link) link.classList.toggle("tab-active", t === tab);
    });
    if (tab === "uebungen") ladeUebungen();
}

/* =========================================================
   ÜBUNGEN LADEN & ANZEIGEN
========================================================= */

let uebungenCache = [];
let aktiveUebungDetailId = null;

function ladeUebungen() {
    fetch("/uebungen")
        .then(r => r.json())
        .then(data => {
            uebungenCache = data;
            renderUebungenListe(data);
        });
}

function renderUebungenListe(uebungen) {
    const container = document.getElementById("uebungen-liste");
    if (!uebungen.length) {
        container.innerHTML = '<p class="uebungen-loading">Keine Übungen vorhanden.</p>';
        return;
    }

    container.innerHTML = uebungen.map(u => {
        const statusClass = u.status || "vorbereitung";
        const startStr = u.start_zeit
            ? new Date(u.start_zeit).toLocaleString("de-DE", {day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})
            : "—";
        const endStr = u.end_zeit
            ? new Date(u.end_zeit).toLocaleString("de-DE", {day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})
            : u.status === "aktiv" ? "läuft…" : "—";

        return `
        <div class="uebung-card" onclick="openUebungDetail(${u.id})">
            <div class="uebung-card-status ${statusClass}"></div>
            <div class="uebung-card-body">
                <div class="uebung-card-name">${u.name}</div>
                <div class="uebung-card-meta">Start: ${startStr} &nbsp;|&nbsp; Ende: ${endStr}</div>
            </div>
            <div class="uebung-card-counts">
                <span class="uebung-count-badge">📡 ${u.anzahl_messgeraete} Messgeräte</span>
                <span class="uebung-count-badge">☢ ${u.anzahl_quellen} Quellen</span>
            </div>
            <span class="uebung-status-badge ${statusClass}">${statusClass}</span>
        </div>`;
    }).join("");
}

/* =========================================================
   ÜBUNG DETAIL
========================================================= */

function openUebungDetail(id) {
    fetch(`/uebung/${id}`)
        .then(r => r.json())
        .then(u => {
            aktiveUebungDetailId = id;
            const readonly = u.status === "abgeschlossen";

            document.getElementById("udTitel").innerText = u.name;

            const badge = document.getElementById("udStatusBadge");
            badge.innerText = u.status;
            badge.className = "uebung-status-badge " + u.status;

            document.getElementById("udStart").innerText = u.start_zeit
                ? new Date(u.start_zeit).toLocaleString("de-DE") : "—";
            document.getElementById("udEnde").innerText = u.end_zeit
                ? new Date(u.end_zeit).toLocaleString("de-DE")
                : u.status === "aktiv" ? "läuft…" : "—";

            const messgeraete = u.geraete.filter(g => g.typ === "messgeraet");
            const quellen     = u.geraete.filter(g => g.typ === "quelle");

            document.getElementById("udAnzahlMessgeraete").innerText = messgeraete.length;
            document.getElementById("udAnzahlQuellen").innerText     = quellen.length;

            renderUdGeraeteListe("udMessgeraeteListe", messgeraete, readonly);
            renderUdGeraeteListe("udQuellenListe",     quellen,     readonly);

            // Readonly-Banner
            const banner = document.getElementById("udReadonlyBanner");
            if (banner) banner.style.display = readonly ? "flex" : "none";

            // Hinzufügen-Buttons
            const btnM = document.getElementById("udBtnAddMessgeraet");
            const btnQ = document.getElementById("udBtnAddQuelle");
            if (btnM) btnM.style.display = readonly ? "none" : "";
            if (btnQ) btnQ.style.display = readonly ? "none" : "";

            // Gefahrenzone
            const gz = document.getElementById("udGefahrenzone");
            if (gz) gz.style.display = readonly ? "none" : "";

            // Aktions-Buttons
            const aktionenDiv = document.getElementById("udAktionenHeader");
            aktionenDiv.innerHTML = "";

            if (readonly) {
                // Nur reaktivieren erlaubt
                const btnAktiv = document.createElement("button");
                btnAktiv.className = "btn btn-login";
                btnAktiv.innerText = "▶ Reaktivieren";
                btnAktiv.onclick   = () => uebungAktivieren(id);
                aktionenDiv.appendChild(btnAktiv);
            } else if (u.status === "vorbereitung") {
                const btnAktiv = document.createElement("button");
                btnAktiv.className = "btn btn-login";
                btnAktiv.innerText = "▶ Aktivieren";
                btnAktiv.onclick   = () => uebungAktivieren(id);
                aktionenDiv.appendChild(btnAktiv);
            } else if (u.status === "aktiv") {
                const btnStop = document.createElement("button");
                btnStop.className = "btn btn-logout";
                btnStop.innerText = "■ Beenden";
                btnStop.onclick   = () => uebungBeenden(id);
                aktionenDiv.appendChild(btnStop);
            }

            document.getElementById("uebungDetailModal").style.display = "block";
        });
}

function renderUdGeraeteListe(containerId, geraete, readonly = false) {
    const el = document.getElementById(containerId);
    if (!geraete.length) {
        el.innerHTML = '<span class="ud-empty">Keine Geräte zugeordnet</span>';
        return;
    }
    el.innerHTML = geraete.map(g => `
        <div class="ud-geraet-row" id="ud-geraet-${g.id}">
            <span class="ud-geraet-name">${g.name}</span>
            <span class="ud-geraet-mac">${g.mac_adresse || "—"}</span>
            <span class="ud-geraet-status ${g.status || 'inaktiv'}">${g.status || "—"}</span>
            ${readonly ? "" : `<button class="ud-geraet-remove" title="Aus Übung entfernen"
                    onclick="udGeraetEntfernen(${g.id}, event)">✕</button>`}
        </div>`).join("");
}

function udGeraetEntfernen(geraetId, event) {
    event.stopPropagation();
    if (!confirm("Gerät aus der Übung entfernen?")) return;
    fetch(`/device/${geraetId}/remove_from_uebung`, { method: "POST" })
        .then(r => {
            if (r.ok) {
                const row = document.getElementById("ud-geraet-" + geraetId);
                if (row) row.remove();
                openUebungDetail(aktiveUebungDetailId); // neu laden für Zähler
            }
        });
}

function closeUebungDetail() {
    document.getElementById("uebungDetailModal").style.display = "none";
    aktiveUebungDetailId = null;
    ladeUebungen(); // Liste aktualisieren
}

/* =========================================================
   ÜBUNG AKTIVIEREN / BEENDEN
========================================================= */

function uebungAktivieren(id) {
    fetch(`/uebung/${id}/aktivieren`, { method: "POST" })
        .then(r => {
            if (r.ok) {
                closeUebungDetail();
                ladeUebungen();
            }
        });
}

function uebungBeenden(id) {
    if (!confirm("Übung als abgeschlossen markieren?")) return;
    fetch(`/uebung/${id}/beenden`, { method: "POST" })
        .then(r => {
            if (r.ok) {
                closeUebungDetail();
                ladeUebungen();
            }
        });
}

function deleteUebung() {
    if (!aktiveUebungDetailId) return;
    const name = document.getElementById("udTitel").innerText;
    if (!confirm(`Übung „${name}" dauerhaft löschen?\nAlle Gerätezuordnungen werden aufgehoben.`)) return;
    fetch(`/uebung/${aktiveUebungDetailId}`, { method: "DELETE" })
        .then(r => {
            if (r.ok) {
                closeUebungDetail();
                ladeUebungen();
            }
        });
}

/* =========================================================
   NEUE ÜBUNG
========================================================= */

function openNeueUebung() {
    document.getElementById("neueUebungName").value   = "";
    document.getElementById("neueUebungStatus").value = "vorbereitung";
    document.getElementById("neueUebungStart").value  = "";
    document.getElementById("neueUebungError").innerText = "";
    document.getElementById("neueUebungModal").style.display = "block";
}

function closeNeueUebung() {
    document.getElementById("neueUebungModal").style.display = "none";
}

function submitNeueUebung() {
    const name   = document.getElementById("neueUebungName").value.trim();
    const status = document.getElementById("neueUebungStatus").value;
    const start  = document.getElementById("neueUebungStart").value;

    if (!name) {
        document.getElementById("neueUebungError").innerText = "Bitte einen Namen eingeben.";
        return;
    }

    fetch("/uebungen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, status, start_zeit: start || null })
    }).then(r => {
        if (r.ok) {
            closeNeueUebung();
            ladeUebungen();
        } else {
            r.text().then(t => document.getElementById("neueUebungError").innerText = "Fehler: " + t);
        }
    });
}

/* =========================================================
   GERÄT ZU ÜBUNG HINZUFÜGEN (aus Übungs-Detail)
========================================================= */

function openAddDeviceForUebung(typ) {
    // addDeviceModal nutzen, aber mit uebung-kontext
    addDeviceUebungKontext = aktiveUebungDetailId;
    openAddDevice(typ);
}

// Überschreibe add_to_uebung um spezifische Übung zu nutzen
let addDeviceUebungKontext = null;

// Übungs-Detail nach new_device aktualisieren wird im originalen Handler erledigt
// (addDeviceUebungKontext wird dort geprüft)

// Close-Handler erweitern
document.addEventListener("DOMContentLoaded", function() {
    document.addEventListener("click", e => {
        const neueUebungModal  = document.getElementById("neueUebungModal");
        const uebungDetailModal = document.getElementById("uebungDetailModal");
        if (neueUebungModal   && e.target === neueUebungModal)   closeNeueUebung();
        if (uebungDetailModal && e.target === uebungDetailModal) closeUebungDetail();
    });
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") { closeNeueUebung(); closeUebungDetail(); }
    });
});

/* =========================================================
   LIVE-MESSUNG / DIAGRAMME
========================================================= */

// Farbpalette für mehrere Geräte
const CHART_COLORS = [
    "#3498db","#e74c3c","#2ecc71","#f39c12","#9b59b6",
    "#1abc9c","#e67e22","#34495e","#e91e63","#00bcd4"
];

let chartCpsVerlauf  = null;
let chartDosisVerlauf = null;
let chartCpsBar      = null;
let chartDosisBar    = null;

function initCharts() {
    const defaults = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } }
    };

    chartCpsVerlauf = new Chart(document.getElementById("chartCpsVerlauf"), {
        type: "line",
        data: { labels: [], datasets: [] },
        options: { ...defaults,
            scales: {
                x: { ticks: { maxTicksLimit: 10, font: { size: 10 } } },
                y: { beginAtZero: true, title: { display: true, text: "mSv/h", font: { size: 11 } } }
            }
        }
    });

    chartDosisVerlauf = new Chart(document.getElementById("chartDosisVerlauf"), {
        type: "line",
        data: { labels: [], datasets: [] },
        options: { ...defaults,
            scales: {
                x: { ticks: { maxTicksLimit: 10, font: { size: 10 } } },
                y: { beginAtZero: true, title: { display: true, text: "mSv", font: { size: 11 } } }
            }
        }
    });

    chartCpsBar = new Chart(document.getElementById("chartCpsBar"), {
        type: "bar",
        data: { labels: [], datasets: [{ label: "Aktuelle Dosisrate (mSv/h)", data: [], backgroundColor: [] }] },
        options: { ...defaults,
            plugins: { ...defaults.plugins, legend: { display: false } },
            scales: {
                x: { ticks: { font: { size: 10 } } },
                y: { beginAtZero: true, title: { display: true, text: "mSv/h", font: { size: 11 } } }
            }
        }
    });

    chartDosisBar = new Chart(document.getElementById("chartDosisBar"), {
        type: "bar",
        data: { labels: [], datasets: [{ label: "Gesamtdosis (mSv)", data: [], backgroundColor: [] }] },
        options: { ...defaults,
            plugins: { ...defaults.plugins, legend: { display: false } },
            scales: {
                x: { ticks: { font: { size: 10 } } },
                y: { beginAtZero: true, title: { display: true, text: "mSv", font: { size: 11 } } }
            }
        }
    });
}

function ladeLiveUebungen() {
    fetch("/uebungen/liste")
        .then(r => r.json())
        .then(uebungen => {
            const sel = document.getElementById("liveUebungSelect");
            sel.innerHTML = "";

            // Aktive zuerst
            const sortiert = [...uebungen].sort((a, b) => {
                const ord = { aktiv: 0, vorbereitung: 1, abgeschlossen: 2 };
                return (ord[a.status] ?? 3) - (ord[b.status] ?? 3);
            });

            sortiert.forEach(u => {
                const opt = document.createElement("option");
                opt.value = u.id;
                const icon = u.status === "aktiv" ? "●" : u.status === "vorbereitung" ? "◐" : "○";
                opt.innerText = `${icon} ${u.name}`;
                sel.appendChild(opt);
            });

            onLiveUebungChange();
        });
}

function onLiveUebungChange() {
    const uebungId = document.getElementById("liveUebungSelect").value;
    if (!uebungId) return;

    // Geräte-Dropdown befüllen
    fetch(`/uebung/${uebungId}`)
        .then(r => r.json())
        .then(u => {
            const sel = document.getElementById("liveGeraetSelect");
            sel.innerHTML = '<option value="">Alle Messgeräte</option>';
            u.geraete
                .filter(g => g.typ === "messgeraet")
                .forEach(g => {
                    const opt = document.createElement("option");
                    opt.value = g.id;
                    opt.innerText = g.name;
                    sel.appendChild(opt);
                });
            ladeCharts();
        });
}

function ladeCharts() {
    const uebungId = document.getElementById("liveUebungSelect").value;
    const geraetId = document.getElementById("liveGeraetSelect").value;
    const limit    = document.getElementById("liveLimitSelect").value;

    if (!uebungId) return;

    let url = `/measurements/history?uebung_id=${uebungId}&limit=${limit}`;
    if (geraetId) url += `&geraet_id=${geraetId}`;

    fetch(url)
        .then(r => r.json())
        .then(daten => {
            const hint = document.getElementById("liveEmptyHint");
            if (!daten.length) {
                hint.style.display = "block";
                document.querySelector(".live-charts-grid").style.display = "none";
                document.getElementById("liveStatCards").innerHTML = "";
                return;
            }
            hint.style.display = "none";
            document.querySelector(".live-charts-grid").style.display = "grid";

            // Daten nach Gerät gruppieren
            const geraeteMap = {};
            daten.forEach(m => {
                if (!geraeteMap[m.geraet_id]) {
                    geraeteMap[m.geraet_id] = { name: m.geraet_name, cps: [], dosis: [], timestamps: [] };
                }
                geraeteMap[m.geraet_id].cps.push(m.cps);
                geraeteMap[m.geraet_id].dosis.push(m.dosis);
                geraeteMap[m.geraet_id].timestamps.push(
                    new Date(m.timestamp).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
                );
            });

            const geraeteIds  = Object.keys(geraeteMap);
            const geraeteList = geraeteIds.map((id, i) => ({ id, ...geraeteMap[id], color: CHART_COLORS[i % CHART_COLORS.length] }));

            // Gemeinsame Zeitachse (alle Timestamps sammeln und deduplizieren)
            const alleTimestamps = [...new Set(daten.map(m =>
                new Date(m.timestamp).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
            ))];

            // Verlaufs-Diagramme (Linien)
            updateVerlaufChart(chartCpsVerlauf,   geraeteList, "cps",   alleTimestamps);
            updateVerlaufChart(chartDosisVerlauf, geraeteList, "dosis", alleTimestamps);

            // Untertitel
            document.getElementById("liveCpsSubtitle").innerText  = `${daten.length} Messpunkte`;
            document.getElementById("liveDosisSubtitle").innerText = `${geraeteList.length} Gerät${geraeteList.length !== 1 ? "e" : ""}`;

            // Balken-Diagramme (letzter Wert je Gerät)
            const barLabels = geraeteList.map(g => kuerze(g.name, 14));
            const barColors = geraeteList.map(g => g.color);

            chartCpsBar.data.labels                    = barLabels;
            chartCpsBar.data.datasets[0].data           = geraeteList.map(g => g.cps.at(-1)   ?? 0);
            chartCpsBar.data.datasets[0].backgroundColor = barColors;
            chartCpsBar.update();

            chartDosisBar.data.labels                    = barLabels;
            chartDosisBar.data.datasets[0].data           = geraeteList.map(g => g.dosis.at(-1) ?? 0);
            chartDosisBar.data.datasets[0].backgroundColor = barColors;
            chartDosisBar.update();

            // Stat-Kacheln
            renderStatCards(geraeteList);
        });
}

function updateVerlaufChart(chart, geraeteList, feld, labels) {
    chart.data.labels   = labels;
    chart.data.datasets = geraeteList.map(g => ({
        label:           g.name,
        data:            g[feld],
        borderColor:     g.color,
        backgroundColor: g.color + "22",
        borderWidth:     2,
        pointRadius:     geraeteList[0][feld].length > 60 ? 0 : 3,
        tension:         0.3,
        fill:            false
    }));
    chart.update();
}

function renderStatCards(geraeteList) {
    const container = document.getElementById("liveStatCards");

    // Gesamt-Statistiken
    const alleDosiswerte = geraeteList.flatMap(g => g.dosis);
    const alleCpswerte   = geraeteList.flatMap(g => g.cps);
    const maxDosis  = Math.max(...alleDosiswerte).toFixed(1);
    const maxCps    = Math.max(...alleCpswerte).toFixed(2);
    const avgDosis  = (alleDosiswerte.reduce((a, b) => a + b, 0) / alleDosiswerte.length).toFixed(1);

    container.innerHTML = `
        <div class="live-stat-card">
            <span class="live-stat-label">Geräte</span>
            <span class="live-stat-value">${geraeteList.length}</span>
            <span class="live-stat-sub">Messgeräte mit Daten</span>
        </div>
        <div class="live-stat-card">
            <span class="live-stat-label">Max. Dosisrate</span>
            <span class="live-stat-value">${maxCps}</span>
            <span class="live-stat-sub">mSv/h (Spitzenwert)</span>
        </div>
        <div class="live-stat-card">
            <span class="live-stat-label">Max. Gesamtdosis</span>
            <span class="live-stat-value">${maxDosis}</span>
            <span class="live-stat-sub">mSv (höchstes Gerät)</span>
        </div>
        <div class="live-stat-card">
            <span class="live-stat-label">Ø Gesamtdosis</span>
            <span class="live-stat-value">${avgDosis}</span>
            <span class="live-stat-sub">mSv (alle Geräte)</span>
        </div>
        ${geraeteList.map(g => `
        <div class="live-stat-card">
            <span class="live-stat-label" style="color:${g.color}">${kuerze(g.name, 18)}</span>
            <span class="live-stat-value">${(g.cps.at(-1) ?? 0).toFixed(2)}</span>
            <span class="live-stat-sub">mSv/h aktuell · ${(g.dosis.at(-1) ?? 0).toFixed(1)} mSv gesamt</span>
        </div>`).join("")}
    `;
}

function kuerze(str, max) {
    return str.length > max ? str.slice(0, max - 1) + "…" : str;
}

// Tab-Switch-Hook: Charts beim ersten Öffnen initialisieren
const _origSwitchTab = switchTab;
function switchTab(tab) {
    _origSwitchTab(tab);
    if (tab === "live") {
        if (!chartCpsVerlauf) initCharts();
        ladeLiveUebungen();
    }
}