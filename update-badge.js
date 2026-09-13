(()=>{
  const SUBSCRIBE_API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/push-subscribe';
  const VAPID_PUBLIC_KEY='BD0T9vv-U9TB7ykrqZXih1XkQgVQrl9il1uURiqGLq7ZL840hIpcJ6iLiA3Rn9XrX3HjKD8uWE-1ErFc7i6k81c';
  const LAST_SEEN_KEY='go-eschenbach-last-seen-report';
  const hero=document.querySelector('.hero');
  if(!hero||!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window))return;

  const standalone=window.matchMedia?.('(display-mode: standalone)').matches||window.navigator.standalone===true;
  if(!standalone)return;

  const topNotice=(className,html)=>{
    const existing=document.querySelector(`.${className}`);
    if(existing)return existing;
    const el=document.createElement('div');
    el.className=`update-top-wrap ${className}`;
    el.innerHTML=html;
    hero.insertAdjacentElement('afterend',el);
    return el;
  };

  const decodeKey=value=>{
    const pad='='.repeat((4-value.length%4)%4);
    const raw=atob((value+pad).replace(/-/g,'+').replace(/_/g,'/'));
    return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)));
  };

  const sendSubscription=async subscription=>{
    const r=await fetch(SUBSCRIBE_API,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'subscribe',subscription:subscription.toJSON()})
    });
    if(!r.ok)throw Error('subscription_failed');
  };

  const ensureSubscription=async()=>{
    const registration=await navigator.serviceWorker.ready;
    let subscription=await registration.pushManager.getSubscription();
    if(!subscription){
      subscription=await registration.pushManager.subscribe({
        userVisibleOnly:true,
        applicationServerKey:decodeKey(VAPID_PUBLIC_KEY)
      });
    }
    await sendSubscription(subscription);
    return subscription;
  };

  const clearBadge=()=>{
    if('clearAppBadge' in navigator)navigator.clearAppBadge().catch(()=>{});
  };
  clearBadge();
  window.addEventListener('pageshow',clearBadge);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')clearBadge();});

  const formatVersion=value=>{
    const text=String(value||'').trim();
    const m=text.match(/^(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{2}:\d{2}))?/);
    return m?`${m[1]}${m[2]?` · ${m[2]} Uhr`:''}`:text;
  };

  const checkFreshReport=async()=>{
    try{
      const r=await fetch(`data/report.json?fresh=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return;
      const d=await r.json();
      const version=String(d.generated_at||'').trim();
      if(!version)return;
      const previous=localStorage.getItem(LAST_SEEN_KEY)||'';
      if(previous&&previous!==version){
        const notice=topNotice('update-fresh-notice',`<div class="update-fresh-card"><span class="update-fresh-one">1</span><div><strong>Neuer Bericht verfügbar</strong><small>Update vom ${formatVersion(version)}</small></div><button type="button" aria-label="Update-Hinweis schliessen">×</button></div>`);
        notice.querySelector('button')?.addEventListener('click',()=>notice.remove());
      }
      localStorage.setItem(LAST_SEEN_KEY,version);
    }catch{}
  };
  checkFreshReport();

  if(Notification.permission==='granted'){
    ensureSubscription().catch(()=>{});
    return;
  }
  if(Notification.permission==='denied')return;

  const prompt=topNotice('update-badge-prompt','<button type="button" class="update-badge-enable"><span class="update-badge-dot">1</span><span>Rote 1 bei neuen Updates aktivieren</span></button>');
  const button=prompt.querySelector('button');
  if(!button)return;

  button.addEventListener('click',async()=>{
    button.disabled=true;
    try{
      const permission=await Notification.requestPermission();
      if(permission!=='granted'){
        prompt.remove();
        return;
      }
      await ensureSubscription();
      button.innerHTML='<span class="update-badge-check">✓</span><span>Update-Hinweise aktiviert</span>';
      setTimeout(()=>prompt.remove(),1600);
    }catch{
      button.disabled=false;
      button.lastElementChild.textContent='Aktivierung nochmals versuchen';
    }
  });
})();
