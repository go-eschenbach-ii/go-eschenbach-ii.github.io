(()=>{
  const REST='https://kfpxheegmeupnuzqjqqt.supabase.co/rest/v1/rpc';
  const API_KEY='sb_publishable_vlP2dIHDTK-VY5LK-jeS_w_tN04WaK0';
  const TOKEN_KEY='go-eschenbach-comment-admin-token';

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
      .admin-analytics-details{margin-top:12px;border-top:1px solid #e5e7eb;padding-top:10px}
      .admin-analytics-details summary{cursor:pointer;font-weight:800;font-size:13px}
      .admin-analytics-days{margin-top:8px;display:grid;gap:5px}
      .admin-analytics-day{display:flex;justify-content:space-between;gap:12px;font-size:13px;padding:5px 0;border-bottom:1px solid #f0f0f0}
      .admin-analytics-day:last-child{border-bottom:0}
      @media(max-width:600px){.admin-analytics-stat{padding:9px 5px}.admin-analytics-stat strong{font-size:20px}.admin-analytics-stat span{font-size:10px}}
    `;
    document.head.appendChild(style);
  }

  function mount(stats){
    if(!stats?.ok||document.getElementById('adminAppAnalytics'))return true;
    const app=document.getElementById('app');
    if(!app||app.querySelector('.skeleton'))return false;

    const daily=Array.isArray(stats.daily)?stats.daily:[];
    const today=Number(stats.today?.opens||0);
    const yesterday=Number(daily[1]?.opens||0);
    const seven=daily.slice(0,7).reduce((sum,d)=>sum+Number(d.opens||0),0);

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
        <div class="admin-analytics-stat"><strong>${today}</strong><span>Aufrufe heute</span></div>
        <div class="admin-analytics-stat"><strong>${yesterday}</strong><span>gestern</span></div>
        <div class="admin-analytics-stat"><strong>${seven}</strong><span>letzte 7 Tage</span></div>
      </div>
      <details class="admin-analytics-details">
        <summary>Tageswerte anzeigen</summary>
        <div class="admin-analytics-days">
          ${daily.map(d=>`<div class="admin-analytics-day"><span>${String(d.label||'')}</span><strong>${Number(d.opens||0)}</strong></div>`).join('')}
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
    try{await rpc('go_eschenbach_track_app_open');}catch{}
    await loadAdminStats();
  })();
})();