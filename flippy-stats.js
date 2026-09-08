(()=>{
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const isEschenbach=m=>/FC\s+Eschenbach\s+II/i.test(String(m?.home||''))||/FC\s+Eschenbach\s+II/i.test(String(m?.away||''));

  const dateValue=value=>{
    const m=String(value||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return m?new Date(Number(m[3]),Number(m[2])-1,Number(m[1])).getTime():Number.MAX_SAFE_INTEGER;
  };

  const outcomeFromResult=value=>{
    const m=String(value||'').match(/(\d+)\s*[:\-]\s*(\d+)/);
    if(!m)return null;
    const a=Number(m[1]),b=Number(m[2]);
    return a>b?'win':a===b?'draw':'loss';
  };

  const outcomeFromRecent=m=>{
    if(!isEschenbach(m)||m?.home_goals==null||m?.away_goals==null)return null;
    const home=/FC\s+Eschenbach\s+II/i.test(String(m.home||''));
    const own=home?Number(m.home_goals):Number(m.away_goals);
    const opp=home?Number(m.away_goals):Number(m.home_goals);
    return own>opp?'win':own===opp?'draw':'loss';
  };

  function seasonTimeline(d){
    const e=d?.eschenbach||{};
    const played=Math.max(0,Number(e.played)||0);
    const teamCount=Array.isArray(d?.standings)?d.standings.length:0;
    const eschenbachUpcoming=Array.isArray(d?.upcoming_matches)?d.upcoming_matches.filter(isEschenbach).length:0;
    const total=Math.max(
      played,
      teamCount>1?(teamCount-1)*2:0,
      played+eschenbachUpcoming,
      5
    );

    const audit=Array.isArray(d?.scorer_audit?.checked_matches)?[...d.scorer_audit.checked_matches]:[];
    audit.sort((a,b)=>dateValue(a.date)-dateValue(b.date));
    let results=audit.map(x=>outcomeFromResult(x.result)).filter(Boolean);

    // Falls bei einem Update einzelne Audit-Spiele fehlen, ergänzen wir bekannte
    // aktuelle Resultate chronologisch, ohne bereits vorhandene Daten zu verdoppeln.
    if(results.length<played&&Array.isArray(d?.recent_results)){
      const knownDates=new Set(audit.map(x=>String(x.date||'')));
      const extra=d.recent_results
        .filter(isEschenbach)
        .filter(x=>!knownDates.has(String(x.date||'')))
        .sort((a,b)=>dateValue(a.date)-dateValue(b.date))
        .map(outcomeFromRecent)
        .filter(Boolean);
      results=[...results,...extra];
    }

    // Letzte Absicherung über die Tabellenwerte. Im Normalfall wird dieser Block
    // nicht benötigt, da scorer_audit alle bisherigen Eschenbach-Spiele enthält.
    if(results.length<played){
      const target={win:Number(e.wins)||0,draw:Number(e.draws)||0,loss:Number(e.losses)||0};
      const have=results.reduce((a,x)=>(a[x]=(a[x]||0)+1,a),{win:0,draw:0,loss:0});
      ['win','draw','loss'].forEach(type=>{
        const missing=Math.max(0,(target[type]||0)-(have[type]||0));
        for(let i=0;i<missing&&results.length<played;i++)results.push(type);
      });
    }

    results=results.slice(0,played);
    while(results.length<played)results.push('loss');
    while(results.length<total)results.push('future');
    return{results,total};
  }

  const markLabel=(state,index)=>{
    const text=state==='win'?'Sieg':state==='draw'?'Unentschieden':state==='loss'?'Niederlage':'noch nicht gespielt';
    return `Spiel ${index+1}: ${text}`;
  };

  const enhance=(d)=>{
    const grid=document.querySelector('#app .grid');
    if(!grid||grid.classList.contains('stats-flip'))return false;
    const cards=[...grid.querySelectorAll('.stat')];
    if(cards.length<3)return false;
    const rank=cards[0].querySelector('strong')?.textContent?.trim()||'–';
    const points=cards[1].querySelector('strong')?.textContent?.trim()||'–';
    const winsRaw=cards[2].querySelector('strong')?.textContent?.trim()||'0';
    const leader=rank==='#1'?'LEADER':`RANG ${rank.replace('#','')}`;
    const timeline=seasonTimeline(d||{});
    const marks=timeline.results.map((state,i)=>`<span class="wins-mark ${state}" title="${esc(markLabel(state,i))}"></span>`).join('');
    const timelineLabel=timeline.results.map((state,i)=>markLabel(state,i)).join(', ');

    grid.classList.add('stats-flip');
    grid.innerHTML=`
      <div class="stat stat-rank" aria-label="${esc(rank)} Rang">
        <span class="rank-sticker">${esc(leader)}</span>
        <strong class="rank-number">${esc(rank)}</strong>
        <span class="rank-label">Rang</span>
      </div>
      <div class="stat stat-points" aria-label="${esc(points)} Punkte">
        <div class="points-orbit"><strong class="points-number">${esc(points)}</strong></div>
        <div class="points-copy"><b>Punkte</b><small>Saison 26/27</small></div>
        <span class="points-label">Punktestand</span>
      </div>
      <div class="stat stat-wins" aria-label="${esc(winsRaw)} Siege">
        <strong class="wins-number">${esc(winsRaw)}</strong>
        <div class="wins-copy"><b>SIEGE</b><small>Saisonsiege</small><div class="wins-marks" style="--season-games:${timeline.total}" role="img" aria-label="${esc(timelineLabel)}">${marks}</div></div>
      </div>`;
    return true;
  };

  const waitForGrid=d=>{
    if(enhance(d))return;
    const target=document.getElementById('app');
    if(target){
      const observer=new MutationObserver(()=>{if(enhance(d))observer.disconnect();});
      observer.observe(target,{childList:true,subtree:true});
    }
  };

  fetch(`data/report.json?stats=${Date.now()}`,{cache:'no-store'})
    .then(r=>r.ok?r.json():{})
    .then(waitForGrid)
    .catch(()=>waitForGrid({}));

  if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js?v=17').catch(()=>{});}
})();
