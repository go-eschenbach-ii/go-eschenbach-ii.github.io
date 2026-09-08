(()=>{
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/match-comments-admin';
  const TOKEN_KEY='go-eschenbach-comment-admin-token';
  const TAP_LIMIT=5;
  const TAP_WINDOW=2600;
  let taps=[];
  let activating=false;

  async function activate(){
    if(activating||localStorage.getItem(TOKEN_KEY))return;
    activating=true;
    const code=window.prompt('Kommentar-Modus freischalten: Einmaligen Aktivierungscode eingeben');
    if(!code){activating=false;return;}
    try{
      const r=await fetch(API,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'activate',activation_code:code.trim(),label:'Marc iPhone'})
      });
      const d=await r.json().catch(()=>({}));
      if(!r.ok||!d.admin_token){
        window.alert('Aktivierungscode stimmt nicht oder wurde bereits verwendet.');
        activating=false;
        return;
      }
      localStorage.setItem(TOKEN_KEY,d.admin_token);
      window.alert('Kommentar-Modus ist auf diesem Gerät freigeschaltet. Die App wird neu geladen.');
      window.location.reload();
    }catch{
      window.alert('Freischaltung konnte gerade nicht abgeschlossen werden.');
      activating=false;
    }
  }

  function registerTap(){
    if(localStorage.getItem(TOKEN_KEY))return;
    const now=Date.now();
    taps=taps.filter(t=>now-t<TAP_WINDOW);
    taps.push(now);
    if(taps.length>=TAP_LIMIT){
      taps=[];
      activate();
    }
  }

  function install(){
    const title=document.querySelector('.hero h1');
    const logo=document.getElementById('logoButton');
    const logoImg=logo?.querySelector('img');

    [title,logo,logoImg].filter(Boolean).forEach(el=>{
      el.style.webkitUserSelect='none';
      el.style.userSelect='none';
      el.style.webkitTouchCallout='none';
      el.style.touchAction='manipulation';
    });

    title?.addEventListener('click',registerTap);

    logo?.addEventListener('click',e=>{
      if(localStorage.getItem(TOKEN_KEY))return;
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      registerTap();
    },true);

    logo?.addEventListener('contextmenu',e=>{
      if(localStorage.getItem(TOKEN_KEY))return;
      e.preventDefault();
    },true);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
