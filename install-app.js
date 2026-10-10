(()=>{
  const button=document.getElementById('installAppButton');
  if(!button)return;

  let deferredPrompt=null;
  const ADMIN_TOKEN_KEY='go-eschenbach-comment-admin-token';
  const isStandalone=()=>window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;
  const isAdmin=()=>!!localStorage.getItem(ADMIN_TOKEN_KEY);
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
        <p class="install-app-intro">In Safari unten auf <strong>Teilen</strong> tippen.</p>
        <div class="install-app-highlight"><strong>Zum Home-Bildschirm</strong> wählen</div>
        <p class="install-app-simple-end">Danach mit <strong>Hinzufügen</strong> bestätigen.</p>
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
    const title=dialog.querySelector('#installAppDialogTitle');
    const intro=dialog.querySelector('.install-app-intro');
    const highlight=dialog.querySelector('.install-app-highlight');
    const end=dialog.querySelector('.install-app-simple-end');

    if(isIOS()){
      if(title)title.textContent='App auf Home-Bildschirm laden';
      if(intro)intro.innerHTML='In Safari unten auf <strong>Teilen</strong> tippen.';
      if(highlight)highlight.innerHTML='<strong>Zum Home-Bildschirm</strong> wählen';
      if(end)end.innerHTML='Danach mit <strong>Hinzufügen</strong> bestätigen.';
    }else{
      if(title)title.textContent='App auf Handy laden';
      if(intro)intro.textContent='Öffne das Browser-Menü.';
      if(highlight)highlight.innerHTML='<strong>App installieren</strong> oder <strong>Zum Home-Bildschirm</strong> wählen';
      if(end)end.textContent='Danach die Installation bestätigen.';
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
    button.hidden=!isAdmin();
  });

  // Normale User sehen den Hinweis nur, solange die App nicht vom
  // Home-Bildschirm im Standalone-Modus geöffnet wird. Der Admin sieht ihn
  // weiterhin als Vorschau/Kontrolle.
  button.hidden=isStandalone()&&!isAdmin();

  button.addEventListener('click',async()=>{
    closeMenu();
    if(isStandalone()){
      if(isAdmin()){
        showInstructions();
      }else{
        button.hidden=true;
      }
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