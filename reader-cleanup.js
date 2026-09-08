(()=>{
  const isEschenbachMatch=match=>/FC\s+Eschenbach\s+II/i.test(String(match?.home||''))||/FC\s+Eschenbach\s+II/i.test(String(match?.away||''));
  const scorerTextPattern=/(Torschütz|Tore?\s+für|Treffer\s+für|traf(?:en)?\b)/i;

  const scorerNoteFromAudit=(match,auditMatches)=>{
    if(!isEschenbachMatch(match))return'';
    const opponent=/FC\s+Eschenbach\s+II/i.test(String(match.home||''))?String(match.away||''):String(match.home||'');
    const audit=(auditMatches||[]).find(a=>String(a?.date||'')===String(match.date||'')&&String(a?.opponent||'').trim()===opponent.trim());
    if(!audit)return scorerTextPattern.test(String(match.note||''))?String(match.note||'').trim():'';
    const scorers=String(audit.scorers||'').trim();
    let note=scorers?`Tore für Eschenbach II: ${scorers}.`:'';
    const own=Math.max(0,Number(audit.own_goals)||0);
    if(own===1)note+=`${note?' ':''}Dazu kam ein Eigentor zugunsten von Eschenbach.`;
    if(own>1)note+=`${note?' ':''}Dazu kamen ${own} Eigentore zugunsten von Eschenbach.`;
    return note;
  };

  const kickoffValue=match=>{
    const dm=String(match?.date||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if(!dm)return Number.MAX_SAFE_INTEGER;
    const tm=String(match?.time||'00:00').match(/^(\d{1,2}):(\d{2})$/);
    return new Date(Number(dm[3]),Number(dm[2])-1,Number(dm[1]),tm?Number(tm[1]):0,tm?Number(tm[2]):0,0,0).getTime();
  };

  const prepareReport=data=>{
    if(!data||typeof data!=='object')return data;
    const auditMatches=Array.isArray(data.scorer_audit?.checked_matches)?data.scorer_audit.checked_matches:[];
    if(Array.isArray(data.recent_results)){
      data.recent_results=data.recent_results.map(match=>({...match,note:scorerNoteFromAudit(match,auditMatches)}));
    }
    if(Array.isArray(data.upcoming_matches)){
      data.upcoming_matches=data.upcoming_matches
        .map(match=>({...match,note:''}))
        .sort((a,b)=>kickoffValue(a)-kickoffValue(b));
    }
    return data;
  };

  const originalFetch=window.fetch.bind(window);
  window.fetch=async(...args)=>{
    const response=await originalFetch(...args);
    const requestUrl=String(typeof args[0]==='string'?args[0]:args[0]?.url||'');
    if(!requestUrl.includes('data/report.json'))return response;
    try{
      const data=prepareReport(await response.clone().json());
      return new Response(JSON.stringify(data),{status:response.status,statusText:response.statusText,headers:response.headers});
    }catch{
      return response;
    }
  };

  const cleanVisibleNotes=()=>{
    const app=document.getElementById('app');
    if(!app)return false;
    app.querySelectorAll('.review-card .match,.outlook-card .match').forEach(row=>{
      const notes=[...row.querySelectorAll(':scope > .muted')];
      if(notes.length<2)return;
      const note=notes[notes.length-1];
      const isEschenbach=/FC\s+Eschenbach\s+II/i.test(row.textContent||'');
      if(!isEschenbach||!scorerTextPattern.test(note.textContent||''))note.remove();
    });
    return true;
  };

  cleanVisibleNotes();
  const target=document.getElementById('app');
  if(target){
    const observer=new MutationObserver(()=>cleanVisibleNotes());
    observer.observe(target,{childList:true,subtree:true});
  }
})();
