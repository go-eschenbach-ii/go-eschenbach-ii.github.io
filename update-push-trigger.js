(()=>{
  const statusEl=document.getElementById('bottomUpdateStatus');
  if(!statusEl)return;
  const PUSH_API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/update-push';
  const ADMIN_TOKEN_KEY='go-eschenbach-comment-admin-token';
  let lastText='';

  const maybeSend=()=>{
    const text=(statusEl.textContent||'').trim();
    if(text===lastText)return;
    lastText=text;
    if(!/^Aktualisiert\b/i.test(text))return;
    const adminToken=localStorage.getItem(ADMIN_TOKEN_KEY)||'';
    if(!adminToken)return;
    fetch(PUSH_API,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({admin_token:adminToken}),
      keepalive:true
    }).catch(()=>{});
  };

  new MutationObserver(maybeSend).observe(statusEl,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['data-state']});
  maybeSend();
})();
