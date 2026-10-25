(()=>{
  const ensureMatchHighlightStyles=()=>{
    if(document.getElementById('eschenbachMatchHighlightStyles'))return;
    const style=document.createElement('style');
    style.id='eschenbachMatchHighlightStyles';
    style.textContent=`
      #app .review-card .match:not(.eschenbach-match),
      #app .outlook-card .match:not(.eschenbach-match){
        border-color:#c9c9c9;
        background:#fff;
        box-shadow:none;
      }
      #app .review-card .match.eschenbach-match,
      #app .outlook-card .match.eschenbach-match{
        position:relative;
        box-sizing:border-box;
        border:4px solid #111!important;
        background:linear-gradient(135deg,#fff7ba 0%,#ffdf35 58%,#f4c400 100%)!important;
        box-shadow:0 0 0 4px #f4c400,7px 7px 0 #111!important;
        padding-top:19px!important;
        margin-top:18px!important;
        margin-bottom:14px!important;
      }
      #app .review-card .match.eschenbach-match:before,
      #app .outlook-card .match.eschenbach-match:before{
        content:'ESCHENBACH';
        position:absolute;
        top:-13px;
        right:10px;
        background:#111;
        color:#f4c400;
        border:3px solid #f4c400;
        border-radius:999px;
        padding:5px 10px 4px;
        font-size:10px;
        line-height:1;
        font-weight:1000;
        letter-spacing:.09em;
        box-shadow:3px 3px 0 #111;
        transform:rotate(2deg);
        z-index:2;
        white-space:nowrap;
      }
      #app .review-card .match.eschenbach-match .match-pairing,
      #app .outlook-card .match.eschenbach-match .match-pairing{
        font-weight:950;
      }
      @media(max-width:600px){
        #app .review-card .match.eschenbach-match,
        #app .outlook-card .match.eschenbach-match{
          border-width:4px!important;
          box-shadow:0 0 0 3px #f4c400,5px 5px 0 #111!important;
          padding-top:18px!important;
          margin-top:17px!important;
        }
        #app .review-card .match.eschenbach-match:before,
        #app .outlook-card .match.eschenbach-match:before{
          top:-12px;
          right:8px;
          border-width:2px;
          padding:5px 8px 4px;
          font-size:8.5px;
          box-shadow:2px 2px 0 #111;
        }
      }
    `;
    document.head.appendChild(style);
  };

  const fitPairing=row=>{
    const pairing=row?.children?.[1];
    if(!pairing||pairing.tagName!=='DIV')return;
    pairing.classList.add('match-pairing');
    pairing.style.whiteSpace='nowrap';
    pairing.style.fontSize='';
    pairing.style.letterSpacing='';
    requestAnimationFrame(()=>{
      let size=parseFloat(getComputedStyle(pairing).fontSize)||16;
      const minSize=9.5;
      while(pairing.scrollWidth>pairing.clientWidth&&size>minSize){
        size=Math.max(minSize,size-.5);
        pairing.style.fontSize=`${size}px`;
      }
      if(pairing.scrollWidth>pairing.clientWidth)pairing.style.letterSpacing='-.02em';
    });
  };

  const fitAllPairings=()=>{
    document.querySelectorAll('#app .review-card .match,#app .outlook-card .match').forEach(fitPairing);
  };

  const decorate=()=>{
    ensureMatchHighlightStyles();
    const cards=[...document.querySelectorAll('#app section.card')];
    if(!cards.length)return false;

    cards.forEach(card=>{
      const title=card.querySelector(':scope > h2')?.textContent?.trim()||'';
      if(title==='Rückblick')card.classList.add('section-card','review-card');
      if(title==='Aktuelle Situation')card.classList.add('section-card','standings-card');
      if(title==='Ausblick')card.classList.add('section-card','outlook-card');
      if(title==='Eschenbach-Torschützen')card.classList.add('section-card','scorers-card');
    });

    document.querySelectorAll('#app .review-card .match,#app .outlook-card .match').forEach(row=>{
      if(row.textContent.includes('FC Eschenbach II'))row.classList.add('eschenbach-match');
      fitPairing(row);
    });

    const scorerCard=document.querySelector('#app .scorers-card');
    if(scorerCard){
      scorerCard.querySelectorAll('.match').forEach(row=>row.classList.add('scorer-row'));
      const sticker=[...scorerCard.querySelectorAll('span')].find(el=>el.textContent.trim()==='TOPSCORER');
      if(sticker){
        sticker.className='topscorer-sticker';
        sticker.removeAttribute('style');
        sticker.closest('.match')?.classList.add('top-scorer');
      }
    }
    return true;
  };

  if(!decorate()){
    const target=document.getElementById('app');
    if(target){
      const observer=new MutationObserver(()=>{
        if(decorate())observer.disconnect();
      });
      observer.observe(target,{childList:true,subtree:true});
    }
  }

  let resizeTimer=null;
  addEventListener('resize',()=>{
    clearTimeout(resizeTimer);
    resizeTimer=setTimeout(fitAllPairings,100);
  });

  if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js?v=59').catch(()=>{});}
})();
