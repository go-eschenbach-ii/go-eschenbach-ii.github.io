(()=>{
  const corrections=[[/\bGerber\b/g,'Gürber']];
  const fixText=value=>corrections.reduce((text,[pattern,replacement])=>text.replace(pattern,replacement),String(value??''));
  const fixNode=node=>{
    if(!node)return;
    if(node.nodeType===Node.TEXT_NODE){
      const next=fixText(node.nodeValue);
      if(next!==node.nodeValue)node.nodeValue=next;
      return;
    }
    if(node.nodeType!==Node.ELEMENT_NODE&&node.nodeType!==Node.DOCUMENT_FRAGMENT_NODE)return;
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
    let current;
    while((current=walker.nextNode())){
      const next=fixText(current.nodeValue);
      if(next!==current.nodeValue)current.nodeValue=next;
    }
  };
  const start=()=>{
    fixNode(document.body);
    const observer=new MutationObserver(records=>{
      for(const record of records){
        if(record.type==='characterData')fixNode(record.target);
        for(const node of record.addedNodes||[])fixNode(node);
      }
    });
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
