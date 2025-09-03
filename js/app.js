// js/app.js
const DATA_URL = 'https://mujarrib.com/garden/data.json';

async function loadNotes() {
  const res = await fetch(DATA_URL + '?v=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) throw new Error('Fetch data.json failed: ' + res.status);
  const data = await res.json();

  // Converti l'oggetto in un array normale per il renderer esistente
  return Object.entries(data).map(([title, it]) => ({
    title: title || '(senza titolo)',
    type: Array.isArray(it.TYPE) ? it.TYPE[0] : (it.TYPE || 'nota'),
    tags:  Array.isArray(it.TAGS) ? it.TAGS : [],
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
