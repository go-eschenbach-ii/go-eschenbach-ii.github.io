(()=>{
  const tokenKey='go-eschenbach-comment-admin-token';
  const token=localStorage.getItem(tokenKey)||'';
  if(!token)return;
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-draft';
  const statusEl=document.getElementById('bottomUpdateStatus');
  const button=document.getElementById('bottomUpdate');
  let draft=null,refreshing=false,dialog=null,notice=null,busy=false;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(action,extra={}){
    const response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action,admin_token:token,...extra}),cache:'no-store'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(data.error||'Netzwerkfehler');
    return data;
  }
  function banner(){
    if(!notice){
      notice=document.createElement('div');
      notice.id='reportDraftNotice';
      notice.className='review-draft-notice';
      const span=document.createElement('span');
      span.textContent='Ein Update wartet auf deine Freigabe.';
      span.id='reviewDraftNoticeText';
      const openButton=document.createElement('button');
      openButton.type='button';openButton.textContent='Entwurf prüfen';
      openButton.addEventListener('click',open);
      notice.append(span,openButton);
      document.querySelector('footer')?.prepend(notice);
    }
    notice.hidden=!draft;
    if(draft){
      const isData=draft.review_required===false;
      const span=notice.querySelector('#reviewDraftNoticeText');
      if(span)span.textContent=isData
        ?'🔎 Neuigkeiten vor der Veröffentlichung prüfen'
        :'✍️ Ein Berichtsentwurf wartet auf deine Freigabe.';
      const action=notice.querySelector('button');
      if(action)action.textContent=isData?'Neuigkeiten ansehen':'Entwurf prüfen';
      if(button && !button.disabled)button.textContent=isData?'Neuigkeiten prüfen':'Entwurf prüfen';
    }
  }
  async function refresh(){
    if(refreshing||busy||document.hidden)return;
    refreshing=true;
    try{
      const d=await api('status');
      draft=d.pending?d:null;
      banner();
      if(draft && !dialog && statusEl){
        statusEl.textContent=draft.review_required===false
          ?'Neuigkeiten-Vorschau bereit. Bitte vor Veröffentlichung prüfen.'
          :'Neuer Berichtsentwurf bereit. Bitte vor Veröffentlichung prüfen.';
        statusEl.dataset.state='review';
        if(button){button.textContent=draft.review_required===false?'Neuigkeiten prüfen':'Entwurf prüfen';button.disabled=false;}
      }
    }catch(e){console.warn('Entwurfsprüfung derzeit nicht erreichbar',e);}
    finally{refreshing=false;}
  }
  const FIELDS=[
    ['title','Titel',2],
    ['lead','Einleitung',4],
    ['review','Rückblick',12],
    ['current_situation','Aktuelle Lage',8],
    ['outlook','Ausblick',8]
  ];
  function buildPanel(d){
    const r=d.report||{};
    const onlyNews=d.review_required===false;
    const shade=document.createElement('div');
    shade.className='review-draft-overlay';
    shade.setAttribute('role','dialog');
    shade.setAttribute('aria-modal','true');
    shade.setAttribute('aria-label',onlyNews?'Neuigkeiten vor Veröffentlichung prüfen':'Berichtsentwurf prüfen und freigeben');
    const box=document.createElement('section');
    box.className='review-draft-panel';
    box.innerHTML='<div class="review-draft-top"><div><strong>'+
      (onlyNews?'Vorschau: Neuigkeiten':'Bericht vor Veröffentlichung prüfen')+
      '</strong><p>'+(onlyNews
        ?'Diese Meldungen erscheinen erst nach deiner Freigabe. Die bisherigen Berichtstexte und Herzen bleiben unverändert.'
        :'Nur für dich sichtbar. Der bisherige Bericht bleibt öffentlich, bis du freigibst.')+
      '</p></div><button type="button" class="review-draft-close" aria-label="Schliessen">×</button></div>';
    const article=document.createElement('div');
    article.className='review-draft-body';
    const info=document.createElement('div');
    info.className='review-draft-info';
    info.textContent=onlyNews
      ?'Vorgeschlagene Meldungen für «Neuigkeiten»: Du kannst sie bearbeiten oder abwählen. Ergebnislisten, Rangliste, Spielplan und Torschützen werden ebenfalls aktualisiert.'
      :'Neuer Bericht vom '+String(r.generated_at||'')+'. Du kannst die Texte direkt korrigieren.';
    article.append(info);
    if(onlyNews){
      const block=document.createElement('section');
      block.className='review-news-preview';
      const items=Array.isArray(d.news?.items)?d.news.items:[];
      const header=document.createElement('h3');
      header.textContent='Das ist neu!';
      block.append(header);
      if(!items.length){
        const empty=document.createElement('p');
        empty.className='review-news-empty';
        empty.textContent='Keine konkreten Neuigkeiten erkannt. Die übrigen Daten können trotzdem aktualisiert werden. Es wird keine neue Neuigkeiten-Meldung erstellt.';
        block.append(empty);
      }
      items.forEach((item,i)=>{
        const row=document.createElement('label');
        row.className='review-news-item';
        const check=document.createElement('input');
        check.type='checkbox';check.checked=true;check.className='review-news-include';
        check.setAttribute('aria-label','Meldung '+(i+1)+' veröffentlichen');
        const field=document.createElement('textarea');
        field.className='review-news-text';field.value=String(item);field.rows=2;
        field.maxLength=400;field.spellcheck=true;
        field.setAttribute('aria-label','Text der Meldung '+(i+1));
        const update=()=>{field.disabled=!check.checked;row.classList.toggle('is-excluded',!check.checked);};
        check.addEventListener('change',update);
        row.append(check,field);block.append(row);
      });
      article.append(block);
    }else{
    for(const [key,label,rows] of FIELDS){
      const wrap=document.createElement('label');
      wrap.className='review-draft-field';
      const head=document.createElement('strong');head.textContent=label;
      const area=document.createElement('textarea');area.rows=rows;area.dataset.key=key;
      area.value=String(r[key]||'');
      area.maxLength=15000;area.spellcheck=true;
      wrap.append(head,area);article.append(wrap);
    }
    const result=document.createElement('div');result.className='review-draft-facts';
    const items=(r.recent_results||[]).slice(0,12);
    result.innerHTML='<h3>Resultate (Kontrolle)</h3>'+
      items.map(m=>'<p>'+esc(m.date)+' · '+esc(m.home)+' <b>'+esc(m.home_goals)+' : '+esc(m.away_goals)+'</b> '+esc(m.away)+'</p>').join('')+
      '<h3>Nächste Spiele</h3>'+
      (r.upcoming_matches||[]).slice(0,12).map(m=>'<p>'+esc(m.date)+' · '+esc(m.time)+' · '+esc(m.home)+' – '+esc(m.away)+'</p>').join('')+
      '<h3>Tabelle</h3>'+
      (r.standings||[]).map(m=>'<p>'+esc(m.rank)+'. '+esc(m.team)+' · '+esc(m.points)+' Punkte</p>').join('');
    article.append(result);
    }
    const actions=document.createElement('div');
    actions.className='review-draft-actions';
    actions.innerHTML='<button type="button" data-action="save">'+(onlyNews?'Meldungen speichern':'Korrekturen speichern')+'</button>'+
      '<button type="button" data-action="publish" class="review-draft-primary">'+(onlyNews?'Update freigeben':'Veröffentlichen')+'</button>'+
      '<button type="button" data-action="discard" class="review-draft-danger">'+(onlyNews?'Update verwerfen':'Entwurf verwerfen')+'</button>';
    const message=document.createElement('p');message.className='review-draft-status';message.setAttribute('aria-live','polite');
    actions.append(message);
    box.append(article,actions);
    shade.append(box);
    shade.querySelector('.review-draft-close').addEventListener('click',close);
    shade.addEventListener('click',e=>{if(e.target===shade)close();});
    actions.querySelectorAll('button[data-action]').forEach(b=>b.addEventListener('click',()=>change(b.dataset.action,message,box)));
    return shade;
  }
  function close(){
    dialog?.remove();dialog=null;
  }
  async function open(){
    if(dialog){dialog.querySelector('textarea')?.focus();return;}
    if(!draft){await refresh();if(!draft)return;}
    dialog=buildPanel(draft);
    document.body.append(dialog);
    dialog.querySelector('textarea')?.focus();
  }
  function edits(box){
    const fields={};
    box.querySelectorAll('textarea[data-key]').forEach(el=>{fields[el.dataset.key]=el.value.trim();});
    return fields;
  }
  function newsEdits(box){
    const items=[];
    box.querySelectorAll('.review-news-item').forEach(row=>{
      if(!row.querySelector('.review-news-include')?.checked)return;
      const value=(row.querySelector('.review-news-text')?.value||'').trim();
      if(value)items.push(value);
    });
    return items;
  }
  async function waitForPublicReport(expected,timeout=150000){
    const begin=Date.now();
    while(Date.now()-begin<timeout){
      try{
        const response=await fetch('data/report.json?approval='+Date.now(),{cache:'no-store'});
        if(response.ok){
          const current=await response.json();
          if(String(current.generated_at||'')===String(expected))return true;
        }
      }catch{}
      await new Promise(resolve=>setTimeout(resolve,5000));
    }
    return false;
  }
  async function change(action,message,box){
    if(busy||!draft)return;
    const onlyNews=draft.review_required===false;
    if(action==='publish'&&!window.confirm(onlyNews
      ?'Daten aktualisieren und die ausgewählten Neuigkeiten für alle veröffentlichen?'
      :'Den Bericht jetzt für alle Nutzer veröffentlichen?'))return;
    if(action==='discard'&&!window.confirm(onlyNews
      ?'Dieses Daten-Update ohne Veröffentlichung verwerfen?'
      :'Den unveröffentlichten Berichtsentwurf wirklich verwerfen?'))return;
    busy=true;
    box.querySelectorAll('button,textarea').forEach(el=>el.disabled=true);
    message.textContent=action==='publish'?'Veröffentlichung läuft …':action==='save'?'Änderungen werden gespeichert …':'Entwurf wird verworfen …';
    try{
      if(action==='save'||action==='publish'){
        if(onlyNews){
          const saved=await api('save_news',{items:newsEdits(box)});
          draft.news=saved.news;
        }else{
          const saved=await api('save',{edits:edits(box)});
          draft.report=saved.report;
        }
      }
      if(action==='publish'){
        const expectedVersion=String(draft.report.generated_at||'');
        const published=await api('publish');
        if(!published.published)throw Error('not_published');
        draft=null;banner();close();
        if(statusEl){statusEl.textContent='Freigegeben. Veröffentlichung läuft …';statusEl.dataset.state='publishing';}
        if(button){button.textContent='Veröffentlicht';button.disabled=true;}
        const live=await waitForPublicReport(expectedVersion);
        if(statusEl){
          statusEl.textContent=live?'Aktualisiert ✓':'Freigegeben. Der neue Bericht erscheint in Kürze.';
          statusEl.dataset.state=live?'done':'info';
        }
        if(button){button.textContent=live?'Aktualisiert':'Update';button.disabled=false;}
        if(live)setTimeout(()=>location.reload(),2200);
      }else if(action==='discard'){
        await api('discard');
        draft=null;banner();close();
        if(statusEl){statusEl.textContent=onlyNews?'Update verworfen. Keine neuen Meldungen veröffentlicht.':'Entwurf verworfen. Der bisherige Bericht bleibt bestehen.';statusEl.dataset.state='info';}
        if(button){button.textContent='Update';button.disabled=false;}
      }else{
        message.textContent=onlyNews
          ?'Neuigkeiten gespeichert. Noch nichts veröffentlicht.'
          :'Korrekturen gespeichert. Der Bericht ist weiterhin unveröffentlicht.';
      }
    }catch(e){
      message.textContent='Konnte nicht abgeschlossen werden: '+String(e.message||e);
    }finally{
      busy=false;
      if(dialog)box.querySelectorAll('button,textarea').forEach(el=>el.disabled=false);
    }
  }
  window.GoDraftReview={open,refresh,get hasPending(){return Boolean(draft);}};
  window.addEventListener('go-draft-ready',()=>{refresh().then(()=>{if(draft)open();});});
  window.addEventListener('pageshow',refresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},15000);
  refresh();
})();