(()=>{
  const REST='https://kfpxheegmeupnuzqjqqt.supabase.co/rest/v1/rpc';
  const API_KEY='sb_publishable_vlP2dIHDTK-VY5LK-jeS_w_tN04WaK0';
  const TOKEN_KEY='go-eschenbach-comment-admin-token';
  const DEVICE_KEY='go-eschenbach-anon-device-id-v1';

  async function rpc(name,body={}){
    const r=await fetch(`${REST}/${name}`,{
      method:'POST',
      headers:{'Content-Type':'application/json','apikey':API_KEY},
      body:JSON.stringify(body),
      cache:'no-store'
    });
    if(!r.ok)throw new Error('analytics_rpc');
    return r.json();
  }

  function uuid(){
    if(crypto?.randomUUID)return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
      const r=Math.random()*16|0;
      const v=c==='x'?r:(r&0x3|0x8);
      return v.toString(16);
    });
  }

  function getDeviceId(){
    try{
      let id=localStorage.getItem(DEVICE_KEY)||'';
      if(!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)){
        id=uuid();
        localStorage.setItem(DEVICE_KEY,id);
      }
      return id;
    }catch{
      return uuid();
    }
  }

  function isStandalone(){
    return window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;
  }

  function injectStyles(){
    if(document.getElementById('appAnalyticsStyles'))return;
    const style=document.createElement('style');
    style.id='appAnalyticsStyles';
    style.textContent=`
      .admin-analytics-card{border:2px solid #111;background:#fffdf1}
      .admin-analytics-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
      .admin-analytics-head h2{margin:0}
      .admin-analytics-badge{font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;background:#111;color:#f4c400;padding:5px 8px;border-radius:999px;white-space:nowrap}
      .admin-analytics-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
      .admin-analytics-stat{background:#fff;border:1px solid #e5e7eb;border-radius:13px;padding:11px;text-align:center}
      .admin-analytics-stat strong{display:block;font-size:23px;line-height:1.05}
      .admin-analytics-stat span{display:block;margin-top:4px;font-size:11px;color:#6b7280}
      .admin-analytics-stat.install{background:#fff4f4;border-color:#f3c2c2}
      .admin-analytics-note{margin-top:10px;font-size:11px;line-height:1.35;color:#6b7280}
      .admin-analytics-details{margin-top:12px;border-top:1px solid #e5e7eb;padding-top:10px}
      .admin-analytics-details summary{cursor:pointer;font-weight:800;font-size:13px}
      .admin-analytics-days{margin-top:8px;display:grid;gap:5px}
      .admin-analytics-day{display:flex;justify-content:space-between;gap:12px;font-size:13px;padding:5px 0;border-bottom:1px solid #f0f0f0}
      .admin-analytics-day:last-child{border-bottom:0}
      @media(max-width:600px){
        .admin-analytics-grid{grid-template-columns:repeat(2,1fr)}
        .admin-analytics-stat{padding:9px 5px}
        .admin-analytics-stat strong{font-size:20px}
        .admin-analytics-stat span{font-size:10px}
      }
    `;
    document.head.appendChild(style);
  }

  function mount(stats){
    if(!stats?.ok||document.getElementById('adminAppAnalytics'))return true;
    const app=document.getElementById('app');
    if(!app||app.querySelector('.skeleton'))return false;

    const daily=Array.isArray(stats.daily)?stats.daily:[];
    const today=Number(stats.today?.users??stats.today?.opens??0);
    const yesterday=Number(stats.yesterday??daily[1]?.users??daily[1]?.opens??0);
    const seven=Number(stats.users_7d??daily.slice(0,7).reduce((sum,d)=>sum+Number(d.users??d.opens??0),0));
    const fourteen=Number(stats.users_14d??daily.slice(0,14).reduce((sum,d)=>sum+Number(d.users??d.opens??0),0));
    const installed=Number(stats.standalone_devices||0);

    injectStyles();
    const card=document.createElement('section');
    card.className='card admin-analytics-card';
    card.id='adminAppAnalytics';
    card.innerHTML=`
      <div class="admin-analytics-head">
        <h2>📊 App-Statistik</h2>
        <span class="admin-analytics-badge">Nur Admin</span>
      </div>
      <div class="admin-analytics-grid">
        <div class="admin-analytics-stat"><strong>${today}</strong><span>Nutzer heute</span></div>
        <div class="admin-analytics-stat"><strong>${yesterday}</strong><span>gestern</span></div>
        <div class="admin-analytics-stat"><strong>${seven}</strong><span>letzte 7 Tage</span></div>
        <div class="admin-analytics-stat"><strong>${fourteen}</strong><span>letzte 14 Tage</span></div>
        <div class="admin-analytics-stat install"><strong>${installed}</strong><span>als App genutzt</span></div>
      </div>
      <div class="admin-analytics-note">Seit 07.10.2026 werden anonyme Geräte statt einzelner App-Starts gezählt. «Als App genutzt» zählt Geräte, die GO Eschenbach II vom Home-Bildschirm im App-Modus geöffnet haben.</div>
      <details class="admin-analytics-details">
        <summary>Tageswerte anzeigen</summary>
        <div class="admin-analytics-days">
          ${daily.map(d=>`<div class="admin-analytics-day"><span>${String(d.label||'')}</span><strong>${Number(d.users??d.opens??0)}</strong></div>`).join('')}
        </div>
      </details>
    `;
    app.appendChild(card);
    return true;
  }

  function mountWhenReady(stats){
    if(mount(stats))return;
    const app=document.getElementById('app');
    if(!app)return;
    const obs=new MutationObserver(()=>{
      if(mount(stats))obs.disconnect();
    });
    obs.observe(app,{childList:true,subtree:true});
    setTimeout(()=>obs.disconnect(),12000);
  }

  async function loadAdminStats(){
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token)return;
    try{
      const stats=await rpc('go_eschenbach_get_app_stats',{p_admin_token:token});
      if(stats?.ok)mountWhenReady(stats);
    }catch{}
  }

  (async()=>{
    const isAdmin=!!localStorage.getItem(TOKEN_KEY);
    if(!isAdmin){
      try{
        await rpc('go_eschenbach_track_app_open_v2',{
          p_device_id:getDeviceId(),
          p_standalone:isStandalone()
        });
      }catch{}
    }
    await loadAdminStats();
  })();
})();