const CACHE='liga4daily-v64';
const ASSETS=[
  './','index.html','styles.css','stats-flip.css','theme-yellowblack.css','bottom-update.css',
  'team-photo-source.css','match-tip.css','app-menu.css','mood-meter.css','scorer-hearts.css',
  'share-button.css','match-commentary.css','update-badge.css','app.js','flippy-stats.js',
  'theme-enhance.js','reader-cleanup.js','match-tip.js','app-menu.js','mood-meter.js',
  'scorer-hearts.js','share-button.js','admin-activation-tap.js','match-commentary.js',
  'commentary-launcher.js','admin-update.js','update-badge.js','update-push-trigger.js',
  'manifest.webmanifest','logo-eschenbach-ii.svg','app-icon-180.png','apple-touch-icon.png',
  'app-icon-192.png','app-icon-512.png','team-photo.jpg','data/report.json'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  event.respondWith(
    fetch(event.request).then(response=>{
      const copy=response.clone();
      caches.open(CACHE).then(cache=>cache.put(event.request,copy));
      return response;
    }).catch(()=>caches.match(event.request))
  );
});

self.addEventListener('push',event=>{
  let data={};
  try{data=event.data?event.data.json():{};}catch{}
  const title=String(data.title||'GO Eschenbach II');
  const options={
    body:String(data.body||'Es gibt ein frisches Update.'),
    icon:'app-icon-192.png?v=5',
    badge:'app-icon-192.png?v=5',
    tag:'go-eschenbach-update',
    renotify:true,
    data:{url:String(data.url||'https://go-eschenbach-ii.github.io/')}
  };
  const tasks=[self.registration.showNotification(title,options)];
  if(self.navigator&&'setAppBadge' in self.navigator){
    tasks.push(self.navigator.setAppBadge(Number(data.badge||1)).catch(()=>{}));
  }
  event.waitUntil(Promise.all(tasks));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const url=event.notification.data?.url||'https://go-eschenbach-ii.github.io/';
  const tasks=[];
  if(self.navigator&&'clearAppBadge' in self.navigator){
    tasks.push(self.navigator.clearAppBadge().catch(()=>{}));
  }
  tasks.push(
    self.clients.matchAll({type:'window',includeUncontrolled:true}).then(clients=>{
      for(const client of clients){
        if('focus' in client){
          client.navigate(url).catch(()=>{});
          return client.focus();
        }
      }
      return self.clients.openWindow?self.clients.openWindow(url):undefined;
    })
  );
  event.waitUntil(Promise.all(tasks));
});
