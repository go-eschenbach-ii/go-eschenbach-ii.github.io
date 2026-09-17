(()=>{
  const el=document.getElementById('bottomUpdate');
  const statusEl=document.getElementById('bottomUpdateStatus');
  if(!el)return;

  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-update-request-v2';
  const BASELINE_KEY='go-eschenbach-before-generated-at';
  const REQUEST_KEY='go-eschenbach-last-update-request';
  const ADMIN_TOKEN_KEY='go-eschenbach-comment-admin-token';
  let pollTimer=null;
  let reportWatchTimer=null;
  let holdTimer=null;
  let requestedAt=null;
  let beforeGeneratedAt='';
  let decisionPending=false;

  const setStatus=(text,state='')=>{
    if(!statusEl)return;
    statusEl.textContent=text||'';
    statusEl.dataset.state=state;
  };

  const askReviewUpdate=()=>new Promise(resolve=>{
    const overlay=document.createElement('div');
    overlay.setAttribute('role','dialog');
    overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label','Rückblick aktualisieren');
    Object.assign(overlay.style,{
      position:'fixed',inset:'0',zIndex:'99999',display:'flex',alignItems:'center',justifyContent:'center',
      padding:'24px',background:'rgba(0,0,0,.48)'
    });

    const box=document.createElement('div');
    Object.assign(box.style,{
      width:'min(360px,100%)',background:'#fff',color:'#111',borderRadius:'16px',padding:'20px',
      boxShadow:'0 18px 50px rgba(0,0,0,.28)',fontFamily:'inherit'
    });

    const title=document.createElement('div');
    title.textContent='Rückblick aktualisieren?';
    Object.assign(title.style,{fontSize:'19px',fontWeight:'700',marginBottom:'8px'});

    const text=document.createElement('div');
    text.textContent='Soll der Text «Rückblick» bei diesem Update ebenfalls erneuert werden?';
    Object.assign(text.style,{fontSize:'15px',lineHeight:'1.4',marginBottom:'18px'});

    const buttons=document.createElement('div');
    Object.assign(buttons.style,{display:'flex',gap:'10px'});

    const finish=value=>{
      document.removeEventListener('keydown',onKey);
      overlay.remove();
      resolve(value);
    };
    const onKey=e=>{
      if(e.key==='Escape')finish(false);
    };

    const no=document.createElement('button');
    no.type='button';
    no.textContent='Nein, beibehalten';
    Object.assign(no.style,{
      flex:'1',padding:'11px 10px',border:'1px solid #ccc',borderRadius:'10px',background:'#fff',
      color:'#111',font:'inherit',fontWeight:'600'
    });
    no.addEventListener('click',()=>finish(false));

    const yes=document.createElement('button');
    yes.type='button';
    yes.textContent='Ja, erneuern';
    Object.assign(yes.style,{
      flex:'1',padding:'11px 10px',border:'0',borderRadius:'10px',background:'#111',
      color:'#fff',font:'inherit',fontWeight:'700'
    });
    yes.addEventListener('click',()=>finish(true));

    buttons.append(no,yes);
    box.append(title,text,buttons);
    overlay.append(box);
    document.body.append(overlay);
    document.addEventListener('keydown',onKey);
    yes.focus();
  });

  const getReportVersion=async()=>{
    try{
      const r=await fetch(`data/report.json?updatecheck=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return'';
      const d=await r.json();
      return String(d.generated_at||'');
    }catch{return'';}
  };

  const stopPolling=()=>{
    if(pollTimer){clearTimeout(pollTimer);pollTimer=null;}
  };
  const stopReportWatch=()=>{
    if(reportWatchTimer){clearTimeout(reportWatchTimer);reportWatchTimer=null;}
  };
  const cancelHold=()=>{
    if(holdTimer){clearTimeout(holdTimer);holdTimer=null;}
  };

  const finishPublished=()=>{
    stopPolling();
    stopReportWatch();
    localStorage.removeItem(BASELINE_KEY);
    localStorage.removeItem(REQUEST_KEY);
    setStatus('Aktualisiert ✓','done');
    el.textContent='Aktualisiert';
    setTimeout(()=>location.reload(),700);
  };

  const checkPublishedReport=async()=>{
    const current=await getReportVersion();
    if(current && beforeGeneratedAt && current!==beforeGeneratedAt){
      finishPublished();
      return true;
    }
    return false;
  };

  const watchPublishedReport=(started=Date.now())=>{
    stopReportWatch();
    const tick=async()=>{
      if(await checkPublishedReport())return;
      if(Date.now()-started>=150000)return;
      reportWatchTimer=setTimeout(tick,4000);
    };
    tick();
  };

  const waitForPublishedReport=async()=>{
    setStatus('Bericht wird veröffentlicht …','publishing');
    if(await checkPublishedReport())return;
    watchPublishedReport();
    setTimeout(()=>{
      if(reportWatchTimer){
        stopReportWatch();
        setStatus('Aktualisiert. App kurz neu öffnen.','done');
        el.textContent='Update';
        el.disabled=false;
      }
    },150000);
  };

  const poll=async()=>{
    stopPolling();
    try{
      const r=await fetch(`${API}?t=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)throw Error();
      const d=await r.json();
      if(d.pending){
        if(d.phase==='running')setStatus('Aktualisierung läuft …','running');
        else setStatus('Update startet …','running');
        pollTimer=setTimeout(poll,7000);
        return;
      }

      const completedAt=d.completed_at?new Date(d.completed_at).getTime():0;
      const failedAt=d.failed_at?new Date(d.failed_at).getTime():0;
      const reqTime=requestedAt?new Date(requestedAt).getTime():0;
      if(failedAt && (!reqTime||failedAt>=reqTime)){
        stopReportWatch();
        setStatus('Aktualisierung fehlgeschlagen. Bitte nochmals versuchen.','error');
        el.textContent='Update';
        el.disabled=false;
        return;
      }
      if(completedAt && (!reqTime||completedAt>=reqTime)){
        await waitForPublishedReport();
        return;
      }
      pollTimer=setTimeout(poll,7000);
    }catch{
      setStatus('Verbindung wird erneut geprüft …','running');
      pollTimer=setTimeout(poll,10000);
    }
  };

  const setupGitHub=async()=>{
    const token=window.prompt('Einmalige Einrichtung: Füge deinen GitHub Fine-grained Token ein. Er wird nicht auf dem iPhone gespeichert.');
    if(!token)return false;
    const code=window.prompt('Gib den einmaligen Setup-Code ein:');
    if(!code)return false;
    setStatus('GitHub wird verbunden …','running');
    try{
      const r=await fetch(API,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'setup',github_token:token.trim(),setup_code:code.trim()})
      });
      const d=await r.json().catch(()=>({}));
      if(!r.ok||!d.configured){
        setStatus(d.error==='wrong_setup_code'?'Setup-Code stimmt nicht.':'GitHub-Verbindung konnte nicht eingerichtet werden.','error');
        return false;
      }
      setStatus('GitHub verbunden ✓','done');
      return true;
    }catch{
      setStatus('GitHub-Verbindung konnte nicht eingerichtet werden.','error');
      return false;
    }
  };

  const requestUpdate=async(updateReview=null)=>{
    if(el.disabled||decisionPending)return;
    if(updateReview===null){
      decisionPending=true;
      try{
        updateReview=await askReviewUpdate();
      }finally{
        decisionPending=false;
      }
    }
    if(el.disabled)return;

    el.disabled=true;
    el.textContent='Startet …';
    setStatus(updateReview?'Update wird gestartet …':'Update wird gestartet – Rückblick bleibt bestehen …','running');
    beforeGeneratedAt=await getReportVersion();
    if(beforeGeneratedAt)localStorage.setItem(BASELINE_KEY,beforeGeneratedAt);
    try{
      const adminToken=localStorage.getItem(ADMIN_TOKEN_KEY)||'';
      let r=await fetch(API,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'request',admin_token:adminToken,update_review:updateReview})
      });
      let d=await r.json().catch(()=>({}));

      if(r.status===503&&d.setup_required){
        el.disabled=false;
        el.textContent='Update';
        setStatus('Einmalige GitHub-Verbindung nötig.','info');
        const configured=await setupGitHub();
        if(configured)setTimeout(()=>requestUpdate(updateReview),400);
        return;
      }
      if(r.status===429){
        const mins=Math.max(1,Math.ceil(Number(d.cooldown_seconds||60)/60));
        setStatus(`Bereits kürzlich aktualisiert. In ca. ${mins} Min. wieder möglich.`,'info');
        el.textContent='Update';
        el.disabled=false;
        return;
      }
      if(!r.ok||!d.pending)throw Error();
      requestedAt=d.requested_at||new Date().toISOString();
      localStorage.setItem(REQUEST_KEY,requestedAt);
      const comments=Number(d.comments_count||0);
      if(comments>0){
        setStatus(updateReview
          ?`Update mit ${comments} Matchkommentar${comments===1?'':'en'} gestartet …`
          :`Update mit ${comments} Matchkommentar${comments===1?'':'en'} gestartet – Rückblick bleibt bestehen …`,'running');
      }else{
        setStatus(updateReview
          ?(d.phase==='running'?'Aktualisierung läuft …':'Update gestartet …')
          :(d.phase==='running'?'Aktualisierung läuft – Rückblick bleibt bestehen …':'Update gestartet – Rückblick bleibt bestehen …'),'running');
      }
      el.textContent='Läuft …';
      watchPublishedReport();
      poll();
    }catch{
      stopReportWatch();
      setStatus('Update konnte nicht gestartet werden.','error');
      el.textContent='Update';
      el.disabled=false;
    }
  };

  el.addEventListener('click',e=>e.preventDefault());
  el.addEventListener('contextmenu',e=>e.preventDefault());
  el.addEventListener('pointerdown',()=>{
    cancelHold();
    if(el.disabled||decisionPending)return;
    holdTimer=setTimeout(()=>{holdTimer=null;requestUpdate();},1200);
  });
  el.addEventListener('pointerup',cancelHold);
  el.addEventListener('pointercancel',cancelHold);
  el.addEventListener('pointerleave',cancelHold);

  (async()=>{
    try{
      const r=await fetch(`${API}?t=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return;
      const d=await r.json();
      if(d.pending){
        beforeGeneratedAt=localStorage.getItem(BASELINE_KEY)||await getReportVersion();
        requestedAt=d.requested_at||localStorage.getItem(REQUEST_KEY);
        el.disabled=true;
        el.textContent='Läuft …';
        setStatus(d.phase==='running'?'Aktualisierung läuft …':'Update startet …','running');
        watchPublishedReport();
        poll();
      }else{
        beforeGeneratedAt=localStorage.getItem(BASELINE_KEY)||'';
        if(beforeGeneratedAt && await checkPublishedReport())return;
        localStorage.removeItem(BASELINE_KEY);
        localStorage.removeItem(REQUEST_KEY);
      }
    }catch{}
  })();
})();
