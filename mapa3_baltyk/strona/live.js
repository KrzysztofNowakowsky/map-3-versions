// Mapa 3: dane NA ŻYWO - temperatura wody ze stacji IMGW-PIB (punkty na mapie)
// i temperatura powierzchni morza + prognoza 7 dni z Open-Meteo (karta "Teraz w zatoce").
// Gdy API nie odpowiada (np. firewall na uczelni) -> live_zapas.json zapisany przez live_zapas.py.

(() => {
const IMGW = 'https://danepubliczne.imgw.pl/api/data/hydro/';
const MORZE = 'https://marine-api.open-meteo.com/v1/marine?latitude=54.55&longitude=18.75'
  + '&current=sea_surface_temperature&daily=sea_surface_temperature_max&forecast_days=7&timezone=Europe%2FWarsaw';
const STACJE = ['153180120', '154180120', '154180090', '154180140', '154180100'];  // Hel, Gdynia, Puck, Gdańsk, Władysławowo

const pobierz = url => fetch(url, { cache: 'no-store' }).then(r => (r.ok ? r.json() : Promise.reject(r.status)));

async function dane() {
  try {
    const [hydro, morze] = await Promise.all([pobierz(IMGW), pobierz(MORZE)]);
    return { hydro: hydro.filter(s => STACJE.includes(s.id_stacji)), morze, offline: null };
  } catch (e) {
    const zapas = await pobierz('live_zapas.json').catch(() => null);
    return zapas ? { ...zapas, offline: zapas.pobrano } : null;
  }
}

function kolor(t) {                         // 10 °C niebieski -> 24 °C czerwony
  const k = Math.max(0, Math.min(1, (t - 10) / 14));
  return `hsl(${Math.round(210 - 210 * k)}, 80%, 45%)`;
}

const liczba = v => (v === null || v === undefined || v === '' ? null : parseFloat(v));
const godzina = s => (s ? s.slice(0, 16).replace('T', ' ') : '');

function punkty(hydro) {
  hydro.forEach(s => {
    const t = liczba(s.temperatura_wody);
    if (t === null) return;
    const ikona = L.divIcon({
      className: 'punkt-live',
      html: `<span class="puls" style="background:${kolor(t)}"></span><b style="background:${kolor(t)}">${t.toFixed(1)}°</b>`,
      iconSize: [46, 24], iconAnchor: [23, 12],
    });
    L.marker([liczba(s.lat), liczba(s.lon)], { icon: ikona, zIndexOffset: 1000 })
      .bindPopup(`<b>${s.stacja}</b> (IMGW-PIB)<br>woda: <b>${t.toFixed(1)} °C</b>`
        + `<br>stan wody: ${s.stan_wody} cm<br><small>pomiar: ${godzina(s.temperatura_wody_data_pomiaru)}</small>`)
      .addTo(mapa);
  });
}

function karta(d) {
  const t = d.morze.current.sea_surface_temperature;
  const dni = d.morze.daily.time.map((dzien, i) => ({ dzien, t: d.morze.daily.sea_surface_temperature_max[i] }));
  const min = Math.min(...dni.map(x => x.t)) - 0.3, max = Math.max(...dni.map(x => x.t)) + 0.3;
  const W = 260, H = 54;
  const pkt = dni.map((x, i) => [i * (W / (dni.length - 1)), H - ((x.t - min) / (max - min)) * H]);
  const sciezka = pkt.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const dzienTyg = s => ['nd', 'pn', 'wt', 'śr', 'cz', 'pt', 'sb'][new Date(s).getDay()];
  const stacje = d.hydro.map(s => liczba(s.temperatura_wody)).filter(x => x !== null);
  const sr = stacje.length ? (stacje.reduce((a, b) => a + b, 0) / stacje.length).toFixed(1) : '–';

  const div = document.createElement('div');
  div.className = 'teraz';
  div.innerHTML = `
    <div class="teraz-naglowek">
      <span class="${d.offline ? 'kropka offline' : 'kropka'}"></span>
      ${d.offline ? `Offline — zapis z ${godzina(d.offline)}` : 'Na żywo · dziś'}
    </div>
    <div class="teraz-wartosci">
      <div><b style="color:${kolor(t)}">${t.toFixed(1)}°C</b><span>morze (Open-Meteo)</span></div>
      <div><b style="color:${kolor(+sr)}">${sr}°C</b><span>średnio na 5 stacjach IMGW</span></div>
    </div>
    <svg viewBox="-6 -8 ${W + 12} ${H + 26}" class="teraz-wykres" aria-label="Prognoza temperatury morza na 7 dni">
      <path d="${sciezka}" fill="none" stroke="#35b6c7" stroke-width="2.5" stroke-linecap="round"/>
      ${pkt.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#0b3954"/>
        <text x="${p[0]}" y="${H + 15}" text-anchor="middle">${dzienTyg(dni[i].dzien)}</text>`).join('')}
    </svg>
    <p class="opis">Prognoza temperatury morza na 7 dni. To dane z <b>dzisiaj</b> — mapa pokazuje sezon ${document.querySelector('header h1').textContent.match(/\d{4}/)?.[0] || ''}. Kliknij punkt na mapie, żeby zobaczyć stację.</p>`;
  document.querySelector('#szczegoly').after(div);
}

async function start() {
  const d = await dane();
  if (!d) return;
  punkty(d.hydro);
  karta(d);
}
// start po wczytaniu sceny.json (jeśli już wczytane - od razu)
if (window.scenyGotowe) start();
else document.addEventListener('sceny-gotowe', start, { once: true });
})();
