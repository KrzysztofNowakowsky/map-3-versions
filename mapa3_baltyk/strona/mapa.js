// Mapa 3: pasek czasu na mapie (suwak + animacja) i porównanie dwóch dat (belka przesuwana po mapie).
// Korzysta z globalnych z index.html: mapa, sceny, pokaz(); startuje po zdarzeniu 'sceny-gotowe'.

(() => {
const KROK_MS = 1300;          // czas jednej klatki animacji

function el(tag, klasa, html) {
  const e = document.createElement(tag);
  if (klasa) e.className = klasa;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function opisDaty(s) {
  const [r, m, d] = s.data.split('-');
  return { data: `${d}.${m}.${r}`, zakwit: s.zakwit_pct === null ? 'brak danych' : `${s.zakwit_pct}%` };
}

function warstwaKafelkow(data, typ, opcje = {}) {
  return L.tileLayer(`kafelki/${typ}/${data}/{z}/{x}/{y}.png`, {
    minZoom: 7, minNativeZoom: 9, maxNativeZoom: 11, maxZoom: 16, opacity: typ === 'mci' ? 0.9 : 1,
    bounds: window.zasiegKafelkow, ...opcje
  });
}

// ---------- 1. Pasek czasu + animacja ----------
function pasekCzasu() {
  const wybor = document.querySelector('#data');
  const pasek = el('div', 'os-czasu');
  const graj = el('button', 'os-graj', '▶');
  graj.title = 'Animacja sezonu (spacja)';
  const suwak = el('input', 'os-suwak');
  Object.assign(suwak, { type: 'range', min: 0, max: sceny.length - 1, step: 1, value: 0 });
  const etykieta = el('div', 'os-etykieta');
  const znaczniki = el('div', 'os-znaczniki');
  sceny.forEach(s => {
    const z = el('span');
    // wysokość kreski = % zakwitu, żeby na osi było widać szczyt
    z.style.height = `${6 + Math.min(s.zakwit_pct || 0, 70) * 0.35}px`;
    z.title = `${opisDaty(s).data}: ${opisDaty(s).zakwit}`;
    znaczniki.append(z);
  });
  const srodek = el('div', 'os-srodek');
  srodek.append(znaczniki, suwak);
  pasek.append(graj, srodek, etykieta);

  const kontrolka = L.control({ position: 'bottomleft' });
  kontrolka.onAdd = () => {
    L.DomEvent.disableClickPropagation(pasek);
    L.DomEvent.disableScrollPropagation(pasek);
    return pasek;
  };
  kontrolka.addTo(mapa);
  const dopasuj = () => { pasek.style.width = `${Math.min(680, mapa.getSize().x - 28)}px`; };
  dopasuj();
  mapa.on('resize', dopasuj);

  function odswiez() {
    const i = sceny.findIndex(s => s.data === wybor.value);
    suwak.value = i;
    const o = opisDaty(sceny[i]);
    etykieta.innerHTML = `<b>${o.data}</b><span>zakwit ${o.zakwit}</span>`;
    [...znaczniki.children].forEach((z, j) => z.classList.toggle('aktywny', j === i));
  }

  function ustaw(i) {
    wybor.value = sceny[(i + sceny.length) % sceny.length].data;
    pokaz();
    odswiez();
  }

  let timer = null;
  function stop() { clearInterval(timer); timer = null; graj.textContent = '▶'; }
  graj.addEventListener('click', () => {
    if (timer) return stop();
    graj.textContent = '⏸';
    ustaw(+suwak.value + 1);
    timer = setInterval(() => ustaw(+suwak.value + 1), KROK_MS);
  });
  suwak.addEventListener('input', () => { stop(); ustaw(+suwak.value); });
  wybor.addEventListener('change', () => { stop(); odswiez(); });
  document.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea')) return;
    if (e.key === 'ArrowRight') { stop(); ustaw(+suwak.value + 1); }
    if (e.key === 'ArrowLeft') { stop(); ustaw(+suwak.value - 1); }
    if (e.key === ' ') { e.preventDefault(); graj.click(); }
  });
  odswiez();
}

// ---------- 2. Porównanie dwóch dat ----------
function porownanie() {
  const pane = mapa.createPane('porownanie');
  pane.style.zIndex = 450;                        // nad warstwą główną (tilePane = 200)
  let prawa = null, x = 0.5, wlaczone = false;

  const belka = el('div', 'belka', '<span>⇆</span>');
  const podpisL = el('div', 'podpis-porownania lewy');
  const podpisP = el('div', 'podpis-porownania prawy');
  mapa.getContainer().append(belka, podpisL, podpisP);

  const panel = el('div', 'porownaj-panel');
  const przycisk = el('button', 'porownaj-przycisk', '⇆ Porównaj daty');
  const wyborP = el('select', 'porownaj-data');
  sceny.forEach(s => wyborP.add(new Option(`${opisDaty(s).data} (${opisDaty(s).zakwit})`, s.data)));
  const najwiekszy = sceny.reduce((a, b) => ((b.zakwit_pct || 0) > (a.zakwit_pct || 0) ? b : a));
  wyborP.value = najwiekszy.data;
  panel.append(przycisk, wyborP);
  const kontrolka = L.control({ position: 'topright' });
  kontrolka.onAdd = () => { L.DomEvent.disableClickPropagation(panel); return panel; };
  kontrolka.addTo(mapa);

  function przytnij() {
    if (!wlaczone) return;
    const rozmiar = mapa.getSize();
    const px = rozmiar.x * x;
    const nw = mapa.containerPointToLayerPoint([0, 0]);
    const se = mapa.containerPointToLayerPoint(rozmiar);
    const granica = mapa.containerPointToLayerPoint([px, 0]).x;
    pane.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${granica}px)`;
    belka.style.left = `${px}px`;
  }

  function podpisy() {
    const typ = document.querySelector('#warstwa').value;
    const lewa = sceny.find(s => s.data === document.querySelector('#data').value);
    const pr = sceny.find(s => s.data === wyborP.value);
    podpisL.textContent = `◀ ${opisDaty(lewa).data} · ${opisDaty(lewa).zakwit}`;
    podpisP.textContent = `${opisDaty(pr).data} · ${opisDaty(pr).zakwit} ▶`;
    if (prawa) mapa.removeLayer(prawa);
    prawa = warstwaKafelkow(wyborP.value, typ, { pane: 'porownanie' }).addTo(mapa);
    przytnij();
  }

  function przelacz(stan) {
    wlaczone = stan;
    mapa.getContainer().classList.toggle('tryb-porownania', stan);
    przycisk.classList.toggle('aktywny', stan);
    przycisk.textContent = stan ? '✕ Zamknij porównanie' : '⇆ Porównaj daty';
    if (stan) { podpisy(); } else if (prawa) { mapa.removeLayer(prawa); prawa = null; pane.style.clip = ''; }
  }

  przycisk.addEventListener('click', () => przelacz(!wlaczone));
  wyborP.addEventListener('change', () => { if (wlaczone) podpisy(); else przelacz(true); });
  document.querySelector('#data').addEventListener('change', () => wlaczone && podpisy());
  document.querySelector('#warstwa').addEventListener('change', () => wlaczone && podpisy());
  mapa.on('move zoom resize', przytnij);

  // przeciąganie belki (mysz i palec)
  let ciagne = false;
  const start = e => { ciagne = true; mapa.dragging.disable(); e.preventDefault(); };
  const ruch = e => {
    if (!ciagne) return;
    const p = e.touches ? e.touches[0] : e;
    const r = mapa.getContainer().getBoundingClientRect();
    x = Math.min(0.97, Math.max(0.03, (p.clientX - r.left) / r.width));
    przytnij();
  };
  const koniec = () => { if (ciagne) { ciagne = false; mapa.dragging.enable(); } };
  belka.addEventListener('mousedown', start);
  belka.addEventListener('touchstart', start, { passive: false });
  window.addEventListener('mousemove', ruch);
  window.addEventListener('touchmove', ruch, { passive: true });
  window.addEventListener('mouseup', koniec);
  window.addEventListener('touchend', koniec);
}

// start po wczytaniu sceny.json (jeśli już wczytane - od razu)
function start() {
  pasekCzasu();
  porownanie();
}
if (window.scenyGotowe) start();
else document.addEventListener('sceny-gotowe', start, { once: true });
})();
