(()=>{
  const host=document.getElementById('urgentAlertHost');
  if(!host)return;

  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const isActive=alert=>{
    if(!alert||alert.active!==true)return false;
    const from=alert.active_from?new Date(alert.active_from).getTime():0;
    const until=alert.active_until?new Date(alert.active_until).getTime():Infinity;
    const now=Date.now();
    return Number.isFinite(from)&&Number.isFinite(until)&&now>=from&&now<=until;
  };

  const setBadge=async value=>{
    try{
      if(value>0&&'setAppBadge' in navigator)await navigator.setAppBadge(value);
      if(value<=0&&'clearAppBadge' in navigator)await navigator.clearAppBadge();
    }catch{}
  };

  fetch('data/alert.json?'+Date.now(),{cache:'no-store'})
    .then(r=>{if(!r.ok)throw Error();return r.json()})
    .then(alert=>{
      if(!isActive(alert)){
        host.hidden=true;
        setBadge(0);
        return;
      }
      host.innerHTML=`
        <div class="urgent-alert-card" role="alert">
          <div class="urgent-alert-icon" aria-hidden="true">!</div>
          <div class="urgent-alert-copy">
            <div class="urgent-alert-title">${esc(alert.title||'Wichtige Meldung')}</div>
            <p class="urgent-alert-text">${esc(alert.message||'')}</p>
            ${alert.meta?`<span class="urgent-alert-meta">${esc(alert.meta)}</span>`:''}
          </div>
        </div>`;
      host.hidden=false;
      setBadge(Math.max(1,Number(alert.badge)||1));
    })
    .catch(()=>{});
})();
