(()=>{
  const host=document.getElementById('liveTickerHost');
  if(!host)return;
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/live-ticker';
  const TOKEN_KEY='go-eschenbach-comment-admin-token';
  const SEEN_PREFIX='go-eschenbach-live-seen:';
  const adminToken=localStorage.getItem(TOKEN_KEY)||'';
  let report=null,live={match:null,events:[]},busy=false;
  let shownSignature='',selectedKey='',refreshing=false;
  const isEschenbach=m=>[m.home,m.away].includes('FC Eschenbach II');
  const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const makeKey=m=>[m.date,m.time||'',m.home,m.away].join('|');
  const dateISO=value=>String(value||'').split('.').reverse().join('-');
  const shortTeam=t=>String(t||'').replace(/^(FC|SC)\s+/,'');
  const matchLabel=m=>String(m.date||'')+' · '+String(m.time||'')+' Uhr · '+m.home+' – '+m.away;
  const minute=t=>{
    if(!t)return'';
    try{return new Date(t).toLocaleTimeString('de-CH',{timeZone:'Europe/Zurich',hour:'2-digit',minute:'2-digit'})+' Uhr';}
    catch{return'';}
  };
  function nextFixture(){
    const all=(report?.upcoming_matches||[]).filter(m=>m&&isEschenbach(m)&&m.date&&m.time);
    const upcoming=all.filter(m=>{
      const start=Date.parse(dateISO(m.date)+'T'+String(m.time).padStart(5,'0')+':00+02:00');
      return Number.isFinite(start)&&start>Date.now()-3*3600000;
    });
    upcoming.sort((a,b)=>dateISO(a.date).localeCompare(dateISO(b.date))||String(a.time).localeCompare(String(b.time)));
    return upcoming[0]||null;
  }
  function previewMatch(f){
    return f?{
      match_key:makeKey(f),match_date:dateISO(f.date),match_time:f.time,
      home:f.home,away:f.away,home_goals:0,away_goals:0,status:'upcoming',
      updated_at:''
    }:null;
  }
  function choices(){
    if(!report)return[];
    const all=[...(report.upcoming_matches||[])].filter(m=>
      m&&isEschenbach(m)&&m.time&&m.date
    );
    const uniq=new Map(all.map(m=>[makeKey(m),m]));
    const current=Date.now();
    return [...uniq.values()].filter(m=>{
      const t=Date.parse(dateISO(m.date)+'T12:00:00Z');
      return Number.isFinite(t)&&Math.abs(t-current)<47*3600000;
    }).sort((a,b)=>dateISO(a.date).localeCompare(dateISO(b.date)));
  }
  function acknowledge(){
    const m=live.match,ev=live.events?.[0];
    if(!m||!ev)return;
    try{localStorage.setItem(SEEN_PREFIX+m.match_key,ev.id);}catch{}
    const one=host.querySelector('.live-ticker-one');
    if(one)one.remove();
  }
  function controlsMatch(m){
    if(!m)return'';
    return '<div class="live-ticker-admin-actions">'+
      '<button type="button" data-action="goal" data-team="home" aria-label="Tor '+esc(m.home)+'">⚽ Tor '+esc(shortTeam(m.home))+' +1</button>'+
      '<button type="button" data-action="goal" data-team="away" aria-label="Tor '+esc(m.away)+'">⚽ Tor '+esc(shortTeam(m.away))+' +1</button>'+
      '<button type="button" class="live-secondary" data-action="correction" data-team="home">−1 '+esc(shortTeam(m.home))+'</button>'+
      '<button type="button" class="live-secondary" data-action="correction" data-team="away">−1 '+esc(shortTeam(m.away))+'</button>'+
      '<button type="button" class="live-secondary live-finish" data-action="finish">Spiel beenden</button>'+
      '</div>';
  }
  function choicesPanel(){
    const candidates=choices();
    if(!adminToken||!candidates.length)return'';
    if(!selectedKey||!candidates.some(m=>makeKey(m)===selectedKey)){
      const today=new Date().toLocaleDateString('de-CH',{timeZone:'Europe/Zurich',day:'2-digit',month:'2-digit',year:'numeric'});
      const preferred=candidates.find(m=>m.date===today)||candidates[0];
      selectedKey=makeKey(preferred);
    }
    return '<div class="live-ticker-admin-start"><span>Admin · Livematch auswählen</span>'+
      '<select id="liveTickerMatchSelect" aria-label="Match auswählen">'+
       candidates.map(m=>'<option value="'+esc(makeKey(m))+'"'+(makeKey(m)===selectedKey?' selected':'')+'>'+esc(matchLabel(m))+'</option>').join('')+
      '</select><button type="button" data-action="start">Liveticker starten</button></div>';
  }
  function render(force=false){
    const m=live.match?.status==='live'?live.match:previewMatch(nextFixture());
    const events=m?.status==='live'?live.events||[]:[];
    if(!m&&!adminToken){host.hidden=true;return;}
    const latest=events[0]?.id||'';
    let seen='';
    try{seen=m?localStorage.getItem(SEEN_PREFIX+m.match_key)||'':'';}catch{}
    const unread=Boolean(latest&&seen!==latest);
    const signature=JSON.stringify([m,events,unread,selectedKey,Boolean(adminToken),busy]);
    if(!force&&shownSignature===signature)return;
    shownSignature=signature;
    host.hidden=false;
    const active=m?.status==='live';
    const planned=m?.status==='upcoming';
    const heading='<div class="live-ticker-head"><strong>'+(active?'🔴 LIVE':planned?'⚽ NÄCHSTES SPIEL':'⚽ LIVETICKER')+'</strong>'+
      (unread?'<span class="live-ticker-one" aria-label="Neue Tore">1</span>':'')+
      '<span class="live-ticker-head-caption">'+(active?'Spielstand · laufend':'Spielstand')+'</span></div>';
    const scoreboard=m?'<div class="live-ticker-score">'+
      '<div class="live-ticker-team">'+esc(shortTeam(m.home))+'</div>'+
      '<div class="live-ticker-numbers">'+(planned?'– : –':Number(m.home_goals)+' : '+Number(m.away_goals))+'</div>'+
      '<div class="live-ticker-team">'+esc(shortTeam(m.away))+'</div></div>'+
      '<div class="live-ticker-meta">'+esc(m.match_date.split('-').reverse().join('.'))+
      ' · '+esc(m.match_time)+' Uhr · '+(active?'Liveticker aktiv':planned?'Noch nicht gestartet':'Spiel beendet')+'</div>':'';
    const feed=m&&!planned?'<div class="live-ticker-events"><strong>Tor-Ticker</strong>'+
      (events.length?'<ol>'+events.map(e=>{
        const team=e.team==='home'?m.home:m.away;
        return '<li><span class="live-ticker-event-time">'+esc(minute(e.created_at))+'</span>'+
          '<span>'+(e.event_type==='goal'?'⚽ Tor für ':'↩️ Korrektur für ')+esc(team)+
          ' · <strong>'+Number(e.home_goals)+':'+Number(e.away_goals)+'</strong></span></li>';
      }).join('')+'</ol>':'<p>Noch keine Tore eingetragen.</p>')+
      '</div>':'';
    const admin=m&&active&&adminToken?'<div class="live-ticker-admin">'+
      '<div class="live-ticker-admin-title">Nur für Admin: Tor erfassen</div>'+
      controlsMatch(m)+'</div>':'';
    host.innerHTML='<section class="live-ticker-card" id="liveTickerCard" tabindex="-1">'+heading+scoreboard+feed+
      (adminToken?choicesPanel()+admin:'')+'</section>';
    host.querySelector('#liveTickerMatchSelect')?.addEventListener('change',e=>{selectedKey=e.target.value;});
    host.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',()=>act(button.dataset.action,button.dataset.team)));
    host.querySelector('.live-ticker-events')?.addEventListener('click',acknowledge);
    host.querySelector('.live-ticker-score')?.addEventListener('click',acknowledge);
    host.querySelector('.live-ticker-head')?.addEventListener('click',acknowledge);
    if(busy)host.querySelectorAll('button,select').forEach(el=>el.disabled=true);
  }
  async function load(){
    if(refreshing||busy)return;
    refreshing=true;
    try{
      const r=await fetch(API+'?t='+Date.now(),{cache:'no-store'});
      if(!r.ok)throw Error('fetch_failed');
      const data=await r.json();
      live={match:data.match||null,events:data.events||[]};
      if(!report||Date.now()-(window.__goLiveReportLoadedAt||0)>60000){
        try{const fresh=await fetch('data/report.json?live='+Date.now(),{cache:'no-store'});
          if(fresh.ok){report=await fresh.json();window.__goLiveReportLoadedAt=Date.now();}
        }catch{}
      }
      render();
    }catch(err){
      console.warn('Liveticker zurzeit nicht abrufbar',err);
    }finally{refreshing=false;}
  }
  async function act(action,team){
    if(!adminToken||busy)return;
    const payload={action,admin_token:adminToken};
    if(action==='start'){
      const match=choices().find(m=>makeKey(m)===selectedKey);
      if(!match)return;
      if(!window.confirm('Liveticker starten für:\n'+matchLabel(match)+'?'))return;
      Object.assign(payload,{match_key:makeKey(match),match_date:dateISO(match.date),
        match_time:match.time,home:match.home,away:match.away});
    }else{
      if(!live.match)return;
      payload.match_key=live.match.match_key;
      if(action==='goal'||action==='correction'){
        payload.team=team;
        payload.event_id=crypto.randomUUID();
        if(action==='correction'&&!window.confirm('Ein Tor bei '+(team==='home'?live.match.home:live.match.away)+' abziehen?'))return;
      }else if(action==='finish'){
        if(!window.confirm('Liveticker abschliessen?'))return;
      }
    }
    busy=true;render(true);
    try{
      const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const response=await r.json().catch(()=>({}));
      if(!r.ok)throw Error(response.error||'Speichern fehlgeschlagen');
      if(response.push?.failed)console.warn('Pushzustellung teilweise fehlgeschlagen',response.push);
      // Do not automatically mark news read: the viewer should acknowledge it.
      const latest=await fetch(API+'?t='+Date.now(),{cache:'no-store'});
      if(latest.ok){
        const d=await latest.json();
        live={match:d.match||response.match,events:d.events||[]};
      }else{live.match=response.match;}
    }catch(err){
      window.alert('Liveticker konnte nicht aktualisiert werden: '+String(err.message||err));
    }finally{busy=false;shownSignature='';render(true);}
  }
  (async()=>{
    try{
      const r=await fetch('data/report.json?liveticker='+Date.now(),{cache:'no-store'});
      if(r.ok){report=await r.json();window.__goLiveReportLoadedAt=Date.now();}
    }catch{}
    await load();
    // Admin sees the start panel even if the server has no active match.
    render(true);
  })();
  setInterval(()=>{if(!document.hidden)load();},8000);
  window.addEventListener('pageshow',load);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
})();
