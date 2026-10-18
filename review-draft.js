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
      span.textContent='✍️ Ein Berichtsentwurf wartet auf deine Freigabe.';
      const openButton=document.createElement('button');
      openButton.type='button';openButton.textContent='Entwurf prüfen';
      openButton.addEventListener('click',open);
      notice.append(span,openButton);
      document.querySelector('footer')?.prepend(notice);
    }
    notice.hidden=!draft;
    if(draft && button && !button.disabled)button.textContent='Entwurf prüfen';
  }
  async function refresh(){
    if(refreshing||busy||document.hidden)return;
    refreshing=true;
    try{
      const d=await api('status');
      draft=d.pending?d:null;
      banner();
      if(draft && !dialog && statusEl){
        statusEl.textContent='Neuer Berichtsentwurf bereit. Bitte vor Veröffentlichung prüfen.';
        statusEl.dataset.state='review';
        if(button){button.textContent='Entwurf prüfen';button.disabled=false;}
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
    const shade=document.createElement('div');
    shade.className='review-draft-overlay';
    shade.setAttribute('role','dialog');
    shade.setAttribute('aria-modal','true');
    shade.setAttribute('aria-label','Berichtsentwurf prüfen und freigeben');
    const box=document.createElement('section');
    box.className='review-draft-panel';
    box.innerHTML='<div class="review-draft-top"><div><strong>Bericht vor Veröffentlichung prüfen</strong><p>Nur für dich sichtbar. Der bisherige Bericht bleibt öffentlich, bis du freigibst.</p></div><button type="button" class="review-draft-close" aria-label="Schliessen">×</button></div>';
    const article=document.createElement('div');
    article.className='review-draft-body';
    const info=document.createElement('div');
    info.className='review-draft-info';
    info.textContent='Neuer Bericht vom '+String(r.generated_at||'')+'. Du kannst die Texte direkt korrigieren.';
    article.append(info);
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
    const actions=document.createElement('div');
    actions.className='review-draft-actions';
    actions.innerHTML='<button type="button" data-action="save">Korrekturen speichern</button>'+
      '<button type="button" data-action="publish" class="review-draft-primary">Veröffentlichen</button>'+
      '<button type="button" data-action="discard" class="review-draft-danger">Entwurf verwerfen</button>';
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
  async function change(action,message,box){
    if(busy||!draft)return;
    if(action==='publish'&&!window.confirm('Den Bericht jetzt für alle Nutzer veröffentlichen?'))return;
    if(action==='discard'&&!window.confirm('Den unveröffentlichten Berichtsentwurf wirklich verwerfen?'))return;
    busy=true;
    box.querySelectorAll('button,textarea').forEach(el=>el.disabled=true);
    message.textContent=action==='publish'?'Veröffentlichung läuft …':action==='save'?'Änderungen werden gespeichert …':'Entwurf wird verworfen …';
    try{
      if(action==='save'||action==='publish'){
        const saved=await api('save',{edits:edits(box)});
        draft.report=saved.report;
      }
      if(action==='publish'){
        const published=await api('publish');
        if(!published.published)throw Error('not_published');
        draft=null;banner();close();
        if(statusEl){statusEl.textContent='Aktualisiert ✓';statusEl.dataset.state='done';}
        if(button){button.textContent='Aktualisiert';button.disabled=false;}
        setTimeout(()=>location.reload(),2200);
      }else if(action==='discard'){
        await api('discard');
        draft=null;banner();close();
        if(statusEl){statusEl.textContent='Entwurf verworfen. Der bisherige Bericht bleibt bestehen.';statusEl.dataset.state='info';}
        if(button){button.textContent='Update';button.disabled=false;}
      }else{
        message.textContent='Korrekturen gespeichert. Der Bericht ist weiterhin unveröffentlicht.';
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