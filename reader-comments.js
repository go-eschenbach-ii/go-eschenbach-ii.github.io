(function readerCommentsApp() {
  const API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/reader-comments-public';
  const NAME_KEY='go-eschenbach-reader-comment-name';
  const DEVICE_KEY='go-eschenbach-reader-comment-device';
  const ADMIN_KEY='go-eschenbach-comment-admin-token';
  const PAGE_SIZE=20;
  let reportKey='';
  let panel=null;
  let list=null;
  let form=null;
  let status=null;
  let moreButton=null;
  let visible=0;
  let hasMore=false;
  let busy=false;

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
  function addComment(item){
    const card=document.createElement('article');
    card.className='reader-comment';
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
    if(localStorage.getItem(ADMIN_KEY)){
      const hide=document.createElement('button');
      hide.type='button';
      hide.className='reader-comment-hide';
      hide.textContent='Ausblenden';
      hide.setAttribute('aria-label','Kommentar von '+name.textContent+' ausblenden');
      hide.addEventListener('click',()=>hideComment(String(item.id||''),hide));
      card.append(hide);
    }
    list.append(card);
  }
  async function load(reset=false){
    if(busy)return;
    busy=true;
    if(moreButton)moreButton.disabled=true;
    if(reset){
      visible=0;
      list.replaceChildren();
      setStatus('Kommentare werden geladen …');
    }
    try{
      const response=await fetch(API+'?report_key='+encodeURIComponent(reportKey)+
        '&offset='+visible+'&t='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw Error('load_failed');
      const data=await response.json();
      if(!data.ok || !Array.isArray(data.comments))throw Error('bad_response');
      if(reset)list.replaceChildren();
      data.comments.forEach(addComment);
      visible+=data.comments.length;
      hasMore=Boolean(data.has_more);
      moreButton.hidden=!hasMore;
      if(!visible){
        const empty=document.createElement('p');
        empty.className='reader-comments-empty';
        empty.textContent='Noch keine Kommentare. Schreibe den ersten!';
        list.append(empty);
      }
      setStatus(visible? 'Neueste Kommentare zuerst' : '');
    }catch{
      if(reset)list.replaceChildren();
      setStatus('Kommentare konnten gerade nicht geladen werden. Bitte später erneut versuchen.',true);
    }finally{
      busy=false;
      moreButton.disabled=false;
    }
  }
  async function hideComment(id,button){
    if(!id || !localStorage.getItem(ADMIN_KEY))return;
    if(!window.confirm('Diesen Kommentar für alle ausblenden?'))return;
    button.disabled=true;
    try{
      const res=await fetch(API,{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'Authorization':'Bearer '+localStorage.getItem(ADMIN_KEY)
        },
        body:JSON.stringify({action:'hide',id})
      });
      if(!res.ok)throw Error('hide_failed');
      const data=await res.json();
      if(!data.ok)throw Error('hide_failed');
      setStatus('Kommentar wurde ausgeblendet.');
      await load(true);
    }catch{
      setStatus('Kommentar konnte nicht ausgeblendet werden.',true);
    }finally{
      button.disabled=false;
    }
  }
  async function submit(e){
    e.preventDefault();
    if(busy)return;
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
          website:form.querySelector('.reader-comment-website').value
        })
      });
      const data=await res.json().catch(()=>({}));
      if(!res.ok){
        if(res.status===429)throw Error('Bitte kurz warten, bevor du einen weiteren Kommentar veröffentlichst.');
        if(res.status===409)throw Error('Diesen Kommentar hast du bereits abgeschickt.');
        if(data.error==='no_links')throw Error('Bitte keine Links oder E-Mail-Adressen veröffentlichen.');
        if(data.error==='invalid_input')throw Error('Bitte Vorname und Kommentar überprüfen.');
        throw Error('Der Kommentar konnte nicht gespeichert werden. Versuche es nochmals.');
      }
      if(!data.ok)throw Error('Der Kommentar konnte nicht gespeichert werden.');
      localStorage.setItem(NAME_KEY,name);
      messageInput.value='';
      setStatus('Dein Kommentar wurde veröffentlicht.');
      // Run refresh after releasing the posting lock.
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
    panel.className='card reader-comments-card';
    panel.setAttribute('aria-labelledby','readerCommentsTitle');

    const headline=document.createElement('h2');
    headline.id='readerCommentsTitle';
    headline.textContent='💬 Kommentare zum Spielbericht';
    const intro=document.createElement('p');
    intro.className='reader-comments-intro';
    intro.textContent='Was meinst du zum Spiel? Teile deine Meinung mit anderen Eschenbach-Fans.';

    form=document.createElement('form');
    form.className='reader-comment-form';
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
    const subTitle=document.createElement('h3');
    subTitle.textContent='Stimmen der Fans';
    subTitle.className='reader-comments-subtitle';
    list=document.createElement('div');
    list.className='reader-comments-list';
    moreButton=document.createElement('button');
    moreButton.type='button';
    moreButton.className='reader-comments-more';
    moreButton.textContent='Weitere Kommentare anzeigen';
    moreButton.hidden=true;
    moreButton.addEventListener('click',()=>load(false));
    panel.append(headline,intro,form,status,subTitle,list,moreButton);
    review.after(panel);
    load(true);
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
