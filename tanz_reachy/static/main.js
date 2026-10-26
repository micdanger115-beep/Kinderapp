const STATE_TEXT = {
    warten: "Reachy wartet – Antenne antippen zum Tanzen",
    lied: "Reachy tanzt",
    gute_nacht: "Gute-Nacht-Lied",
    schlafen: "Reachy schläft 😴",
};

const $ = (id) => document.getElementById(id);
let songsRendered = false;
let editing = false; // Regler nicht überschreiben, während jemand daran zieht
let pinSet = true;
let pinWrong = false;
let pinResetAllowed = false; // kurz nach dem App-Start darf ein vergessener PIN ersetzt werden

function storedPin() {
    try { return localStorage.getItem("eltern_pin") || ""; } catch (e) { return ""; }
}
function storePin(pin) {
    try { localStorage.setItem("eltern_pin", pin); } catch (e) { /* nur bis zum Neuladen */ }
    sessionPin = pin;
}
let sessionPin = storedPin();

async function post(path, body) {
    try {
        const res = await fetch(path, {
            method: "POST",
            // Der PIN-Header ist Pflicht, auch als Schutz vor fremden Webseiten.
            headers: { "Content-Type": "application/json", "X-Eltern-PIN": sessionPin },
            body: JSON.stringify(body || {}),
        });
        if (res.status === 401) pinWrong = true;
        refresh();
        return res;
    } catch (e) {
        $("status").textContent = "Keine Verbindung zu Reachy";
    }
}

function pinMustBeCreated() {
    return !pinSet || (pinWrong && pinResetAllowed);
}

function renderPinBox() {
    const show = !pinSet || pinWrong || !sessionPin;
    $("pin-box").hidden = !show;
    if (pinMustBeCreated()) {
        $("pin-title").textContent = pinSet ? "Neuen Eltern-PIN festlegen" : "Eltern-PIN festlegen";
        $("pin-hint").textContent = "Damit nur ihr Reachy über diese Seite steuern könnt. Mindestens 4 Zeichen.";
    } else {
        $("pin-title").textContent = "Eltern-PIN eingeben";
        $("pin-hint").textContent = pinWrong
            ? "PIN falsch oder zu viele Versuche. PIN vergessen? App im Reachy-Dashboard neu starten, dann kann 5 Minuten lang ein neuer PIN festgelegt werden."
            : "Bitte den Eltern-PIN eingeben.";
    }
}

$("pin-btn").addEventListener("click", async () => {
    const pin = $("pin-input").value.trim();
    if (!pin) return;
    if (pinMustBeCreated()) {
        const res = await post("/api/pin", { new_pin: pin });
        if (!res || !res.ok) {
            $("pin-hint").textContent = "PIN braucht mindestens 4 Zeichen.";
            return;
        }
    }
    storePin(pin);
    pinWrong = false;
    $("pin-input").value = "";
    refresh();
});

function renderSongs(songs) {
    const box = $("songs");
    for (const song of songs) {
        const b = document.createElement("button");
        b.className = "song";
        b.dataset.id = song.id;
        b.innerHTML = `<span class="emoji">${song.emoji}</span><span>${song.title}</span>`;
        b.addEventListener("click", () => post("/api/play", { song_id: song.id }));
        box.appendChild(b);
    }
    songsRendered = true;
}

function formatMinutes(s) {
    const m = Math.floor(s / 60);
    const sec = String(s % 60).padStart(2, "0");
    return `${m}:${sec}`;
}

async function refresh() {
    let st;
    try {
        st = await (await fetch("/api/status")).json();
    } catch (e) {
        $("status").textContent = "Keine Verbindung zu Reachy";
        return;
    }
    if (!songsRendered) renderSongs(st.songs);
    pinSet = st.pin_set;
    pinResetAllowed = st.pin_reset_allowed;
    renderPinBox();

    let text = STATE_TEXT[st.state] || st.state;
    if (st.song) text = `${st.song.emoji} ${st.song.title}`;
    if (st.session_remaining_s > 0) text += ` · noch ${formatMinutes(st.session_remaining_s)}`;
    $("status").textContent = text;
    $("progress-bar").style.width = `${Math.round(st.song_progress * 100)}%`;

    document.querySelectorAll(".song").forEach((b) => {
        b.classList.toggle("active", st.song && b.dataset.id === st.song.id);
    });
    const asleep = st.state === "schlafen";
    $("play-btn").disabled = asleep;
    $("sleep-btn").disabled = asleep || st.state === "gute_nacht";
    $("wake-btn").disabled = !asleep;
    $("stop-btn").disabled = !(st.state === "lied" || st.state === "gute_nacht");
    $("still-btn").disabled = asleep;

    const sysVol = st.system_volume;
    $("volume-warning").hidden = !(sysVol > st.system_volume_warn);
    $("volume-warning").textContent = `Die Grundlautstärke von Reachy steht auf ${sysVol} %. `
        + `Für Kinderohren bitte im Reachy-Dashboard auf höchstens ${st.system_volume_warn} % stellen.`;

    if (!editing) {
        const vol = Math.round(st.settings.volume * 100);
        $("volume").max = Math.round(st.max_volume * 100);
        $("volume").value = vol;
        $("volume-label").textContent = `${vol} %`;
        $("minutes").value = st.settings.session_minutes;
        $("minutes-label").textContent = `${st.settings.session_minutes} Min.`;
        $("antenna-buttons").checked = st.settings.antenna_buttons;
    }
}

$("play-btn").addEventListener("click", () => post("/api/play", {}));
$("stop-btn").addEventListener("click", () => post("/api/stop"));
$("still-btn").addEventListener("click", () => post("/api/still"));
$("sleep-btn").addEventListener("click", () => post("/api/sleep"));
$("wake-btn").addEventListener("click", () => post("/api/wake"));

for (const id of ["volume", "minutes"]) {
    const el = $(id);
    el.addEventListener("input", () => {
        editing = true;
        if (id === "volume") $("volume-label").textContent = `${el.value} %`;
        else $("minutes-label").textContent = `${el.value} Min.`;
    });
    el.addEventListener("change", () => {
        editing = false;
        const body = id === "volume"
            ? { volume: Number(el.value) / 100 }
            : { session_minutes: Number(el.value) };
        post("/api/settings", body);
    });
}
$("antenna-buttons").addEventListener("change", (e) => {
    post("/api/settings", { antenna_buttons: e.target.checked });
});

refresh();
setInterval(refresh, 1000);
