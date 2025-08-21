// js/app.js
const DATA_URL = 'https://mujarrib.com/garden/data.ndtl';

async function loadNotes() {
  const res = await fetch(DATA_URL + '?v=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) throw new Error('Fetch data.ndtl failed: ' + res.status);
  const text = await res.text();
  // Usa il parser Indental che già avevi (esporta una funzione parseIndental)
  const items = parseIndental(text); // -> array di oggetti {TITLE, TYPE, TAGS, DATE, QOTE, LINK, ...}

  // Normalizzazione minima per il renderer esistente
  return items.map(it => ({
    title: it.TITLE || '(senza titolo)',
    type:  it.TYPE  || 'nota',
    tags:  (it.TAGS || '').split(',').map(s => s.trim()).filter(Boolean),
    date:  it.DATE  || '',
    body:  it.QOTE || it.BODY || '',
    link:  it.LINK || ''
  }));
}

let notes = [];
loadNotes()
  .then(arr => { notes = arr; render(); })
  .catch(err => {
    console.error(err);
    document.getElementById('grid').innerHTML =
      '<div class="empty">Impossibile caricare i dati.</div>';
  });
