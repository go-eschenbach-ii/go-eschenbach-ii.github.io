(function readerCommentsApp() {
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/reader-comments-public';
  const NAME_KEY='go-eschenbach-reader-comment-name';
  const DEVICE_KEY='go-eschenbach-reader-comment-device';
  const PAGE_SIZE=20;
  let reportKey='';
  let panel=null;
  let toggleButton=null;
  let list=null;
  let form=null;
  let status=null;
  let moreButton=null;
  let visible=0;
  let hasMore=false;
  let busy=false;
  let replyToId=null;
  let replyToName='';
  let replyingButton=null;
  let formContext=null;

  function slug(value){
    return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'')
      .toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,55);
  }
  function dateKey(value){
    const m=String(value||'').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return m ? m[3]+m[2]+m[1] : '';
  }
  function keyForReport(d){
    const matches=(Array.isArray(d.recent_results)?d.recent_results:[])
      .filter(m=>/fc\s+eschenbach\s+ii/i.test(String(m.home||''))||/fc\s+eschenbach\s+ii/i.test(String(m.away||'')))
      .filter(m=>dateKey(m.date) && m.home_goals!=null && m.away_goals!=null)
      .sort((a,b)=>dateKey(b.date).localeCompare(dateKey(a.date)));
    const m=matches[0];
    if(m)return 'match:'+dateKey(m.date)+':'+slug(m.home)+':'+slug(m.away);
    return 'report:'+(dateKey(d.report_date)||'00000000');
  }
  function deviceId(){
    let id=localStorage.getItem(DEVICE_KEY);
    if(!id){
      if(crypto.randomUUID)id=crypto.randomUUID();
      else{
        const bytes=new Uint8Array(16);
        crypto.getRandomValues(bytes);
        id=Array.from(bytes,x=>x.toString(16).padStart(2,'0')).join('');
      }
      localStorage.setItem(DEVICE_KEY,id);
    }
    return id;
  }
  function setStatus(message,error){
    if(!status)return;
    status.textContent=message||'';
    status.classList.toggle('is-error',Boolean(error));
  }
  function formatDate(value){
    const d=new Date(value);
    if(Number.isNaN(d.getTime()))return '';
    return d.toLocaleString('de-CH',{
      timeZone:'Europe/Zurich',
      day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'
    });
  }
  function addComment(item, container, isReply=false){
    const card=document.createElement('article');
    card.className=isReply?'reader-comment reader-comment-reply':'reader-comment';
    const info=document.createElement('div');
    info.className='reader-comment-head';
    const name=document.createElement('strong');
    name.textContent=String(item.display_name||'Fan');
    const time=document.createElement('time');
    time.textContent=formatDate(item.created_at);
    if(item.created_at)time.dateTime=item.created_at;
    info.append(name,time);
    const body=document.createElement('p');
    body.className='reader-comment-body';
    body.textContent=String(item.body||'');
    card.append(info,body);
    const actions=document.createElement('div');
    actions.className='reader-comment-actions';
    if(!isReply){
      const reply=document.createElement('button');
      reply.type='button';
      reply.className='reader-comment-answer';
      reply.textContent='Antworten';
      reply.setAttribute('aria-label','Auf Kommentar von '+name.textContent+' antworten');
      reply.addEventListener('click',()=>openForm({id:item.id,name:name.textContent,card,button:reply}));
      actions.append(reply);
    }
    if(actions.childNodes.length)card.append(actions);
    container.append(card);
    return card;
  }
  function renderComments(items){
    const roots=items.filter(c=>!c.parent_id);
    const replies=new Map();
    for(const comment of items){
      if(!comment.parent_id)continue;
      if(!replies.has(comment.parent_id))replies.set(comment.parent_id,[]);
      replies.get(comment.parent_id).push(comment);
    }
    for(const root of roots){
      const card=addComment(root,list);
      const children=replies.get(root.id)||[];
      if(children.length){
        const wrap=document.createElement('div');
        wrap.className='reader-comment-replies';
        for(const child of children)addComment(child,wrap,true);
        card.append(wrap);
      }
    }
  }
  async function load(reset=false){
    if(busy)return;
    busy=true;
    if(moreButton)moreButton.disabled=true;
    if(reset){
      visible=0;
      list.replaceChildren();
      setStatus('');
    }
    try{
      const response=await fetch(API+'?report_key='+encodeURIComponent(reportKey)+
        '&offset='+visible+'&t='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw Error('load_failed');
      const data=await response.json();
      if(!data.ok || !Array.isArray(data.comments))throw Error('bad_response');
      if(reset)list.replaceChildren();
      renderComments(data.comments);
      visible+=Number(data.root_count??data.comments.filter(c=>!c.parent_id).length);
      hasMore=Boolean(data.has_more);
      moreButton.hidden=!hasMore;
      if(!visible){
        const empty=document.createElement('p');
        empty.className='reader-comments-empty';
        empty.textContent='Noch keine Kommentare. Schreibe den ersten!';
        list.append(empty);
      }
      setStatus('');
    }catch{
      if(reset)list.replaceChildren();
      setStatus('Kommentare konnten gerade nicht geladen werden. Bitte später erneut versuchen.',true);
    }finally{
      busy=false;
      moreButton.disabled=false;
    }
  }
  async function submit(e){
    e.preventDefault();
    if(busy)return;
    const requestedParent=replyToId;
    const nameInput=form.querySelector('.reader-comment-name');
    const messageInput=form.querySelector('.reader-comment-text');
    const submitButton=form.querySelector('.reader-comment-submit');
    const name=String(nameInput.value||'').trim().replace(/\s+/g,' ');
    const message=String(messageInput.value||'').trim();
    if(name.length<2||name.length>32){
      setStatus('Bitte einen Vornamen mit mindestens zwei Zeichen angeben.',true);
      nameInput.focus();
      return;
    }
    if(message.length<3||message.length>700){
      setStatus('Bitte einen Kommentar mit 3 bis 700 Zeichen schreiben.',true);
      messageInput.focus();
      return;
    }
    busy=true;
    submitButton.disabled=true;
    submitButton.textContent='Wird gesendet …';
    setStatus('');
    try{
      const res=await fetch(API,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          action:'create',report_key:reportKey,
          display_name:name,body:message,device_id:deviceId(),
          parent_id:requestedParent,
          website:form.querySelector('.reader-comment-website').value
        })
      });
      const data=await res.json().catch(()=>({}));
      if(!res.ok){
        if(res.status===429)throw Error('Bitte kurz warten, bevor du einen weiteren Kommentar veröffentlichst.');
        if(res.status===409)throw Error('Diesen Kommentar hast du bereits abgeschickt.');
        if(data.error==='no_links')throw Error('Bitte keine Links oder E-Mail-Adressen veröffentlichen.');
        if(data.error==='parent_not_found')throw Error('Der ursprüngliche Kommentar ist nicht mehr verfügbar.');
        if(data.error==='invalid_input')throw Error('Bitte Vorname und Kommentar überprüfen.');
        throw Error('Der Kommentar konnte nicht gespeichert werden. Versuche es nochmals.');
      }
      if(!data.ok)throw Error('Der Kommentar konnte nicht gespeichert werden.');
      localStorage.setItem(NAME_KEY,name);
      messageInput.value='';
      closePanel();
      // Nach erfolgreichem Speichern verschwindet nur das Eingabefeld.
      // Die öffentliche Kommentarliste bleibt jederzeit sichtbar.
    }catch(err){
      setStatus(err.message||'Senden fehlgeschlagen. Bitte nochmals versuchen.',true);
      return;
    }finally{
      busy=false;
      submitButton.disabled=false;
      submitButton.textContent='Kommentar veröffentlichen';
    }
    await load(true);
    setStatus('Dein Kommentar wurde veröffentlicht.');
  }

  function closePanel(){
    if(!form)return;
    const wasOpen=!form.hidden;
    form.hidden=true;
    if(formContext)formContext.hidden=true;
    replyToId=null;
    replyToName='';
    replyingButton=null;
    const closeButton=panel?.querySelector('.reader-comments-close');
    if(closeButton)closeButton.hidden=true;
    panel.insertBefore(form,status);
    toggleButton?.setAttribute('aria-expanded','false');
    toggleButton?.setAttribute('aria-label','Kommentar schreiben');
    if(wasOpen)toggleButton?.focus({preventScroll:true});
  }
  function openForm(target=null){
    if(!form)return;
    if(!target && !form.hidden && !replyToId){
      closePanel();
      return;
    }
    replyToId=target?.id||null;
    replyToName=target?.name||'';
    replyingButton=target?.button||null;
    form.hidden=false;
    formContext.hidden=!replyToId;
    formContext.textContent=replyToId?'Antwort an '+replyToName:'';
    const closeButton=panel.querySelector('.reader-comments-close');
    if(closeButton)closeButton.hidden=false;
    if(target?.card){
      target.card.append(form);
    }else{
      panel.insertBefore(form,status);
    }
    toggleButton?.setAttribute('aria-expanded',String(!replyToId));
    toggleButton?.setAttribute('aria-label',replyToId?'Kommentar schreiben':'Kommentarfeld schliessen');
    form.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  function togglePanel(){
    openForm();
  }

  function mount(d){
    if(panel)return true;
    const app=document.getElementById('app');
    if(!app||app.querySelector('.skeleton'))return false;
    const review=Array.from(app.querySelectorAll(':scope > section.card'))
      .find(s=>s.querySelector(':scope > h2')?.textContent?.trim()==='Rückblick');
    if(!review)return false;
    reportKey=keyForReport(d);
    panel=document.createElement('section');
    panel.id='readerCommentsPanel';
    panel.className='reader-comments-card';
    panel.setAttribute('aria-label','Fan-Kommentare');
    toggleButton=document.createElement('button');
    toggleButton.id='readerCommentsToggle';
    toggleButton.className='reader-comments-toggle';
    toggleButton.type='button';
    toggleButton.setAttribute('aria-controls','readerCommentsForm');
    toggleButton.setAttribute('aria-expanded','false');
    toggleButton.setAttribute('aria-label','Kommentar schreiben');
    toggleButton.title='Kommentare zum Spielbericht';
    toggleButton.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z"/></svg>';
    toggleButton.addEventListener('click',togglePanel);
    const toolbar=document.createElement('div');
    toolbar.className='reader-comments-toolbar';
    const label=document.createElement('span');
    label.className='reader-comments-toggle-label';
    label.textContent='Kommentar';
    toolbar.append(toggleButton,label);
    const reviewText=review.querySelector(':scope > p');
    if(reviewText)reviewText.insertAdjacentElement('afterend',toolbar);
    else review.append(toolbar);

    const closeButton=document.createElement('button');
    closeButton.type='button';
    closeButton.className='reader-comments-close';
    closeButton.setAttribute('aria-label','Kommentarfeld schliessen');
    closeButton.textContent='×';
    closeButton.hidden=true;
    closeButton.addEventListener('click',closePanel);

    form=document.createElement('form');
    form.id='readerCommentsForm';
    form.className='reader-comment-form';
    form.hidden=true;
    formContext=document.createElement('div');
    formContext.className='reader-comment-reply-context';
    formContext.hidden=true;
    form.append(formContext,closeButton);
    const nameLabel=document.createElement('label');
    nameLabel.textContent='Dein Vorname';
    const nameInput=document.createElement('input');
    nameInput.className='reader-comment-name';
    nameInput.type='text';
    nameInput.maxLength=32;
    nameInput.required=true;
    nameInput.autocomplete='given-name';
    nameInput.placeholder='Vorname';
    nameInput.value=localStorage.getItem(NAME_KEY)||'';
    nameLabel.append(nameInput);
    const messageLabel=document.createElement('label');
    messageLabel.textContent='Dein Kommentar';
    const messageInput=document.createElement('textarea');
    messageInput.className='reader-comment-text';
    messageInput.maxLength=700;
    messageInput.rows=3;
    messageInput.required=true;
    messageInput.placeholder='Was möchtest du zum Spiel sagen?';
    messageLabel.append(messageInput);
    const website=document.createElement('input');
    website.type='text';
    website.className='reader-comment-website';
    website.tabIndex=-1;
    website.autocomplete='off';
    website.setAttribute('aria-hidden','true');
    const submitButton=document.createElement('button');
    submitButton.type='submit';
    submitButton.className='reader-comment-submit';
    submitButton.textContent='Kommentar veröffentlichen';
    form.append(nameLabel,messageLabel,website,submitButton);
    form.addEventListener('submit',submit);

    status=document.createElement('p');
    status.className='reader-comments-status';
    status.setAttribute('role','status');
    status.setAttribute('aria-live','polite');
    list=document.createElement('div');
    list.className='reader-comments-list';
    moreButton=document.createElement('button');
    moreButton.type='button';
    moreButton.className='reader-comments-more';
    moreButton.textContent='Weitere Kommentare anzeigen';
    moreButton.hidden=true;
    moreButton.addEventListener('click',()=>load(false));
    panel.append(form,status,list,moreButton);
    toolbar.after(panel);
    // Kommentare werden unabhängig davon geladen, ob das Eingabefeld geöffnet ist.
    load(true);
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape' && form && !form.hidden)closePanel();
    });
    return true;
  }

  async function start(){
    try{
      const response=await fetch('data/report.json?readercomments='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw Error('no report');
      const d=await response.json();
      if(mount(d))return;
      const app=document.getElementById('app');
      if(!app)return;
      const observer=new MutationObserver(()=>{
        if(mount(d))observer.disconnect();
      });
      observer.observe(app,{childList:true,subtree:true});
      setTimeout(()=>observer.disconnect(),12000);
    }catch(e){
      console.warn('Reader comments unavailable:',e);
    }
  }
  start();
})();
