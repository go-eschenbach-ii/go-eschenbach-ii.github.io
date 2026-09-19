(()=>{
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/section-moods-public';
  const deviceKey='go-eschenbach-mood-device';
  const allowedHeadings=new Set(['Rückblick','Ausblick']);
  let rebuildTimer=null;

  const makeUuid=()=>{
    if(globalThis.crypto?.randomUUID)return crypto.randomUUID();
    const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const h=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');
    return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
  };
  const getDeviceId=()=>{
    let id=localStorage.getItem(deviceKey);
    if(!id){id=makeUuid();localStorage.setItem(deviceKey,id)}
    return id;
  };
  const collectHeadings=()=>[...document.querySelectorAll('#app h2,#app h3.section-subtitle')]
    .filter(el=>allowedHeadings.has(el.textContent?.trim()||''));
  const reportMarker=()=>document.querySelector('.update-sticker')?.getAttribute('aria-label')||'aktueller Bericht';
  const heartCycleKey=()=>document.getElementById('app')?.dataset.heartCycleKey?.trim()||'';
  const sectionKey=heading=>{
    const name=heading.textContent.trim();
    if(name==='Rückblick'){
      const cycle=heartCycleKey();
      if(cycle)return `heading:${name}|cycle:${cycle}`.slice(0,300);
    }
    return `heading:${name}|${reportMarker()}`.slice(0,300);
  };
  const savedKey=key=>`go-eschenbach-mood-choice:${key}`;

  async function loadCount(key,meter){
    const count=meter.querySelector('.mood-meter-count');
    try{
      const r=await fetch(`${API}?section_key=${encodeURIComponent(key)}`,{cache:'no-store'});
      if(!r.ok)throw Error();
      const d=await r.json();
      if(count)count.textContent=String(d.count||0);
    }catch{}
  }

  async function cheer(key,meter){
    const button=meter.querySelector('.mood-meter-button');
    if(!button)return;
    button.disabled=true;
    try{
      const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section_key:key,device_id:getDeviceId()})});
      if(!r.ok)throw Error();
      localStorage.setItem(savedKey(key),'heart');
      button.classList.add('is-selected');
      button.setAttribute('aria-pressed','true');
      await loadCount(key,meter);
    }catch{}finally{
      button.disabled=false;
    }
  }

  function mountHeading(heading){
    if(!allowedHeadings.has(heading.textContent?.trim()||'')||heading.dataset.moodMeterMounted==='1')return;
    heading.dataset.moodMeterMounted='1';
    const key=sectionKey(heading);
    const selected=localStorage.getItem(savedKey(key))==='heart';
    const meter=document.createElement('div');
    meter.className='mood-meter';
    meter.dataset.moodKey=key;
    meter.innerHTML=`<button class="mood-meter-button${selected?' is-selected':''}" type="button" aria-label="Herz für ${heading.textContent.trim()}" aria-pressed="${selected?'true':'false'}"><span class="mood-meter-emoji" aria-hidden="true">❤️</span><span class="mood-meter-count">0</span></button>`;
    heading.insertAdjacentElement('afterend',meter);
    meter.querySelector('.mood-meter-button')?.addEventListener('click',()=>cheer(key,meter));
    loadCount(key,meter);
  }

  const rebuild=()=>collectHeadings().forEach(mountHeading);
  const scheduleRebuild=()=>{clearTimeout(rebuildTimer);rebuildTimer=setTimeout(rebuild,40)};

  rebuild();
  const app=document.getElementById('app');
  if(app)new MutationObserver(scheduleRebuild).observe(app,{childList:true,subtree:true,characterData:true});
})();
