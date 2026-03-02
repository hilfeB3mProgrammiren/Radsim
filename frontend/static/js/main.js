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

    // Neue Karte vor der Add-Karte einfügen
    const addCard = container.querySelector(".add-device-card");

    const card = document.createElement("div");
    card.classList.add("device-card");
    card.dataset.id     = device.id;
    card.dataset.typ    = device.typ;
    card.dataset.name   = device.name;
    card.dataset.mcu    = device.mcu_adresse || "";
    card.dataset.status = device.status || "";
    card.dataset.akku   = device.akku || "";

    const icon = device.typ === "messgeraet" ? "geiger_icon.png" : "quelle_icon.png";

    if (device.typ === "messgeraet") {
        card.dataset.gesamtdosis = device.gesamtdosis || 0;
        card.innerHTML = `
            <div class="device-icon"><img src="/static/img/${icon}" alt="${device.name}"></div>
            <div class="device-name">${device.name}</div>
            <div class="device-doses">
                <div class="current-dose">— mSv/h</div>
                <div class="total-dose">${parseFloat(device.gesamtdosis || 0).toFixed(2)} mSv</div>
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

    // Vor der Add-Karte einfügen, falls vorhanden
    if (addCard) {
        container.insertBefore(card, addCard);
    } else {
        container.appendChild(card);
    }
    bindCardClick(card);
});

/* =========================================================
   ÜBUNG – Live Badge
========================================================= */

socket.on("uebung_gestartet", data => {
    const badge = document.querySelector(".uebung-badge");
    if (badge) {
        badge.classList.remove("inaktiv");
        badge.classList.add("aktiv");
        badge.innerText = "● " + data.name;
    }
});

socket.on("uebung_gestoppt", () => {
    const badge = document.querySelector(".uebung-badge");
    if (badge) {
        badge.classList.remove("aktiv");
        badge.classList.add("inaktiv");
        badge.innerText = "Keine aktive Übung";
    }
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

    fetch(`/device/${activeDeviceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name:        getName?.value,
            mcu_adresse: getMcu?.value,
            status:      getStatus?.value,
            akku:        parseFloat(getAkku?.value) || null
        })
    }).then(r => { if (r.ok) closeDetail(); });
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
   GERÄT HINZUFÜGEN MODAL
========================================================= */

function openAddDevice(typ) {
    // Felder zurücksetzen
    document.getElementById("addName").value        = "";
    document.getElementById("addMcu").value         = "";
    document.getElementById("addStatus").value      = "aktiv";
    document.getElementById("addAkku").value        = "";
    document.getElementById("addDeviceError").innerText = "";

    document.getElementById("addDeviceTyp").value = typ;

    if (typ === "messgeraet") {
        document.getElementById("addDeviceTitle").innerText     = "Messgerät hinzufügen";
        document.getElementById("addMessgeraetFelder").style.display = "block";
        document.getElementById("addQuelleFelder").style.display     = "none";
        document.getElementById("addGesamtdosis").value = "";
    } else {
        document.getElementById("addDeviceTitle").innerText     = "Strahlungsquelle hinzufügen";
        document.getElementById("addMessgeraetFelder").style.display = "none";
        document.getElementById("addQuelleFelder").style.display     = "block";
        document.getElementById("addAlpha").value = "";
        document.getElementById("addBeta").value  = "";
        document.getElementById("addGamma").value = "";
    }

    document.getElementById("addDeviceModal").style.display = "block";
}

function closeAddDevice() {
    document.getElementById("addDeviceModal").style.display = "none";
}

function submitAddDevice() {
    const name = document.getElementById("addName").value.trim();
    const typ  = document.getElementById("addDeviceTyp").value;

    if (!name) {
        document.getElementById("addDeviceError").innerText = "Bitte einen Namen eingeben.";
        return;
    }

    const payload = {
        name:        name,
        typ:         typ,
        mcu_adresse: document.getElementById("addMcu").value.trim() || null,
        status:      document.getElementById("addStatus").value,
        akku:        parseFloat(document.getElementById("addAkku").value) || 100.0,
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
            // Das socket-Event "new_device" übernimmt das Rendern der neuen Karte
        } else {
            r.text().then(t => {
                document.getElementById("addDeviceError").innerText = "Fehler: " + t;
            });
        }
    }).catch(() => {
        document.getElementById("addDeviceError").innerText = "Verbindungsfehler.";
    });
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