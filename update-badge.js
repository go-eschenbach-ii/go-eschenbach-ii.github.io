(()=>{
  const SUBSCRIBE_API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/push-subscribe';
  const VAPID_PUBLIC_KEY='BD0T9vv-U9TB7ykrqZXih1XkQgVQrl9il1uURiqGLq7ZL840hIpcJ6iLiA3Rn9XrX3HjKD8uWE-1ErFc7i6k81c';
  const footer=document.querySelector('footer');
  if(!footer||!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window))return;

  const standalone=window.matchMedia?.('(display-mode: standalone)').matches||window.navigator.standalone===true;
  if(!standalone)return;

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

  if(Notification.permission==='granted'){
    ensureSubscription().catch(()=>{});
    return;
  }
  if(Notification.permission==='denied')return;

  const button=document.createElement('button');
  button.type='button';
  button.className='update-badge-enable';
  button.innerHTML='<span class="update-badge-dot">1</span><span>Rote 1 bei neuen Updates aktivieren</span>';
  footer.appendChild(button);

  button.addEventListener('click',async()=>{
    button.disabled=true;
    try{
      const permission=await Notification.requestPermission();
      if(permission!=='granted'){
        button.remove();
        return;
      }
      await ensureSubscription();
      button.innerHTML='<span class="update-badge-check">✓</span><span>Update-Hinweise aktiviert</span>';
      setTimeout(()=>button.remove(),1600);
    }catch{
      button.disabled=false;
      button.lastElementChild.textContent='Aktivierung nochmals versuchen';
    }
  });
})();
