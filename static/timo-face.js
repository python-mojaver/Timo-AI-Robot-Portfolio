/* Timo Main Face: display metadata and real audio lifecycle, no robot commands. */
(() => {
 'use strict';
 if(window.TimoFace)return;
 const $=id=>document.getElementById(id),modes=['normal','happy','sad','angry','surprised'];
 const labels={normal:'معمولی',happy:'شاد',sad:'غمگین',angry:'عصبانی',surprised:'متعجب'};
 let turn=null,manual=false,lastFace='normal',returnTimer=0,binding=null,context=null,view='face',frame=null;
 let mounted=true,positionRelay=false,explicit=false;
 const root=document.createElement('section');root.id='tf-root';root.setAttribute('aria-label','چهرهٔ تیمو');root.dataset.mouth='closed';
 root.innerHTML='<div id="tf-art-host">'+"<svg class=\"tf-art\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1000 600\" role=\"img\" aria-label=\"Timo face\"><defs><radialGradient id=\"iris\" cx=\"35%\" cy=\"26%\" r=\"85%\"><stop offset=\"0\" stop-color=\"#2a9ce5\"/><stop offset=\"1\" stop-color=\"#1678bd\"/></radialGradient>\n <clipPath id=\"sad-323\"><path d=\"M220 251 Q323 277 426 251 V380 H220Z\"/></clipPath><clipPath id=\"sad-677\"><path d=\"M574 251 Q677 277 780 251 V380 H574Z\"/></clipPath>\n <clipPath id=\"upset-323\"><path d=\"M220 212 L426 270 V380 H220Z\"/></clipPath><clipPath id=\"upset-677\"><path d=\"M574 270 L780 212 V380 H574Z\"/></clipPath></defs><g class=\"tf-breathe\"><g id=\"normal\" class=\"tf-expression active\"><g fill=\"#ff646f\" opacity=\".94\"><ellipse cx=\"253\" cy=\"390\" rx=\"35\" ry=\"18\"/><ellipse cx=\"747\" cy=\"390\" rx=\"35\" ry=\"18\"/></g><g class=\"tf-eye tf-blink\"><circle cx=\"323\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"346\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"286\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><g class=\"tf-eye tf-blink\"><circle cx=\"677\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"700\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"640\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><g class=\"tf-rest-mouth\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M474 385 Q500 447 526 385\"/></g></g><g id=\"happy\" class=\"tf-expression\"><g fill=\"#ff646f\" opacity=\".94\"><ellipse cx=\"253\" cy=\"390\" rx=\"35\" ry=\"18\"/><ellipse cx=\"747\" cy=\"390\" rx=\"35\" ry=\"18\"/></g><g class=\"tf-eye tf-blink\"><path d=\"M241 297 Q323 162 405 297\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"29\" stroke-linecap=\"round\"/></g><g class=\"tf-eye tf-blink\"><path d=\"M595 297 Q677 162 759 297\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"29\" stroke-linecap=\"round\"/></g><g class=\"tf-rest-mouth\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M441 382 Q500 431 559 382 Q546 455 500 458 Q454 455 441 382Z\" fill=\"#238ed5\" stroke=\"none\"/><path d=\"M473 443 Q500 429 527 443\" stroke=\"#83d6ff\" stroke-width=\"9\"/></g></g><g id=\"sad\" class=\"tf-expression\"><g fill=\"#ff646f\" opacity=\".94\"><ellipse cx=\"253\" cy=\"390\" rx=\"35\" ry=\"18\"/><ellipse cx=\"747\" cy=\"390\" rx=\"35\" ry=\"18\"/></g><g class=\"tf-eye tf-blink\"><g clip-path=\"url(#sad-323)\"><circle cx=\"323\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"346\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"286\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><path d=\"M253 246 Q323 270 393 246\" stroke=\"#182027\" fill=\"none\" stroke-width=\"13\"/></g><g class=\"tf-eye tf-blink\"><g clip-path=\"url(#sad-677)\"><circle cx=\"677\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"700\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"640\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><path d=\"M607 246 Q677 270 747 246\" stroke=\"#182027\" fill=\"none\" stroke-width=\"13\"/></g><g class=\"tf-rest-mouth\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M470 422 Q500 378 530 422\"/></g><path class=\"tf-tear\" d=\"M245 337 C245 337 226 362 226 374 A19 19 0 0 0 264 374 C264 362 245 337 245 337Z\" fill=\"#67ceff\"/><circle cx=\"238\" cy=\"375\" r=\"5\" fill=\"#d8f9ff\"/></g><g id=\"angry\" class=\"tf-expression\"><g fill=\"#ff646f\" opacity=\".94\"><ellipse cx=\"253\" cy=\"390\" rx=\"35\" ry=\"18\"/><ellipse cx=\"747\" cy=\"390\" rx=\"35\" ry=\"18\"/></g><g class=\"tf-eye tf-blink\"><g clip-path=\"url(#upset-323)\"><circle cx=\"323\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"346\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"286\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><path d=\"M245 168 L401 202\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"16\" stroke-linecap=\"round\"/></g><g class=\"tf-eye tf-blink\"><g clip-path=\"url(#upset-677)\"><circle cx=\"677\" cy=\"275\" r=\"79\" fill=\"url(#iris)\"/><circle cx=\"700\" cy=\"250\" r=\"30\" fill=\"#f6fbff\"/><circle cx=\"640\" cy=\"313\" r=\"9\" fill=\"#dcf5ff\"/></g><path d=\"M599 202 L755 168\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"16\" stroke-linecap=\"round\"/></g><g class=\"tf-rest-mouth\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M468 417 Q500 399 532 417\"/></g></g><g id=\"surprised\" class=\"tf-expression\"><g fill=\"#ff646f\" opacity=\".94\"><ellipse cx=\"253\" cy=\"390\" rx=\"35\" ry=\"18\"/><ellipse cx=\"747\" cy=\"390\" rx=\"35\" ry=\"18\"/></g><g class=\"tf-eye tf-blink\"><circle cx=\"323\" cy=\"263\" r=\"92\" fill=\"url(#iris)\"/><circle cx=\"347\" cy=\"235\" r=\"32\" fill=\"#f6fbff\"/><circle cx=\"281\" cy=\"307\" r=\"10\" fill=\"#dcf5ff\"/></g><g class=\"tf-eye tf-blink\"><circle cx=\"677\" cy=\"263\" r=\"92\" fill=\"url(#iris)\"/><circle cx=\"701\" cy=\"235\" r=\"32\" fill=\"#f6fbff\"/><circle cx=\"635\" cy=\"307\" r=\"10\" fill=\"#dcf5ff\"/></g><g class=\"tf-rest-mouth\" fill=\"none\" stroke=\"#238ed5\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><ellipse cx=\"500\" cy=\"404\" rx=\"25\" ry=\"36\"/></g></g><g id=\"tf-speaking-mouth\" style=\"display:none\"><ellipse cx=\"500\" cy=\"409\" rx=\"24\" ry=\"2\" fill=\"#238ed5\"/><path d=\"M486 420 Q500 414 514 420\" fill=\"none\" stroke=\"#83d6ff\" stroke-width=\"5\" stroke-linecap=\"round\"/></g></g></svg>"+'</div><div id="tf-caption" role="status"></div><div id="tf-voice-controls"></div>';
 document.body.append(root);
 const gear=document.createElement('button');gear.id='tf-gear';gear.type='button';gear.textContent='⚙';gear.title='گفتگو و تنظیمات';gear.setAttribute('aria-label','بازکردن گفتگو و تنظیمات');gear.setAttribute('aria-expanded','false');document.body.append(gear);
 const menu=document.createElement('nav');menu.id='tf-menu';menu.hidden=true;menu.setAttribute('aria-label','گفتگو و تنظیمات');
 menu.innerHTML='<h2>گفتگو و تنظیمات تیمو</h2><div id="tf-menu-actions"></div><label>حالت چهره</label><div class="tf-expressions" id="tf-expressions"></div><button id="tf-auto" type="button">واکنش خودکار به گفتگو</button><p id="tf-mode-note">حالت چهره از پاسخ ایجنت انتخاب می‌شود.</p>';
 document.body.append(menu);
 const manager=document.createElement('section');manager.id='tf-manager';manager.hidden=true;manager.innerHTML='<div id="tf-manager-bar"><button id="tf-manager-back" type="button">بازگشت به چهره</button><span id="tf-manager-title"></span></div>';
 document.body.append(manager);
 const art=$('tf-art-host'),mouth=art.querySelector('#tf-speaking-mouth'),lip=mouth.querySelector('ellipse');
 function expression(name){
  if(!modes.includes(name))return false;
  art.querySelectorAll('.tf-expression').forEach(x=>x.classList.toggle('active',x.id===name));root.dataset.expression=name;
  root.setAttribute('aria-label','چهرهٔ تیمو: '+labels[name]);return true;
 }
 function amount(value){
  value=Math.max(0,Math.min(1,Number.isFinite(value)?value:0));const open=value>.025;
  root.dataset.mouth=open?'open':'closed';mouth.style.display=open?'':'none';lip.setAttribute('rx',String(17+value*24));lip.setAttribute('ry',String(3+value*38));
  const shine=mouth.querySelector('path');shine.style.opacity=String(value*.75);
 }
 function hideMenu(){menu.hidden=true;gear.setAttribute('aria-expanded','false');}
 function showFace(){view='face';root.hidden=false;manager.hidden=true;document.body.classList.add('tf-mode');hideMenu();}
 function showChat(focus=false){view='chat';root.hidden=true;manager.hidden=true;document.body.classList.remove('tf-mode');hideMenu();if(focus)$('messageInput')?.focus();$('messages')?.scrollTo?.(0,$('messages').scrollHeight);}
 function openManager(section){
  hideMenu();manager.hidden=false;view='manager';$('tf-manager-title').textContent=section==='rooms'?'مدیریت اتاق‌ها':'آموزش و حافظهٔ ایجنت';
  if(!frame){frame=document.createElement('iframe');frame.title='مدیریت ایجنت';frame.setAttribute('sandbox','allow-scripts allow-forms allow-same-origin');manager.append(frame);}
  if(!positionRelay){
   positionRelay=true;const previous=window.onTimoAgentPosition;
   window.onTimoAgentPosition=result=>{
    try{if(typeof previous==='function')previous(result);}catch(_){}
    try{const w=frame?.contentWindow;if(w&&w.location.origin===location.origin&&w.location.pathname==='/agent'&&typeof w.onTimoAgentPosition==='function')w.onTimoAgentPosition(result);}catch(_){}
   };
  }
  frame.onload=()=>{
   try{
    if(window.AndroidRobot&&!frame.contentWindow.AndroidRobot)frame.contentWindow.AndroidRobot=window.AndroidRobot;

    frame.contentDocument.querySelector('[data-tab="'+section+'"]')?.click();
    frame.contentDocument.querySelectorAll('a[href="/"]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();showFace();}));
   }catch(_){ }
  };
  if(!frame.getAttribute('src'))frame.src='/agent';else frame.onload();
 }
 function button(host,label,callback){const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',callback);host.append(b);return b;}
 function clickOriginal(id){const target=$(id);if(target&&!target.disabled)target.click();sync();}
 const actions=$('tf-menu-actions');
 button(actions,'بازگشت به چهرهٔ تمام‌صفحه',showFace);
 button(actions,'نوشتن پیام',()=>showChat(true));button(actions,'مشاهدهٔ گفتگو',()=>showChat());
 button(actions,'آموزش ایجنت و مدیریت حافظه',()=>openManager('memories'));button(actions,'مدیریت اتاق‌ها',()=>openManager('rooms'));
 button(actions,'تنظیمات حرکت ربات',()=>{hideMenu();clickOriginal('agentRobotSettings');});
 button(actions,'صدا و میکروفن',()=>{showChat();$('startBtn')?.focus();});
 button(actions,'سلام شخصی و شناسایی افراد',()=>{showChat();clickOriginal('agentHostButton');});
 button(actions,'گفتگوی تازه',()=>{hideMenu();clickOriginal('newConversationBtn');});
 for(const name of modes)button($('tf-expressions'),labels[name],()=>{manual=true;clearTimeout(returnTimer);expression(name);$('tf-mode-note').textContent='انتخاب دستی: '+labels[name]+'؛ برای واکنش به پاسخ‌ها، حالت خودکار را بزن.';});
 $('tf-auto').onclick=()=>{manual=false;expression(lastFace);$('tf-mode-note').textContent='واکنش خودکار به گفتگو فعال است.';};
 gear.onclick=()=>{armAudio();menu.hidden=!menu.hidden;gear.setAttribute('aria-expanded',String(!menu.hidden));};
 $('tf-manager-back').onclick=showFace;
 const voice=$('tf-voice-controls'),mirrors=[];
 for(const [id,label] of [['startBtn','🎙 شروع گفتگو'],['timoFinishTurnBtn','✓ پایان صحبت و ارسال'],['timoCutReplyBtn','قطع پاسخ'],['stopBtn','پایان گفتگو'],['agentStopBtn','■ توقف حرکت']]){
  const b=button(voice,label,()=>{armAudio();clickOriginal(id);});if(id==='agentStopBtn')b.className='tf-danger';mirrors.push([id,b]);
 }
 function sync(){
  for(const [id,b] of mirrors){const original=$(id);b.hidden=!original || original.style.display==='none';b.disabled=!original || original.disabled;}
  const text=$('status')?.textContent || 'برای صحبت، شروع گفتگو را بزنید.';$('tf-caption').textContent=text.replace(/\s*\[[^\]]+\]/g,'');
 }
 const observer=new MutationObserver(sync);
 if($('status'))observer.observe($('status'),{childList:true,subtree:true,characterData:true});
 const controls=document.querySelector('.voice-controls');if(controls)observer.observe(controls,{childList:true,subtree:true,attributes:true,attributeFilter:['style','disabled']});
 document.addEventListener('click',e=>{if(!menu.hidden&&!menu.contains(e.target)&&e.target!==gear)hideMenu();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!menu.hidden)hideMenu();else if(view!=='face')showFace();}});
 function armAudio(){
  try{if(!context){const C=window.AudioContext||window.webkitAudioContext;if(C)context=new C();}context?.resume()?.catch(()=>{});}catch(_){}
 }
 // Only route media through Web Audio after a running context is available;
 // otherwise keep the browser's original audio output and use playback events.
 function bindAudio(player,token){
  if(token!==turn)return ()=>{};detach();
  const record={player,token,frame:0,source:null,analyser:null,data:null,stopped:false,listeners:[],smooth:0,last:0};binding=record;
  const current=()=>mounted&&binding===record&&turn===token&&!record.stopped;
  function listen(name,fn){player.addEventListener(name,fn);record.listeners.push([name,fn]);}
  function closed(){if(current()){record.smooth=0;amount(0);cancelAnimationFrame(record.frame);record.frame=0;}}
  function tick(at){
   record.frame=0;if(!current()||document.hidden||player.paused||player.ended)return closed();
   if(at-record.last>=33){
    let level=0;
    if(record.analyser){record.analyser.getByteTimeDomainData(record.data);let sum=0;for(const x of record.data)sum+=(x-128)*(x-128);const rms=Math.sqrt(sum/record.data.length)/128;level=rms<.018?0:Math.min(1,rms*6.5);}
    else if(player.readyState>=3){level=.12+.38*Math.abs(Math.sin(player.currentTime*16))*(.6+.4*Math.sin(player.currentTime*7));}
    record.smooth=level===0?record.smooth*.4:record.smooth*.35+level*.65;amount(record.smooth);record.last=at;
   }
   record.frame=requestAnimationFrame(tick);
  }
  function playing(){if(current()&&!record.frame)record.frame=requestAnimationFrame(tick);}
  if(context?.state==='running' && new URL(player.src,location.href).origin===location.origin){
   try{
    const analyser=context.createAnalyser();analyser.fftSize=1024;
    const source=context.createMediaElementSource(player);record.source=source;
    source.connect(analyser);analyser.connect(context.destination);record.analyser=analyser;record.data=new Uint8Array(analyser.fftSize);
   }catch(_){try{record.source?.disconnect();record.source?.connect(context.destination);}catch(_){}record.analyser=null;}
  }
  root.dataset.meter=record.analyser?'rms':'playback';
  listen('playing',playing);for(const event of ['pause','ended','error','waiting','stalled','emptied'])listen(event,closed);
  if(!player.paused&&player.readyState>=3)playing();
  return ()=>detach(record);
 }
 function detach(record=binding){
  if(!record)return;record.stopped=true;cancelAnimationFrame(record.frame);for(const [event,fn] of record.listeners)record.player.removeEventListener(event,fn);
  try{record.source?.disconnect();record.analyser?.disconnect();}catch(_){}
  if(binding===record){binding=null;amount(0);}
 }
 function cancel(){clearTimeout(returnTimer);turn=null;detach();amount(0);}
 window.TimoFace={
  begin(token){cancel();turn=token;explicit=false;if(!manual)expression('normal');if(view==='chat')showFace();sync();},
  response(face,token){if(token!==turn)return;const mode=face?.expression==='upset'?'sad':face?.expression;lastFace=modes.includes(mode)?mode:'normal';explicit=face?.source==='explicit';if(explicit){manual=false;clearTimeout(returnTimer);$('tf-mode-note').textContent='فرمان چهره اجرا شد: '+labels[lastFace]+'؛ واکنش خودکار فعال است.';}if(!manual)expression(lastFace);},
  bindAudio,cancel,armAudio,showFace,showChat,
  complete(token){if(token!==turn)return;detach();clearTimeout(returnTimer);if(!manual&&!explicit)returnTimer=setTimeout(()=>{if(turn===token&&!manual)expression('normal');},6000);},
  back(){if(!menu.hidden){hideMenu();return true;}if(view!=='face'){showFace();return true;}return false;},
  state(){return {turn,expression:root.dataset.expression,manual,meter:root.dataset.meter||'none',view};}
 };
 document.addEventListener('visibilitychange',()=>{if(document.hidden){if(binding){cancelAnimationFrame(binding.frame);binding.frame=0;}amount(0);}else if(binding&&!binding.player.paused)binding.player.dispatchEvent(new Event('playing'));});
 window.addEventListener('pagehide',()=>{mounted=false;cancel();observer.disconnect();context?.close()?.catch(()=>{});});
 document.body.classList.add('tf-enabled');expression('normal');showFace();sync();
})();
