(()=>{
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/match-comments-admin';
  const TOKEN_KEY='go-eschenbach-comment-admin-token';
  const QUEUE_KEY='go-eschenbach-comment-queue-v1';
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  let adminToken=localStorage.getItem(TOKEN_KEY)||'';
  let currentMatch=null;
  let serverComments=[];
  let recognition=null;
  let speechActive=false;
  let wakeLock=null;
  let panel=null;
  let statusEl=null;
  let liveEl=null;
  let notesEl=null;
  let countEl=null;
  let startButton=null;
  let approveAllButton=null;
  let manualWrap=null;
  let activateTimer=null;
  let suppressLogoClick=false;

  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const uid=()=>crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const getQueue=()=>{try{return JSON.parse(localStorage.getItem(QUEUE_KEY)||'[]')}catch{return[]}};
  const setQueue=q=>localStorage.setItem(QUEUE_KEY,JSON.stringify(q));
  const setStatus=(text,state='')=>{if(statusEl){statusEl.textContent=text;statusEl.dataset.state=state;}};
  const localDateFromReport=value=>{
    const m=String(value||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return m?`${m[3]}-${m[2]}-${m[1]}`:'';
  };
  const localDateLabel=value=>{
    const m=String(value||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return m?`${m[1]}.${m[2]}.${m[3]}`:String(value||'');
  };
  const slug=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,60);
  const matchKey=m=>`${localDateFromReport(m.date)||String(m.date||'').replace(/\D/g,'')}:${slug(m.home)}:${slug(m.away)}`;
  const matchLabel=m=>`${m.home} – ${m.away}`;
  const parseKickoff=m=>{
    const dm=String(m.date||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if(!dm)return null;
    const tm=String(m.time||'12:00').match(/^(\d{1,2}):(\d{2})$/);
    const hh=tm?Number(tm[1]):12, mm=tm?Number(tm[2]):0;
    return new Date(Number(dm[3]),Number(dm[2])-1,Number(dm[1]),hh,mm,0,0);
  };
  const isEschenbach=m=>/FC\s+Eschenbach\s+II/i.test(String(m?.home||''))||/FC\s+Eschenbach\s+II/i.test(String(m?.away||''));

  async function api(action,payload={}){
    const headers={'Content-Type':'application/json'};
    if(adminToken)headers.Authorization=`Bearer ${adminToken}`;
    const r=await fetch(API,{method:'POST',headers,body:JSON.stringify({action,...payload})});
    const d=await r.json().catch(()=>({}));
    if(r.status===401){localStorage.removeItem(TOKEN_KEY);adminToken='';}
    if(!r.ok)throw Object.assign(new Error(d.error||'api_error'),{status:r.status,data:d});
    return d;
  }

  async function chooseMatch(){
    const r=await fetch(`data/report.json?commentary=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw Error('report');
    const d=await r.json();
    const upcoming=(d.upcoming_matches||[]).filter(isEschenbach);
    const recent=(d.recent_results||[]).filter(isEschenbach);
    const now=Date.now();
    const all=[...upcoming,...recent].map(m=>({m,k:parseKickoff(m)})).filter(x=>x.k);
    const live=all.filter(x=>now>=x.k.getTime()-2*3600000&&now<=x.k.getTime()+5*3600000).sort((a,b)=>Math.abs(now-a.k)-Math.abs(now-b.k))[0];
    if(live)return live.m;
    const future=all.filter(x=>x.k.getTime()>now).sort((a,b)=>a.k-b.k)[0];
    if(future)return future.m;
    const past=all.filter(x=>x.k.getTime()<=now).sort((a,b)=>b.k-a.k)[0];
    return past?.m||null;
  }

  function combinedComments(){
    if(!currentMatch)return[];
    const key=matchKey(currentMatch);
    const queued=getQueue().filter(x=>x.match_key===key).map(x=>({...x,id:`local:${x.client_id}`,queued:true}));
    return [...serverComments.filter(x=>x.match_key===key),...queued].sort((a,b)=>new Date(a.spoken_at)-new Date(b.spoken_at));
  }

  function formatTime(value){
    const d=new Date(value);
    if(Number.isNaN(d.getTime()))return'';
    return d.toLocaleTimeString('de-CH',{hour:'2-digit',minute:'2-digit'});
  }

  function renderNotes(){
    if(!notesEl||!countEl)return;
    const comments=combinedComments();
    const approved=comments.filter(x=>x.approved).length;
    countEl.innerHTML=`<span class="commentary-chip">${comments.length} Kommentar${comments.length===1?'':'e'}</span><span class="commentary-chip">${approved} für Rückblick freigegeben</span>`;
    if(!comments.length){
      notesEl.innerHTML='<div class="commentary-empty">Noch keine Kommentare. Starte den Sprachmodus und sprich einfach ins Headset.</div>';
      if(approveAllButton)approveAllButton.disabled=true;
      return;
    }
    if(approveAllButton)approveAllButton.disabled=false;
    notesEl.innerHTML=comments.map(c=>{
      const state=c.approved?'Freigegeben':c.edited?'Bearbeitet':c.queued?'Wartet auf Sync':'Neu';
      return `<article class="commentary-note" data-id="${esc(c.id)}">
        <div class="commentary-note-head"><span class="commentary-note-time">${esc(formatTime(c.spoken_at))} Uhr</span><span class="commentary-badge ${c.approved?'approved':''}">${esc(state)}</span></div>
        <textarea aria-label="Transkription bearbeiten">${esc(c.transcript)}</textarea>
        <div class="commentary-note-actions">
          <button type="button" data-action="save">Speichern</button>
          <button type="button" class="approve" data-action="approve">${c.approved?'Freigabe zurücknehmen':'Für Rückblick freigeben'}</button>
          <button type="button" class="delete" data-action="delete">Löschen</button>
        </div>
      </article>`;
    }).join('');
  }

  async function loadComments(){
    if(!currentMatch||!adminToken)return;
    try{
      const d=await api('list',{match_key:matchKey(currentMatch)});
      serverComments=d.comments||[];
      renderNotes();
    }catch(err){
      if(err.status===401){unmountPanel();return;}
      setStatus('Kommentare konnten gerade nicht geladen werden.','error');
    }
  }

  async function flushQueue(){
    if(!adminToken)return;
    let queue=getQueue();
    if(!queue.length)return;
    let changed=false;
    for(const item of [...queue]){
      try{
        const d=await api('create',item);
        if(item.approved&&d.comment?.id)await api('update',{id:d.comment.id,approved:true});
        queue=queue.filter(x=>x.client_id!==item.client_id);
        changed=true;
      }catch{break;}
    }
    if(changed){setQueue(queue);await loadComments();}
  }

  function queueTranscript(text,spokenAt=new Date().toISOString()){
    if(!currentMatch)return;
    const transcript=String(text||'').replace(/\s+/g,' ').trim();
    if(!transcript)return;
    const item={
      client_id:uid(),
      match_key:matchKey(currentMatch),
      match_label:matchLabel(currentMatch),
      match_date:localDateFromReport(currentMatch.date),
      match_time:String(currentMatch.time||''),
      spoken_at:spokenAt,
      transcript,
      approved:false,
      edited:false
    };
    const queue=getQueue();queue.push(item);setQueue(queue);
    renderNotes();
    flushQueue();
  }

  async function requestWakeLock(){
    if(!('wakeLock'in navigator)||document.visibilityState!=='visible'||wakeLock)return;
    try{wakeLock=await navigator.wakeLock.request('screen');wakeLock.addEventListener('release',()=>{wakeLock=null;});}catch{}
  }
  async function releaseWakeLock(){
    try{await wakeLock?.release();}catch{}wakeLock=null;
  }

  function buildRecognition(){
    if(!Recognition)return null;
    const r=new Recognition();
    r.lang='de-CH';
    r.continuous=true;
    r.interimResults=true;
    r.maxAlternatives=1;
    r.onresult=e=>{
      let interim='';
      for(let i=e.resultIndex;i<e.results.length;i++){
        const result=e.results[i];
        const text=String(result[0]?.transcript||'').trim();
        if(!text)continue;
        if(result.isFinal)queueTranscript(text);
        else interim+=(interim?' ':'')+text;
      }
      if(liveEl)liveEl.textContent=interim?`Ich höre: ${interim}`:'';
    };
    r.onerror=e=>{
      if(e.error==='not-allowed'||e.error==='service-not-allowed'){
        speechActive=false;
        updateSpeechButton();
        setStatus('Mikrofon bzw. Spracherkennung wurde nicht freigegeben.','error');
      }else if(e.error!=='aborted'&&e.error!=='no-speech'){
        setStatus('Spracherkennung wird neu gestartet …','');
      }
    };
    r.onend=()=>{
      if(liveEl)liveEl.textContent='';
      if(speechActive)setTimeout(()=>{try{r.start();}catch{}},350);
    };
    return r;
  }

  function updateSpeechButton(){
    if(!startButton)return;
    startButton.classList.toggle('is-active',speechActive);
    startButton.textContent=speechActive?'■ Kommentar-Modus beenden':'🎙 Kommentar-Modus starten';
  }

  async function startSpeech(){
    if(!Recognition){
      setStatus('Diese iPhone-/Browser-Version unterstützt die automatische Transkription hier nicht. Du kannst unten Textnotizen eingeben.','error');
      if(manualWrap)manualWrap.hidden=false;
      return;
    }
    if(speechActive){stopSpeech();return;}
    recognition=buildRecognition();
    if(!recognition)return;
    try{
      speechActive=true;
      updateSpeechButton();
      await requestWakeLock();
      recognition.start();
      setStatus('Kommentar-Modus aktiv – einfach sprechen. Pausen trennen die Kommentare.','active');
    }catch{
      speechActive=false;updateSpeechButton();
      setStatus('Sprachmodus konnte nicht gestartet werden.','error');
    }
  }

  function stopSpeech(){
    speechActive=false;
    updateSpeechButton();
    try{recognition?.stop();}catch{}
    recognition=null;
    if(liveEl)liveEl.textContent='';
    releaseWakeLock();
    setStatus('Kommentar-Modus beendet. Du kannst die Transkriptionen jetzt prüfen und freigeben.','');
  }

  async function handleNoteAction(e){
    const button=e.target.closest('button[data-action]');
    if(!button)return;
    const card=button.closest('.commentary-note');
    const id=card?.dataset.id||'';
    const textarea=card?.querySelector('textarea');
    const text=String(textarea?.value||'').replace(/\s+/g,' ').trim();
    if(!id)return;
    button.disabled=true;
    try{
      if(id.startsWith('local:')){
        const clientId=id.slice(6);
        let q=getQueue();
        const item=q.find(x=>x.client_id===clientId);
        if(!item)return;
        if(button.dataset.action==='delete')q=q.filter(x=>x.client_id!==clientId);
        if(button.dataset.action==='save'){
          if(!text){button.disabled=false;return;}
          item.edited=item.transcript!==text||item.edited;item.transcript=text;
        }
        if(button.dataset.action==='approve')item.approved=!item.approved;
        setQueue(q);renderNotes();flushQueue();
        return;
      }
      const existing=serverComments.find(x=>x.id===id);
      if(!existing)return;
      if(button.dataset.action==='delete')await api('delete',{id});
      if(button.dataset.action==='save'){
        if(!text){button.disabled=false;return;}
        await api('update',{id,transcript:text});
      }
      if(button.dataset.action==='approve')await api('update',{id,approved:!existing.approved});
      await loadComments();
    }catch{setStatus('Änderung konnte gerade nicht gespeichert werden.','error');}
    finally{button.disabled=false;}
  }

  async function approveAll(){
    if(!currentMatch)return;
    approveAllButton.disabled=true;
    try{
      let q=getQueue();
      q.forEach(x=>{if(x.match_key===matchKey(currentMatch))x.approved=true;});
      setQueue(q);
      await flushQueue();
      await api('approve_all',{match_key:matchKey(currentMatch)});
      await loadComments();
      setStatus('Alle Kommentare sind für den nächsten Rückblick freigegeben.','active');
    }catch{setStatus('Freigabe konnte gerade nicht gespeichert werden.','error');}
    finally{approveAllButton.disabled=false;}
  }

  function manualAdd(){
    const field=panel?.querySelector('#commentaryManualText');
    const text=String(field?.value||'').trim();
    if(!text)return;
    queueTranscript(text);
    field.value='';
  }

  function mountPanel(){
    if(panel||!adminToken||!currentMatch)return;
    const app=document.getElementById('app');
    if(!app)return;
    const review=[...app.querySelectorAll('section.card')].find(s=>s.querySelector('h2')?.textContent.trim()==='Rückblick');
    if(!review)return;
    panel=document.createElement('section');
    panel.className='card match-commentary-panel';
    panel.id='matchCommentaryPanel';
    panel.innerHTML=`
      <h2>🎙 Matchkommentar</h2>
      <div class="commentary-match">${esc(matchLabel(currentMatch))}</div>
      <div class="commentary-date">${esc(localDateLabel(currentMatch.date))}${currentMatch.time?` · ${esc(currentMatch.time)} Uhr`:''}</div>
      <div class="commentary-controls">
        <button type="button" class="commentary-primary" id="commentaryStart">🎙 Kommentar-Modus starten</button>
        <button type="button" class="commentary-secondary" id="commentaryApproveAll">Alle für Rückblick freigeben</button>
      </div>
      <div class="commentary-status" id="commentaryStatus">Headset verbinden, dann den Kommentar-Modus starten.</div>
      <div class="commentary-live" id="commentaryLive" aria-live="polite"></div>
      <div class="commentary-counts" id="commentaryCounts"></div>
      <div class="commentary-notes" id="commentaryNotes"></div>
      <div class="commentary-manual" id="commentaryManual" ${Recognition?'hidden':''}>
        <textarea id="commentaryManualText" placeholder="Notiz eintippen …" aria-label="Kommentar als Text eingeben"></textarea>
        <div class="commentary-controls" style="margin-top:7px"><button type="button" class="commentary-secondary" id="commentaryManualAdd">Notiz hinzufügen</button></div>
      </div>
      <p class="commentary-help">Nur auf deinem freigeschalteten Gerät sichtbar. Gespeichert wird die Transkription, keine Audiodatei. Bearbeitete oder freigegebene Texte fliessen erst beim nächsten Update in den Rückblick ein.</p>`;
    review.parentNode.insertBefore(panel,review);
    statusEl=panel.querySelector('#commentaryStatus');
    liveEl=panel.querySelector('#commentaryLive');
    notesEl=panel.querySelector('#commentaryNotes');
    countEl=panel.querySelector('#commentaryCounts');
    startButton=panel.querySelector('#commentaryStart');
    approveAllButton=panel.querySelector('#commentaryApproveAll');
    manualWrap=panel.querySelector('#commentaryManual');
    startButton.addEventListener('click',startSpeech);
    approveAllButton.addEventListener('click',approveAll);
    notesEl.addEventListener('click',handleNoteAction);
    panel.querySelector('#commentaryManualAdd')?.addEventListener('click',manualAdd);
    renderNotes();
    loadComments();
    flushQueue();
  }

  function unmountPanel(){
    stopSpeech();
    panel?.remove();panel=null;statusEl=null;liveEl=null;notesEl=null;countEl=null;startButton=null;approveAllButton=null;manualWrap=null;
  }

  async function initAdmin(){
    if(!adminToken)return;
    try{
      await api('status');
      currentMatch=await chooseMatch();
      if(!currentMatch)return;
      mountPanel();
      if(!panel){
        const app=document.getElementById('app');
        if(app){const obs=new MutationObserver(()=>{mountPanel();if(panel)obs.disconnect();});obs.observe(app,{childList:true,subtree:true});}
      }
    }catch{localStorage.removeItem(TOKEN_KEY);adminToken='';}
  }

  async function activateAdmin(){
    const code=window.prompt('Kommentar-Modus freischalten: Einmaligen Aktivierungscode eingeben');
    if(!code)return;
    try{
      const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'activate',activation_code:code.trim(),label:'Marc iPhone'})});
      const d=await r.json().catch(()=>({}));
      if(!r.ok||!d.admin_token){
        window.alert('Aktivierungscode stimmt nicht oder wurde bereits verwendet.');
        return;
      }
      adminToken=d.admin_token;
      localStorage.setItem(TOKEN_KEY,adminToken);
      currentMatch=await chooseMatch();
      mountPanel();
      window.alert('Kommentar-Modus ist auf diesem Gerät freigeschaltet.');
    }catch{window.alert('Freischaltung konnte gerade nicht abgeschlossen werden.');}
  }

  function installSecretActivation(){
    const logo=document.getElementById('logoButton');
    if(!logo)return;
    const cancel=()=>{if(activateTimer){clearTimeout(activateTimer);activateTimer=null;}};
    logo.addEventListener('pointerdown',()=>{
      cancel();
      activateTimer=setTimeout(()=>{activateTimer=null;suppressLogoClick=true;activateAdmin();},2800);
    });
    logo.addEventListener('pointerup',cancel);
    logo.addEventListener('pointercancel',cancel);
    logo.addEventListener('pointerleave',cancel);
    logo.addEventListener('contextmenu',e=>{if(!adminToken)e.preventDefault();});
    logo.addEventListener('click',e=>{
      if(!suppressLogoClick)return;
      suppressLogoClick=false;
      e.preventDefault();e.stopImmediatePropagation();
    },true);
  }

  document.addEventListener('visibilitychange',()=>{if(speechActive&&document.visibilityState==='visible')requestWakeLock();});
  window.addEventListener('online',()=>flushQueue());
  window.addEventListener('beforeunload',()=>{if(speechActive)stopSpeech();});

  installSecretActivation();
  initAdmin();
})();
