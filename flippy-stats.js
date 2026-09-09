(()=>{
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function seasonTimeline(d){
    const e=d?.eschenbach||{};
    const played=Math.max(0,Number(e.played)||0);
    const wins=Math.max(0,Math.min(played,Number(e.wins)||0));
    const draws=Math.max(0,Math.min(played-wins,Number(e.draws)||0));
    const reportedLosses=Math.max(0,Number(e.losses)||0);
    const losses=Math.max(0,Math.min(played-wins-draws,reportedLosses));
    const accounted=wins+draws+losses;
    const remainingPlayed=Math.max(0,played-accounted);

    const teamCount=Array.isArray(d?.standings)?d.standings.length:0;
    const total=Math.max(
      played,
      teamCount>1?(teamCount-1)*2:0,
      5
    );

    // Die Balken werden bei jedem geladenen Bericht direkt aus den aktuellen
    // Saisonwerten neu aufgebaut. Dadurch gilt immer:
    // Sieg = gelb, Unentschieden = halb gelb/halb grau, Niederlage = grau.
    // Nicht gespielte Partien bleiben ebenfalls grau.
    const results=[
      ...Array(wins).fill('win'),
      ...Array(draws).fill('draw'),
      ...Array(losses+remainingPlayed).fill('loss')
    ];
    while(results.length<total)results.push('future');
    return{results,total,wins,draws,losses:losses+remainingPlayed,played};
  }

  const markLabel=(state,index)=>{
    const text=state==='win'?'Sieg':state==='draw'?'Unentschieden':state==='loss'?'Niederlage':'noch nicht gespielt';
    return `Balken ${index+1}: ${text}`;
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
    const timelineLabel=`${timeline.wins} Siege, ${timeline.draws} Unentschieden, ${timeline.losses} Niederlagen, ${Math.max(0,timeline.total-timeline.played)} noch nicht gespielt`;

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

  if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js?v=22').catch(()=>{});}
})();
