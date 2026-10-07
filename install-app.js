(()=>{
  const button=document.getElementById('installAppButton');
  if(!button)return;

  let deferredPrompt=null;
  const isStandalone=()=>window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;
  const isIOS=()=>/iphone|ipad|ipod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);

  const closeMenu=()=>{
    const menuButton=document.getElementById('appMenuButton');
    const panel=document.getElementById('appMenuPanel');
    if(panel)panel.hidden=true;
    menuButton?.setAttribute('aria-expanded','false');
  };

  const ensureDialog=()=>{
    let dialog=document.getElementById('installAppDialog');
    if(dialog)return dialog;
    dialog=document.createElement('div');
    dialog.id='installAppDialog';
    dialog.className='install-app-dialog';
    dialog.hidden=true;
    dialog.setAttribute('role','dialog');
    dialog.setAttribute('aria-modal','true');
    dialog.setAttribute('aria-labelledby','installAppDialogTitle');
    dialog.innerHTML=`
      <div class="install-app-card">
        <button class="install-app-close" type="button" aria-label="Hinweis schliessen">×</button>
        <div class="install-app-icon" aria-hidden="true">⬆</div>
        <h2 id="installAppDialogTitle">App auf Home-Bildschirm laden</h2>
        <p class="install-app-intro">So hast du GO Eschenbach II wie eine App direkt auf deinem Handy.</p>
        <ol class="install-app-steps">
          <li>Tippe im Browser auf <strong>Teilen</strong> <span class="install-share-symbol" aria-hidden="true">□↑</span>.</li>
          <li>Wähle <strong>Zum Home-Bildschirm</strong>.</li>
          <li>Bestätige oben mit <strong>Hinzufügen</strong>.</li>
        </ol>
        <button class="install-app-ok" type="button">Verstanden</button>
      </div>`;
    document.body.appendChild(dialog);
    const close=()=>{
      dialog.hidden=true;
      document.body.classList.remove('install-dialog-open');
      button.focus();
    };
    dialog.querySelector('.install-app-close')?.addEventListener('click',close);
    dialog.querySelector('.install-app-ok')?.addEventListener('click',close);
    dialog.addEventListener('click',event=>{if(event.target===dialog)close();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!dialog.hidden)close();});
    return dialog;
  };

  const showInstructions=()=>{
    const dialog=ensureDialog();
    const intro=dialog.querySelector('.install-app-intro');
    const steps=dialog.querySelector('.install-app-steps');
    if(isIOS()){
      if(intro)intro.textContent='So hast du GO Eschenbach II wie eine App direkt auf deinem iPhone.';
      if(steps)steps.innerHTML=`
        <li>Tippe in Safari auf <strong>Teilen</strong> <span class="install-share-symbol" aria-hidden="true">□↑</span>.</li>
        <li>Scrolle zu <strong>Zum Home-Bildschirm</strong>.</li>
        <li>Bestätige oben rechts mit <strong>Hinzufügen</strong>.</li>`;
    }else{
      if(intro)intro.textContent='Dein Browser kann die App gerade nicht automatisch installieren.';
      if(steps)steps.innerHTML=`
        <li>Öffne das Menü deines Browsers.</li>
        <li>Wähle <strong>App installieren</strong> oder <strong>Zum Home-Bildschirm</strong>.</li>
        <li>Bestätige die Installation.</li>`;
    }
    dialog.hidden=false;
    document.body.classList.add('install-dialog-open');
    dialog.querySelector('.install-app-close')?.focus();
  };

  window.addEventListener('beforeinstallprompt',event=>{
    event.preventDefault();
    deferredPrompt=event;
    button.hidden=false;
  });

  window.addEventListener('appinstalled',()=>{
    deferredPrompt=null;
    button.hidden=true;
  });

  if(isStandalone())button.hidden=true;

  button.addEventListener('click',async()=>{
    closeMenu();
    if(isStandalone()){
      button.hidden=true;
      return;
    }
    if(deferredPrompt){
      const prompt=deferredPrompt;
      deferredPrompt=null;
      try{
        await prompt.prompt();
        await prompt.userChoice;
      }catch{}
      return;
    }
    showInstructions();
  });
})();