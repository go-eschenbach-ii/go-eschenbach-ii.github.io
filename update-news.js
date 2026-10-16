(()=>{
  const host=document.getElementById('updateNewsHost');
  if(!host)return;

  // Neue Lesebestaetigung: Fruehere Meldungen wurden schon beim Einblenden
  // als gelesen markiert und sollen einmalig erneut gezeigt werden koennen.
  const SEEN_KEY='go-eschenbach-seen-update-news-on-tap-v2';
  let checking=false;

  const getSeen=()=>{
    try{return localStorage.getItem(SEEN_KEY)||'';}catch{return'';}
  };
  const markSeen=id=>{
    try{localStorage.setItem(SEEN_KEY,id);}catch{}
  };

  const show=news=>{
    const current=host.querySelector('.update-news-card');
    if(current?.dataset.newsId===news.id)return;
    const card=document.createElement('section');
    card.className='update-news-card';
    card.dataset.newsId=news.id;
    card.setAttribute('role','button');
    card.setAttribute('tabindex','0');
    card.setAttribute('aria-label','Neue Resultate und Neuigkeiten. Zum Schliessen antippen oder Enter drücken.');

    const heading=document.createElement('div');
    heading.className='update-news-heading';
    const symbol=document.createElement('span');
    symbol.className='update-news-symbol';
    symbol.setAttribute('aria-hidden','true');
    symbol.textContent='★';
    const title=document.createElement('strong');
    title.textContent=String(news.title||'Das ist neu!');
    heading.append(symbol,title);

    const list=document.createElement('ul');
    list.className='update-news-list';
    news.items.slice(0,4).forEach(item=>{
      const li=document.createElement('li');
      li.textContent=String(item);
      list.append(li);
    });

    const hint=document.createElement('div');
    hint.className='update-news-hint';
    hint.textContent='Zum Schliessen hier antippen';

    card.append(heading,list,hint);
    host.replaceChildren(card);
    host.hidden=false;

    let dismissed=false;
    const dismiss=()=>{
      if(dismissed)return;
      dismissed=true;
      // Erst ein aktives Antippen bestaetigt diese Meldung als gelesen.
      markSeen(news.id);
      card.classList.add('update-news-leaving');
      setTimeout(()=>{
        if(host.contains(card)){
          host.hidden=true;
          card.remove();
        }
      },250);
    };
    card.addEventListener('click',dismiss);
    card.addEventListener('keydown',e=>{
      if(e.key==='Enter'||e.key===' '){
        e.preventDefault();
        dismiss();
      }
    });
  };

  const check=async()=>{
    if(checking)return;
    checking=true;
    try{
      const [newsResponse,reportResponse]=await Promise.all([
        fetch('data/update-news.json?t='+Date.now(),{cache:'no-store'}),
        fetch('data/report.json?newscheck='+Date.now(),{cache:'no-store'})
      ]);
      if(!newsResponse.ok||!reportResponse.ok)return;
      const [news,report]=await Promise.all([newsResponse.json(),reportResponse.json()]);
      if(!news||typeof news.id!=='string'||!news.id.trim()||getSeen()===news.id)return;
      if(!Array.isArray(news.items)||!news.items.length)return;
      if(String(news.report_version||'')!==String(report.generated_at||''))return;
      // Die News bleiben bis zum bewussten Schliessen sichtbar. Ein
      // automatisch ablaufendes Zeitlimit gibt es nicht mehr.
      show(news);
    }catch{}
    finally{checking=false;}
  };
  check();
  window.addEventListener('pageshow',check);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
})();
