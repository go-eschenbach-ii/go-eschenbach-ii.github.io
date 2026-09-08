(()=>{
  const TOKEN_KEY='go-eschenbach-comment-admin-token';
  const AFTER_RELOAD_KEY='go-eschenbach-comment-open-after-reload';
  let button=null;
  let busy=false;

  function injectStyles(){
    if(document.getElementById('commentaryLauncherStyles'))return;
    const style=document.createElement('style');
    style.id='commentaryLauncherStyles';
    style.textContent=`
      .commentary-mic-launcher{
        position:fixed;
        z-index:10018;
        right:14px;
        bottom:calc(env(safe-area-inset-bottom) + 18px);
        width:58px;
        height:58px;
        display:grid;
        place-items:center;
        padding:0;
        border:3px solid #111;
        border-radius:50%;
        background:#f4c400;
        color:#111;
        box-shadow:5px 5px 0 #111;
        font-size:27px;
        line-height:1;
        cursor:pointer;
        -webkit-tap-highlight-color:transparent;
      }
      .commentary-mic-launcher:active{transform:translate(2px,2px);box-shadow:3px 3px 0 #111}
      .commentary-mic-launcher:focus-visible{outline:3px solid #fff;outline-offset:3px}
      .commentary-mic-launcher.is-busy{font-size:20px;font-weight:950}
      .commentary-mic-launcher.has-panel{box-shadow:0 0 0 4px #fff,5px 5px 0 #111}
      @media(max-width:600px){
        .commentary-mic-launcher{
          right:11px;
          bottom:calc(env(safe-area-inset-bottom) + 14px);
          width:54px;
          height:54px;
          font-size:25px;
          box-shadow:4px 4px 0 #111;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function setBusy(value){
    busy=value;
    if(!button)return;
    button.disabled=value;
    button.classList.toggle('is-busy',value);
    button.textContent=value?'…':'🎙️';
  }

  function panel(){return document.getElementById('matchCommentaryPanel')}

  function updateButtonState(){
    if(!button)return;
    button.classList.toggle('has-panel',!!panel());
    button.title='Match kommentieren';
  }

  function openPanel(startSpeech=false){
    const p=panel();
    if(!p)return false;
    p.scrollIntoView({behavior:'smooth',block:'start'});
    const start=p.querySelector('#commentaryStart');
    if(startSpeech&&start&&!start.classList.contains('is-active')){
      try{start.click()}catch{}
    }
    return true;
  }

  function waitForPanel({startSpeech=false,timeout=9000}={}){
    if(openPanel(startSpeech))return;
    const app=document.getElementById('app')||document.body;
    const obs=new MutationObserver(()=>{
      if(openPanel(startSpeech)){
        obs.disconnect();
        updateButtonState();
      }
    });
    obs.observe(app,{childList:true,subtree:true});
    setTimeout(()=>obs.disconnect(),timeout);
  }

  function handleClick(){
    if(busy)return;
    if(openPanel(true)){
      updateButtonState();
      return;
    }
    setBusy(true);
    waitForPanel({startSpeech:true,timeout:7000});
    setTimeout(()=>setBusy(false),1300);
  }

  function mount(){
    if(button)return;

    // Das Mikrofon ist ausschliesslich auf bereits freigeschalteten Geräten sichtbar.
    // Besucher ohne lokalen Admin-Token sehen keinerlei Mikrofon- oder Admin-Element.
    if(!localStorage.getItem(TOKEN_KEY))return;

    injectStyles();
    button=document.createElement('button');
    button.id='commentaryMicLauncher';
    button.className='commentary-mic-launcher';
    button.type='button';
    button.textContent='🎙️';
    button.setAttribute('aria-label','Match kommentieren – Mikrofon');
    button.title='Match kommentieren';
    button.addEventListener('click',handleClick);
    document.body.appendChild(button);
    updateButtonState();

    const app=document.getElementById('app');
    if(app){
      const obs=new MutationObserver(updateButtonState);
      obs.observe(app,{childList:true,subtree:true});
    }

    if(sessionStorage.getItem(AFTER_RELOAD_KEY)==='1'){
      sessionStorage.removeItem(AFTER_RELOAD_KEY);
      waitForPanel({startSpeech:false,timeout:12000});
    }
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});
  else mount();
})();
