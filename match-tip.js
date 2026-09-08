(()=>{
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/match-tips-public';
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt',"'":'&#39;','"':'&quot;'}[c]));
  const parseKickoff=(date,time)=>{const m=String(date||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);const t=String(time||'').match(/^(\d{1,2}):(\d{2})/);if(!m)return null;return new Date(Number(m[3]),Number(m[2])-1,Number(m[1]),t?Number(t[1]):0,t?Number(t[2]):0,0,0)};
  const isEschenbach=m=>/FC\s+Eschenbach\s+II/i.test(String(m?.home||''))||/FC\s+Eschenbach\s+II/i.test(String(m?.away||''));
  const clamp=v=>Math.max(0,Math.min(20,Number(v)||0));
  async function loadStats(matchKey,box){try{const r=await fetch(`${API}?match_key=${encodeURIComponent(matchKey)}`);if(!r.ok)throw Error();const d=await r.json();box.textContent=d.total?`${d.total} ${d.total===1?'Tipp':'Tipps'}${d.top?` · häufigster Tipp ${d.top}`:''}`:'Noch keine Tipps – sei der Erste!'}catch{box.textContent='Tipp-Zählung gerade nicht verfügbar.'}}
  async function saveTip(matchKey,tip){const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({match_key:matchKey,home_goals:tip.home,away_goals:tip.away})});if(!r.ok)throw Error()}
  function mount(d){
    if(document.querySelector('.match-tip-card'))return true;
    const match=Array.isArray(d.upcoming_matches)?d.upcoming_matches.find(isEschenbach):null;if(!match)return false;
    const app=document.getElementById('app');if(!app)return false;
    const outlook=[...app.querySelectorAll(':scope > section.card')].find(s=>s.querySelector(':scope > h2')?.textContent?.trim()==='Ausblick');if(!outlook)return false;
    const id=[match.date,match.time,match.home,match.away].join('|');const key='go-eschenbach-match-tip:'+id;
    const kickoff=parseKickoff(match.date,match.time);const locked=kickoff?Date.now()>=kickoff.getTime():false;
    let saved=null;try{saved=JSON.parse(localStorage.getItem(key)||'null')}catch{}
    const card=document.createElement('section');card.className='match-tip-card';card.innerHTML=`<span class="match-tip-kicker">MATCH-TIPP</span><h2>Wie geht das nächste Spiel aus?</h2><div class="match-tip-meta">${esc(match.date)}${match.time?` · ${esc(match.time)} Uhr`:''}</div><div class="match-tip-pairing"><div class="match-tip-team">${esc(match.home)}</div><div class="match-tip-vs">VS</div><div class="match-tip-team">${esc(match.away)}</div></div><div class="match-tip-stats">Tipps werden geladen …</div><div class="match-tip-form${saved||locked?' is-hidden':''}"><div class="match-tip-score"><input class="match-tip-home" type="number" inputmode="numeric" min="0" max="20" aria-label="Tore ${esc(match.home)}"><span class="match-tip-colon">:</span><input class="match-tip-away" type="number" inputmode="numeric" min="0" max="20" aria-label="Tore ${esc(match.away)}"></div><button class="match-tip-action" type="button">Tipp speichern</button></div><div class="match-tip-saved${saved?' is-visible':''}"><div class="match-tip-saved-label">DEIN TIPP</div><div class="match-tip-saved-score">${saved?`${esc(saved.home)} : ${esc(saved.away)}`:''}</div>${!locked?'<button class="match-tip-change" type="button">Tipp ändern</button>':''}</div>${locked&&!saved?'<div class="match-tip-locked">Tipps sind für dieses Spiel geschlossen.</div>':''}`;
    outlook.before(card);
    const stats=card.querySelector('.match-tip-stats'),form=card.querySelector('.match-tip-form'),savedBox=card.querySelector('.match-tip-saved'),savedScore=card.querySelector('.match-tip-saved-score'),home=card.querySelector('.match-tip-home'),away=card.querySelector('.match-tip-away'),action=card.querySelector('.match-tip-action'),change=card.querySelector('.match-tip-change');
    loadStats(id,stats);
    action?.addEventListener('click',async()=>{if(home.value===''||away.value===''){(home.value===''?home:away).focus();return}const tip={home:clamp(home.value),away:clamp(away.value)};action.disabled=true;action.textContent='Speichern …';try{await saveTip(id,tip);localStorage.setItem(key,JSON.stringify(tip));savedScore.textContent=`${tip.home} : ${tip.away}`;form.classList.add('is-hidden');savedBox.classList.add('is-visible');await loadStats(id,stats);action.textContent='Tipp gespeichert'}catch{action.textContent='Nochmals versuchen'}finally{action.disabled=false}});
    change?.addEventListener('click',()=>{let tip=null;try{tip=JSON.parse(localStorage.getItem(key)||'null')}catch{}if(tip){home.value=tip.home;away.value=tip.away}savedBox.classList.remove('is-visible');form.classList.remove('is-hidden');action.textContent='Tipp speichern';home.focus()});
    return true;
  }
  fetch('data/report.json?'+Date.now()).then(r=>r.json()).then(d=>{if(mount(d))return;const app=document.getElementById('app');if(!app)return;const observer=new MutationObserver(()=>{if(mount(d))observer.disconnect()});observer.observe(app,{childList:true,subtree:true})}).catch(()=>{});
})();