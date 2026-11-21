(()=>{
  const button=document.getElementById('appMenuButton');
  const panel=document.getElementById('appMenuPanel');
  const nav=panel?.querySelector('nav');
  if(!button||!panel||!nav)return;

  let targets=[];
  let rebuildTimer=null;

  const collectHeadings=()=>{
    const headings=[];
    const heroTitle=document.querySelector('.hero h1');
    if(heroTitle)headings.push(heroTitle);
    document.querySelectorAll('#app h2,#app h3.section-subtitle').forEach(el=>{
      if(el.closest('.report-card'))return;
      headings.push(el);
    });
    return headings.filter(el=>el.textContent?.trim());
  };

  const rebuild=()=>{
    targets=collectHeadings();
    nav.innerHTML='';
    targets.forEach((target,index)=>{
      const label=target.textContent.trim();
      target.id=target.id||`app-menu-target-${index}`;
      target.classList.add('menu-scroll-target');
      const item=document.createElement('button');
      item.className='app-menu-link';
      item.type='button';
      item.textContent=label;
      item.dataset.menuIndex=String(index);
      nav.appendChild(item);
    });
    const dutiesLink=document.createElement("a");
    dutiesLink.className="app-menu-link";
    dutiesLink.href="aemter.html";
    dutiesLink.textContent="⚽ Einsatzplan";
    dutiesLink.style.cssText="display:block;text-decoration:none;background:#f4c400;color:#111;font-weight:900;border:2px solid #111;margin-top:8px";
    nav.appendChild(dutiesLink);
  };

  const scheduleRebuild=()=>{
    clearTimeout(rebuildTimer);
    rebuildTimer=setTimeout(rebuild,30);
  };

  const close=()=>{
    panel.hidden=true;
    button.setAttribute('aria-expanded','false');
  };
  const open=()=>{
    rebuild();
    panel.hidden=false;
    button.setAttribute('aria-expanded','true');
  };

  button.addEventListener('click',()=>panel.hidden?open():close());
  nav.addEventListener('click',event=>{
    const item=event.target.closest('[data-menu-index]');
    if(!item)return;
    const target=targets[Number(item.dataset.menuIndex)];
    close();
    if(target)setTimeout(()=>target.scrollIntoView({behavior:'smooth',block:'start'}),40);
  });
  document.addEventListener('click',event=>{
    if(panel.hidden||panel.contains(event.target)||button.contains(event.target))return;
    close();
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close();});

  rebuild();
  const app=document.getElementById('app');
  if(app)new MutationObserver(scheduleRebuild).observe(app,{childList:true,subtree:true,characterData:true});
})();