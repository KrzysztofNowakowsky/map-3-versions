// Mapa 3: wykresy pod mapą (Chart.js). Dane z przetworz.py, sst.py i statystyki.py.
//  1) sezon: % zakwitu w kolejnych scenach + temperatura morza (od 2023) i powietrza (sceny.json, sst.json)
//  2) szczyt zakwitu rok po roku (lata.json + rok z mapy z sceny.json)
// Brak pliku z danymi = wykres z komunikatem, reszta strony działa dalej.
// Całość w (() => { ... })(), żeby nazwy nie zderzyły się z innymi skryptami strony (mapa.js, live.js).

(() => {
const KOLOR_ZAKWIT = '#a50026';
const KOLOR_SST = '#2171b5';
const KOLOR_POWIETRZE = '#7a8b99';
const KOLOR_ROK = '#0b3954';

function wczytajJson(plik) {
  return fetch(plik).then(r => (r.ok ? r.json() : null)).catch(() => null);
}

function komunikat(id, tekst) {
  document.querySelector(`#${id}`).replaceWith(Object.assign(
    document.createElement('p'), { className: 'opis', textContent: tekst }));
}

function wykresSezonu(cfg, temp) {
  const rok = String(cfg.rok);
  const sceny = (cfg.wszystkie_sceny || cfg.sceny).filter(s => s.zakwit_pct !== null);
  // oś X: wszystkie dni sezonu z temperaturą powietrza (albo same daty scen, gdy brak sst.json)
  const dni = temp ? Object.keys(temp.powietrze).filter(d => d.startsWith(rok)) : sceny.map(s => s.data);
  const zakwit = Object.fromEntries(sceny.map(s => [s.data, s.zakwit_pct]));
  const zbiory = [{
    type: 'line', label: '% zatoki z zakwitem (MCI > ' + cfg.prog_zakwitu + ')',
    data: dni.map(d => zakwit[d] ?? null), yAxisID: 'y',
    borderColor: KOLOR_ZAKWIT, backgroundColor: KOLOR_ZAKWIT,
    showLine: false, pointRadius: 5, pointHoverRadius: 7,
  }];
  const jestMorze = temp && dni.some(d => temp.morze[d] !== undefined);
  if (jestMorze) {
    zbiory.push({
      type: 'line', label: 'temperatura morza [°C]', data: dni.map(d => temp.morze[d] ?? null),
      yAxisID: 'y2', borderColor: KOLOR_SST, borderWidth: 2, pointRadius: 0, tension: 0.3,
    });
  }
  if (temp) {
    zbiory.push({
      type: 'line', label: 'temperatura powietrza [°C]', data: dni.map(d => temp.powietrze[d] ?? null),
      yAxisID: 'y2', borderColor: KOLOR_POWIETRZE, borderWidth: 1.5, borderDash: [5, 4],
      pointRadius: 0, tension: 0.3,
    });
  }
  new Chart(document.querySelector('#wykres-sezon'), {
    data: { labels: dni, datasets: zbiory },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 10 } },
        y: { min: 0, max: 100, title: { display: true, text: '% zatoki z zakwitem' } },
        ...(temp ? { y2: { position: 'right', grid: { drawOnChartArea: false },
                           title: { display: true, text: 'temperatura [°C]' } } } : {}),
      },
      plugins: { title: { display: true, text: `Sezon ${rok}: zakwit a temperatura` } },
    },
  });
  if (temp) {
    document.querySelector('#zrodlo-sst').textContent = 'Temperatura nad środkiem zatoki: '
      + (jestMorze ? temp.zrodlo_morze + '; ' : `brak temperatury morza dla ${rok} (archiwum Open-Meteo ma ją od 2023 r.); `)
      + temp.zrodlo_powietrze + '.';
  }
}

function wykresLat(cfg, lata) {
  const rok = String(cfg.rok);
  // rok z mapy liczymy z jego pełnego sezonu, pozostałe lata z 2 scen szczytu (lata.json)
  const szczyty = { ...lata.szczyty };
  const naMapie = (cfg.wszystkie_sceny || cfg.sceny).filter(s => s.zakwit_pct !== null);
  if (naMapie.length) {
    const max = naMapie.reduce((a, b) => (b.zakwit_pct > a.zakwit_pct ? b : a));
    szczyty[rok] = { data: max.data, zakwit_pct: max.zakwit_pct };
  }
  const lataX = Object.keys(szczyty).sort();
  new Chart(document.querySelector('#wykres-lata'), {
    type: 'bar',
    data: {
      labels: lataX,
      datasets: [{
        label: 'największy % zakwitu w roku',
        data: lataX.map(r => szczyty[r]?.zakwit_pct ?? null),
        backgroundColor: lataX.map(r => (r === rok ? KOLOR_ZAKWIT : KOLOR_ROK)),
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100, title: { display: true, text: '% zatoki z zakwitem' } } },
      plugins: {
        legend: { display: false },
        title: { display: true, text: `Szczyt zakwitu rok po roku (czerwony = ${rok}, pełny sezon)` },
        tooltip: { callbacks: { afterLabel: c => 'scena: ' + (szczyty[c.label]?.data ?? 'brak') } },
      },
    },
  });
}

Promise.all([wczytajJson('sceny.json'), wczytajJson('sst.json'), wczytajJson('lata.json')])
  .then(([cfg, sst, lata]) => {
    if (!cfg) return;
    wykresSezonu(cfg, sst);
    if (lata) wykresLat(cfg, lata);
    else komunikat('wykres-lata', 'Brak lata.json - uruchom python statystyki.py');
  });
})();
