(()=>{
  const button=document.getElementById('installAppButton');
  if(!button)return;

  let deferredPrompt=null;
  const appUrl='https://go-eschenbach-ii.github.io/';
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
        <div class="install-app-highlight">Wähle: <strong>Zum Home-Bildschirm</strong></div>
        <ol class="install-app-steps">
          <li>Tippe im Browser auf <strong>Teilen</strong> <span class="install-share-symbol" aria-hidden="true">□↑</span>.</li>
          <li>Wähle <strong>Zum Home-Bildschirm</strong>.</li>
          <li>Bestätige mit <strong>Hinzufügen</strong>.</li>
        </ol>
        <button class="install-app-ok" type="button">Verstanden</button>
      </div>`;
    document.body.appendChild(dialog);

    const hideDialog=(restoreFocus=true)=>{
      dialog.hidden=true;
      document.body.classList.remove('install-dialog-open');
      if(restoreFocus)button.focus();
    };

    dialog.querySelector('.install-app-close')?.addEventListener('click',()=>hideDialog(true));
    dialog.querySelector('.install-app-ok')?.addEventListener('click',async()=>{
      hideDialog(false);
      if(navigator.share){
        try{
          await navigator.share({
            title:'GO Eschenbach II',
            text:'GO Eschenbach II auf dem Home-Bildschirm speichern.',
            url:appUrl
          });
        }catch(error){
          if(error?.name!=='AbortError'){
            setTimeout(showInstructions,80);
          }
        }finally{
          button.focus();
        }
        return;
      }
      showInstructions();
    });
    dialog.addEventListener('click',event=>{if(event.target===dialog)hideDialog(true);});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!dialog.hidden)hideDialog(true);});
    return dialog;
  };

  const showInstructions=()=>{
    const dialog=ensureDialog();
    const title=dialog.querySelector('#installAppDialogTitle');
    const intro=dialog.querySelector('.install-app-intro');
    const highlight=dialog.querySelector('.install-app-highlight');
    const steps=dialog.querySelector('.install-app-steps');
    if(isIOS()){
      if(title)title.textContent='Auf dem iPhone speichern';
      if(intro)intro.textContent='Nach „Verstanden“ öffnet sich das Teilen-Menü. Wähle dort:';
      if(highlight)highlight.innerHTML='Wähle: <strong>Zum Home-Bildschirm</strong>';
      if(steps)steps.innerHTML=`
        <li>Tippe unten auf <strong>Verstanden</strong>.</li>
        <li>Wähle im Teilen-Menü <strong>Zum Home-Bildschirm</strong>.</li>
        <li>Tippe oben rechts auf <strong>Hinzufügen</strong>.</li>`;
    }else{
      if(title)title.textContent='App auf Handy laden';
      if(intro)intro.textContent='Nach „Verstanden“ öffnet sich das Teilen-Menü deines Smartphones.';
      if(highlight)highlight.innerHTML='Wähle: <strong>Zum Home-Bildschirm</strong> oder <strong>App installieren</strong>';
      if(steps)steps.innerHTML=`
        <li>Tippe unten auf <strong>Verstanden</strong>.</li>
        <li>Wähle <strong>Zum Home-Bildschirm</strong> oder <strong>App installieren</strong>.</li>
        <li>Bestätige die Installation.</li>`;
    }
    dialog.hidden=false;
    document.body.classList.add('install-dialog-open');
    dialog.querySelector('.install-app-ok')?.focus();
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
    if(deferredPrompt&&!isIOS()){
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