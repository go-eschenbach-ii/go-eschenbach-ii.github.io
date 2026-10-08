(()=>{
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/match-tips-public';
  const DEVICE_KEY='go-eschenbach-tip-device-id';
  const NAME_KEY='go-eschenbach-tip-name';
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const parseKickoff=(date,time)=>{
    const m=String(date||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    const t=String(time||'').match(/^(\d{1,2}):(\d{2})/);
    if(!m)return null;
    return new Date(Number(m[3]),Number(m[2])-1,Number(m[1]),t?Number(t[1]):0,t?Number(t[2]):0,0,0);
  };
  const isEschenbach=m=>/FC\s+Eschenbach\s+II/i.test(String(m?.home||''))||/FC\s+Eschenbach\s+II/i.test(String(m?.away||''));
  const clamp=v=>Math.max(0,Math.min(20,Number(v)||0));
  const cleanName=v=>String(v??'').replace(/\s+/g,' ').trim().slice(0,40);
  const validName=v=>cleanName(v).length>=2;
  const deviceId=(()=>{
    let id=localStorage.getItem(DEVICE_KEY)||'';
    if(id)return id;
    id=(crypto.randomUUID?.()||`dev-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    localStorage.setItem(DEVICE_KEY,id);
    return id;
  })();

  const buildKey=m=>[m.date,m.time||'',m.home,m.away].join('|');

  async function loadState(matchKey){
    const r=await fetch(`${API}?match_key=${encodeURIComponent(matchKey)}&voter_id=${encodeURIComponent(deviceId)}`,{cache:'no-store'});
    if(!r.ok)throw Error();
    return r.json();
  }

  async function loadResultState(match){
    const params=new URLSearchParams({
      match_date:String(match.date||''),
      home_team:String(match.home||''),
      away_team:String(match.away||''),
      final_home_goals:String(match.home_goals),
      final_away_goals:String(match.away_goals)
    });
    const r=await fetch(`${API}?${params.toString()}`,{cache:'no-store'});
    if(!r.ok)throw Error();
    return r.json();
  }

  async function saveTip(matchKey,tip,name){
    const r=await fetch(API,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        match_key:matchKey,
        voter_id:deviceId,
        display_name:cleanName(name),
        home_goals:tip.home,
        away_goals:tip.away
      })
    });
    const d=await r.json().catch(()=>({}));
    if(r.status===409&&d.error==='already_tipped')return{already:true};
    if(!r.ok)throw Error(d.error||'save_failed');
    return{ok:true};
  }

  async function saveName(matchKey,name){
    const r=await fetch(API,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        action:'set_name',
        match_key:matchKey,
        voter_id:deviceId,
        display_name:cleanName(name)
      })
    });
    if(!r.ok)throw Error();
    return r.json();
  }

  function statsText(d){
    return d.total
      ?`${d.total} ${d.total===1?'Tipp':'Tipps'}${d.top?` · häufigster Tipp ${d.top}`:''}`
      :'Noch keine Tipps – sei der Erste!';
  }

  function latestCompletedMatch(d){
    return (Array.isArray(d.recent_results)?d.recent_results:[])
      .filter(m=>isEschenbach(m)&&Number.isFinite(Number(m.home_goals))&&Number.isFinite(Number(m.away_goals)))
      .sort((a,b)=>{
        const da=parseKickoff(a.date,a.time)?.getTime()||0;
        const db=parseKickoff(b.date,b.time)?.getTime()||0;
        return db-da;
      })[0]||null;
  }

  async function mountResultCard(d,outlook){
    if(document.querySelector('.match-tip-result-card'))return;
    const match=latestCompletedMatch(d);
    if(!match)return;

    try{
      const state=await loadResultState(match);
      if(!state?.total)return;

      const winners=Array.isArray(state.winners)?state.winners.filter(Boolean):[];
      const winnerCount=Number(state.winner_count||0);
      const card=document.createElement('section');
      card.className='match-tip-result-card';

      let winnerHtml='';
      if(winnerCount>0&&winners.length){
        winnerHtml=`
          <div class="match-tip-winner-label">RICHTIG GETIPPT</div>
          <div class="match-tip-winners">${winners.map(name=>`<span>${esc(name)}</span>`).join('')}</div>
          ${winnerCount>winners.length?`<div class="match-tip-anonymous">${winnerCount-winners.length} weiterer richtiger Tipp ohne hinterlegten Namen</div>`:''}
        `;
      }else if(winnerCount>0){
        winnerHtml='<div class="match-tip-no-winner">Ein richtiger Tipp wurde ohne Namen abgegeben.</div>';
      }else{
        winnerHtml=`<div class="match-tip-no-winner">Diesmal hat niemand das Resultat <strong>${esc(match.home_goals)}:${esc(match.away_goals)}</strong> exakt getippt.</div>`;
      }

      card.innerHTML=`
        <span class="match-tip-kicker">MATCH-TIPP · AUFLÖSUNG</span>
        <h2>${esc(match.home)} – ${esc(match.away)}</h2>
        <div class="match-tip-result-score">${esc(match.home_goals)} : ${esc(match.away_goals)}</div>
        ${winnerHtml}
        <div class="match-tip-result-meta">${state.total} ${state.total===1?'abgegebener Tipp':'abgegebene Tipps'}</div>
      `;
      outlook.before(card);
    }catch{}
  }

  function mountTipCard(d,outlook){
    if(document.querySelector('.match-tip-card'))return;
    const match=Array.isArray(d.upcoming_matches)?d.upcoming_matches.find(isEschenbach):null;
    if(!match)return;

    const id=buildKey(match);
    const key='go-eschenbach-match-tip:'+id;
    const kickoff=parseKickoff(match.date,match.time);
    const locked=kickoff?Date.now()>=kickoff.getTime():false;
    const rememberedName=cleanName(localStorage.getItem(NAME_KEY)||'');

    let saved=null;
    try{saved=JSON.parse(localStorage.getItem(key)||'null')}catch{}

    const card=document.createElement('section');
    card.className='match-tip-card';
    card.innerHTML=`
      <span class="match-tip-kicker">MATCH-TIPP</span>
      <h2>Wie geht das nächste Spiel aus?</h2>
      <div class="match-tip-meta">${esc(match.date)}${match.time?` · ${esc(match.time)} Uhr`:''}</div>
      <div class="match-tip-pairing">
        <div class="match-tip-team">${esc(match.home)}</div>
        <div class="match-tip-vs">VS</div>
        <div class="match-tip-team">${esc(match.away)}</div>
      </div>
      <div class="match-tip-stats">Tipps werden geladen …</div>

      <div class="match-tip-form${saved||locked?' is-hidden':''}">
        <label class="match-tip-name-label">
          <span>Dein Name</span>
          <input class="match-tip-name" type="text" maxlength="40" autocomplete="name" placeholder="Vorname oder Name" value="${esc(rememberedName)}">
        </label>
        <div class="match-tip-name-note">Dein Name wird nur angezeigt, wenn dein Tipp genau stimmt.</div>
        <div class="match-tip-score">
          <input class="match-tip-home" type="number" inputmode="numeric" min="0" max="20" aria-label="Tore ${esc(match.home)}">
          <span class="match-tip-colon">:</span>
          <input class="match-tip-away" type="number" inputmode="numeric" min="0" max="20" aria-label="Tore ${esc(match.away)}">
        </div>
        <button class="match-tip-action" type="button">Tipp speichern</button>
      </div>

      <div class="match-tip-saved${saved?' is-visible':''}">
        <div class="match-tip-saved-label">DEIN TIPP</div>
        <div class="match-tip-saved-name">${saved?.name?esc(saved.name):''}</div>
        <div class="match-tip-saved-score">${saved?`${esc(saved.home)} : ${esc(saved.away)}`:''}</div>
        <div class="match-tip-name-repair" hidden>
          <div class="match-tip-repair-text">Damit du bei einem richtigen Tipp als Gewinner angezeigt wirst, ergänze deinen Namen.</div>
          <input class="match-tip-repair-input" type="text" maxlength="40" autocomplete="name" placeholder="Vorname oder Name" value="${esc(rememberedName)}">
          <button class="match-tip-repair-action" type="button">Name speichern</button>
        </div>
      </div>

      ${locked&&!saved?'<div class="match-tip-locked">Tipps sind für dieses Spiel geschlossen.</div>':''}
    `;

    outlook.before(card);

    const stats=card.querySelector('.match-tip-stats');
    const form=card.querySelector('.match-tip-form');
    const savedBox=card.querySelector('.match-tip-saved');
    const savedName=card.querySelector('.match-tip-saved-name');
    const savedScore=card.querySelector('.match-tip-saved-score');
    const nameInput=card.querySelector('.match-tip-name');
    const home=card.querySelector('.match-tip-home');
    const away=card.querySelector('.match-tip-away');
    const action=card.querySelector('.match-tip-action');
    const repair=card.querySelector('.match-tip-name-repair');
    const repairInput=card.querySelector('.match-tip-repair-input');
    const repairAction=card.querySelector('.match-tip-repair-action');

    const lockWithTip=tip=>{
      if(!tip)return;
      const name=cleanName(tip.name||'');
      const stored={home:Number(tip.home),away:Number(tip.away),name};
      localStorage.setItem(key,JSON.stringify(stored));
      if(name)localStorage.setItem(NAME_KEY,name);
      savedScore.textContent=`${stored.home} : ${stored.away}`;
      savedName.textContent=name;
      form.classList.add('is-hidden');
      savedBox.classList.add('is-visible');
      repair.hidden=!!name;
    };

    loadState(id).then(state=>{
      stats.textContent=statsText(state);
      if(state.mine)lockWithTip(state.mine);
      else if(saved){
        localStorage.removeItem(key);
        form.classList.toggle('is-hidden',locked);
        savedBox.classList.remove('is-visible');
      }
    }).catch(()=>{
      stats.textContent='Tipp-Zählung gerade nicht verfügbar.';
    });

    action?.addEventListener('click',async()=>{
      const name=cleanName(nameInput.value);
      if(!validName(name)){
        nameInput.classList.add('is-invalid');
        nameInput.focus();
        return;
      }
      nameInput.classList.remove('is-invalid');

      if(home.value===''||away.value===''){
        (home.value===''?home:away).focus();
        return;
      }

      const tip={home:clamp(home.value),away:clamp(away.value)};
      action.disabled=true;
      action.textContent='Speichern …';

      try{
        const result=await saveTip(id,tip,name);
        if(result.already){
          let state=await loadState(id);
          if(state.mine&&!state.mine.name){
            await saveName(id,name);
            state=await loadState(id);
          }
          stats.textContent=statsText(state);
          if(state.mine)lockWithTip(state.mine);
          else{
            form.classList.add('is-hidden');
            savedBox.classList.add('is-visible');
            savedScore.textContent='Bereits abgegeben';
          }
          return;
        }

        localStorage.setItem(NAME_KEY,name);
        lockWithTip({...tip,name});
        const state=await loadState(id);
        stats.textContent=statsText(state);
        action.textContent='Tipp gespeichert';
      }catch{
        action.textContent='Nochmals versuchen';
        action.disabled=false;
      }
    });

    repairAction?.addEventListener('click',async()=>{
      const name=cleanName(repairInput.value);
      if(!validName(name)){
        repairInput.classList.add('is-invalid');
        repairInput.focus();
        return;
      }
      repairInput.classList.remove('is-invalid');
      repairAction.disabled=true;
      repairAction.textContent='Speichern …';

      try{
        await saveName(id,name);
        localStorage.setItem(NAME_KEY,name);
        const state=await loadState(id);
        if(state.mine)lockWithTip(state.mine);
      }catch{
        repairAction.disabled=false;
        repairAction.textContent='Nochmals versuchen';
      }
    });
  }

  function mount(d){
    const app=document.getElementById('app');
    if(!app||app.querySelector('.skeleton'))return false;

    const outlook=[...app.querySelectorAll(':scope > section.card')]
      .find(s=>s.querySelector(':scope > h2')?.textContent?.trim()==='Ausblick');
    if(!outlook)return false;

    mountResultCard(d,outlook);
    mountTipCard(d,outlook);
    return true;
  }

  fetch('data/report.json?'+Date.now())
    .then(r=>r.json())
    .then(d=>{
      if(mount(d))return;
      const app=document.getElementById('app');
      if(!app)return;
      const observer=new MutationObserver(()=>{
        if(mount(d))observer.disconnect();
      });
      observer.observe(app,{childList:true,subtree:true});
    })
    .catch(()=>{});
})();