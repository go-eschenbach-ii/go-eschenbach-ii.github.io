(()=>{
  const host=document.getElementById('updateNewsHost');
  if(!host)return;
  const SEEN_KEY='go-eschenbach-seen-update-news-id';
  const AUTO_CLOSE_MS=18000;

  const getSeen=()=>{try{return localStorage.getItem(SEEN_KEY)||'';}catch{return'';}};
  const markSeen=id=>{try{localStorage.setItem(SEEN_KEY,id);}catch{}};

  const show=news=>{
    const card=document.createElement('section');
    card.className='update-news-card';
    card.setAttribute('role','status');
    const heading=document.createElement('div');
    heading.className='update-news-heading';
    const symbol=document.createElement('span');
    symbol.className='update-news-symbol';
    symbol.setAttribute('aria-hidden','true');
    symbol.textContent='★';
    const title=document.createElement('strong');
    title.textContent=String(news.title||'Das ist neu!');
    const close=document.createElement('button');
    close.type='button';
    close.className='update-news-close';
    close.setAttribute('aria-label','Neuigkeiten schliessen');
    close.textContent='×';
    heading.append(symbol,title,close);

    const list=document.createElement('ul');
    list.className='update-news-list';
    news.items.slice(0,4).forEach(item=>{
      const li=document.createElement('li');
      li.textContent=String(item);
      list.append(li);
    });
    card.append(heading,list);
    host.replaceChildren(card);
    host.hidden=false;
    markSeen(news.id);

    let timer;
    const dismiss=()=>{
      clearTimeout(timer);
      card.classList.add('update-news-leaving');
      setTimeout(()=>{host.hidden=true;host.replaceChildren();},250);
    };
    close.addEventListener('click',dismiss);
    timer=setTimeout(dismiss,AUTO_CLOSE_MS);
  };

  const check=async()=>{
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
      const expiry=Date.parse(String(news.expires_at||''));
      if(!Number.isFinite(expiry)||Date.now()>expiry)return;
      show(news);
    }catch{}
  };
  check();
})();
