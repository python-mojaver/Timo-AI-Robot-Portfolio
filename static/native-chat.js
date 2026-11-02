/* TIMO_NATIVE_CHAT_V1_3: independent listening and cancellable response turns. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id), bridge=window.TimoChatSpeech;
 if(!bridge&&!window.AndroidRobot)return;
 const show=text=>{if($('status'))$('status').textContent=text;};
 if(!bridge||typeof bridge.startConfigured!=='function'){
  const message='نسخهٔ گفتار ۱٫۳ داخل اپ نصب نیست؛ پروژهٔ اصلی اندروید را با Run app اجرا کنید. [NC1.3-APK]';
  if($('startBtn'))$('startBtn').onclick=()=>show(message);show(message);return;
 }
 if(!window.sendMessage||!window.speak||!window.interrupt||!$('startBtn')||!$('stopBtn')){
  show('بارگذاری کد گفتگو کامل نشد؛ صفحه را دوباره باز کنید. [NC1.3-JS]');return;
 }
 const originalSend=window.sendMessage,originalSpeak=window.speak,originalStop=window.stopConversation;
 let enabled=false,liveId=null,ready=false,finishing=false,retry=0,serial=0,turnSerial=0,turn=null;
 let speaking=false,ttsText='',echoUntil=0,errorCount=0,lastRms=null,lastCandidate='',candidateSince=0,heardDuringPlayback=false;
 const prefix=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8);
 const languages={'fa-IR':'فارسی','en-US':'English','tr-TR':'ترکی استانبولی — Türkçe','az-AZ':'ترکی آذربایجانی — Azərbaycanca','auto':'تشخیص خودکار — در صورت پشتیبانی دستگاه'};
 let language='fa-IR',barge=true;
 try{language=localStorage.getItem('timo.voice.language')||language;barge=localStorage.getItem('timo.voice.barge')!=='false';}catch(_){}
 if(!Object.hasOwn(languages,language))language='fa-IR';
 let detectedLanguage=language==='auto'?'fa-IR':language;
 const settings=document.createElement('section');settings.id='timoVoiceSettings';settings.dir='rtl';
 settings.style.cssText='padding:12px;border:1px solid #647b8a66;border-radius:12px;margin:10px 0;color:inherit;font:14px Tahoma';
 const label=document.createElement('label');label.textContent='زبان گفتگو ';label.htmlFor='timoVoiceLanguage';
 const select=document.createElement('select');select.id='timoVoiceLanguage';select.style.cssText='width:100%;padding:9px;margin:7px 0;border-radius:8px';
 for(const [value,name] of Object.entries(languages)){const option=document.createElement('option');option.value=value;option.textContent=name;select.append(option);}
 select.value=language;settings.append(label,select);
 const checkLabel=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.id='timoVoiceBarge';check.checked=barge;
 checkLabel.append(check,document.createTextNode(' قطع خودکار پاسخ با صحبت من'));settings.append(checkLabel);
 const diagnostic=document.createElement('div');diagnostic.id='timoVoiceDiagnostic';diagnostic.style.cssText='font-size:11px;opacity:.8;margin-top:9px;line-height:1.7';settings.append(diagnostic);
 const host=$('tf-menu')||document.querySelector('.voice-controls')||$('startBtn').parentElement;host.append(settings);
 const finish=document.createElement('button');finish.id='timoFinishTurnBtn';finish.type='button';finish.textContent='✓ پایان صحبت و ارسال';
 finish.style.cssText='background:#087f8c;color:white;padding:12px 20px;border:0;border-radius:12px;display:none';$('startBtn').after(finish);
 function buttons(){
  $('startBtn').style.display=enabled?'none':'inline-block';$('stopBtn').style.display=enabled?'inline-block':'none';
  finish.style.display=enabled?'inline-block':'none';finish.disabled=!ready||finishing||!liveId;
  diagnostic.textContent='گفتار '+bridge.getVersion()+' | '+(enabled?(ready?'در حال شنیدن':'آماده‌سازی'):'متوقف')+' | '+languages[language]+(lastRms===null?'':' | سطح ورودی: '+lastRms.toFixed(1));
 }
 const normalize=text=>String(text||'').normalize('NFKC').toLocaleLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
 function echoLike(input,reference){
  const a=normalize(input),b=normalize(reference);if(!a||!b)return false;
  if((' '+b+' ').includes(' '+a+' '))return true;
  const words=a.split(' '),spoken=new Set(b.split(' '));
  return words.length>=2&&words.filter(w=>spoken.has(w)).length/words.length>=.8;
 }
 function isEcho(text){return (speaking||heardDuringPlayback||Date.now()<echoUntil)&&echoLike(text,ttsText);}
 function busy(){return !!turn;}
 function statusListening(){if(!busy()&&enabled)show(ready?'🎤 سؤال بعدی را بپرسید.':'در حال آماده‌سازی شنیدن…');}
 function cancelInput(){clearTimeout(retry);retry=0;liveId=null;ready=false;finishing=false;try{bridge.cancel();}catch(_){}buttons();}
 function schedule(delay=180){
  clearTimeout(retry);retry=0;if(!enabled||document.hidden||liveId)return;
  if(!barge&&busy())return;
  retry=setTimeout(listen,delay);
 }
 function listen(){
  retry=0;if(!enabled||document.hidden||liveId||(!barge&&busy()))return;
  try{
   if(!bridge.isAvailable())throw Error('unavailable');
   liveId=prefix+'-'+(++serial);ready=false;finishing=false;lastCandidate='';candidateSince=0;heardDuringPlayback=false;buttons();
   if(!busy())show('در حال اتصال به سرویس گفتار… [NC1.3]');
   bridge.startConfigured(liveId,JSON.stringify({language,autoLanguage:language==='auto'}));
  }catch(_){enabled=false;cancelInput();show('سرویس گفتار در دسترس نیست؛ تنظیمات یا دسترسی میکروفن را بررسی کنید.');}
 }
 function cancelReply(reason){
  turn=null;turnSerial++;speaking=false;echoUntil=Date.now()+450;
  window.interrupt();
  console.info('[TIMO-CHAT-1.3] reply_cancelled reason='+reason);buttons();
 }
 function stop(){enabled=false;cancelInput();turn=null;turnSerial++;speaking=false;originalStop();buttons();}
 function maybeInterrupt(text,final=false){
  if(!barge||!busy()||isEcho(text))return false;
  const candidate=normalize(text);if(!candidate)return false;
  // Recognition text confirms a new utterance. RMS alone is deliberately not a
  // loudspeaker interrupt trigger: the robot's own voice can raise that meter.
  const letters=candidate.replace(/[^\p{L}\p{N}]/gu,'').length;
  if(!final&&letters<3)return false;
  const now=Date.now();if(candidate!==lastCandidate){lastCandidate=candidate;candidateSince=now;}
  if(!final&&candidate.split(' ').length===1&&letters<5&&now-candidateSince<160)return false;
  cancelReply('new_speech');show('🎤 پاسخ قطع شد؛ ادامهٔ صحبت شما را می‌شنوم.');return true;
 }
 originalStop();
 window.sendMessage=async function(...args){
  const mine=++turnSerial;turn=mine;errorCount=0;
  if(!barge)cancelInput();else schedule();buttons();
  try{return await originalSend.apply(this,args);}
  finally{if(turn===mine){turn=null;speaking=false;echoUntil=Date.now()+350;buttons();statusListening();schedule();}}
 };
 window.speak=async function(...args){
  const mine=turn;ttsText=String(args[0]||'');
  if(!barge)cancelInput();else schedule();
  try{return await originalSpeak.apply(this,args);}
  finally{if(turn===mine){speaking=false;echoUntil=Date.now()+350;buttons();statusListening();schedule();}}
 };
 window.stopConversation=stop;
 const dialogue=window.TimoDialogue;
 if(dialogue&&typeof dialogue.canGreet==='function'){
  const canGreet=dialogue.canGreet;dialogue.canGreet=function(){return !enabled&&canGreet.call(this);};
 }
 // Events come from the real HTMLAudioElement lifecycle, not from TTS requests.
 document.addEventListener('timo:audio-state',event=>{
  const d=event.detail||{};
  if(d.state==='playing'){speaking=true;ttsText=String(d.text||ttsText);}
  else if(d.state==='ended'||d.state==='cancelled'||d.state==='failed'){speaking=false;echoUntil=Date.now()+450;}
  if(enabled)schedule();
 });
 window.onTimoChatSpeech=message=>{
  let event;try{event=typeof message==='string'?JSON.parse(message):message;}catch(_){return;}
  if(!event||typeof event!=='object')return;
  if(event.type==='paused'){stop();return;}
  if(!enabled||!liveId||event.id!==liveId)return;
  if(event.type!=='partial'&&event.type!=='rms')console.info('[TIMO-CHAT-1.3] event='+event.type+' code='+(event.code||0));
  if(event.type==='preparing'){if(!busy())show('آماده‌سازی میکروفن…');}
  else if(event.type==='ready'){ready=true;finishing=false;buttons();statusListening();}
  else if(event.type==='rms'){const n=Number(event.rms);if(Number.isFinite(n)){lastRms=n;buttons();}}
  else if(event.type==='language'){
   if(Object.hasOwn(languages,event.language)&&event.language!=='auto')detectedLanguage=event.language;
  }
  else if(event.type==='speaking'){
   if(speaking)heardDuringPlayback=true;
   // During model/TTS preparation no loudspeaker audio is playing, so genuine
   // speech can cancel immediately. During playback wait for non-echo text.
   if(barge&&busy()&&!speaking&&Date.now()>=echoUntil)cancelReply('speech_during_preparation');
   if(!busy())show('🎤 ادامه بدهید…');
  }
  else if(event.type==='partial'){
   if(speaking)heardDuringPlayback=true;
   const text=typeof event.text==='string'?event.text:'';
   if(isEcho(text))return;
   maybeInterrupt(text);
   if(!busy()&&$('messageInput'))$('messageInput').value=text;
  }
  else if(event.type==='speech_end'){ready=false;finishing=true;buttons();if(!busy())show('در انتظار متن نهایی…');}
  else if(event.type==='final'){
   const text=typeof event.text==='string'?event.text.trim():'';
   const echo=isEcho(text);liveId=null;ready=false;finishing=false;buttons();
   if(echo||!text){schedule(160);return;}
   if(busy()&&!barge){schedule();return;}
   errorCount=0;maybeInterrupt(text,true);if($('messageInput'))$('messageInput').value='';
   window.sendMessage(text,'voice').catch(()=>{show('پاسخ دریافت نشد؛ اتصال سرور را بررسی کنید.');});
  }
  else if(event.type==='error'){
   liveId=null;ready=false;finishing=false;buttons();const code=Number(event.code);
   if([6,7].includes(code)){statusListening();schedule(350);}
   else if([1,2,3,4,5,8,11,-2,-3,-4].includes(code)&&errorCount++<3){
    if(!busy())show('تلاش دوباره برای اتصال گفتار…');schedule(Math.min(2500,500*errorCount));
   }else{enabled=false;cancelInput();show(event.text||'سرویس گفتار پاسخ نداد؛ تنظیمات زبان و میکروفن را بررسی کنید.');}
  }
 };
 $('startBtn').onclick=()=>{stop();enabled=true;errorCount=0;buttons();listen();};$('stopBtn').onclick=stop;
 finish.onclick=()=>{
  if(!enabled||!liveId||!ready||finishing)return;
  finishing=true;buttons();try{bridge.finish(liveId);}catch(_){cancelInput();schedule();}
 };
 const cut=$('timoCutReplyBtn');if(cut)cut.onclick=()=>{cancelReply('button');statusListening();schedule(0);};
 select.onchange=()=>{
  language=select.value;detectedLanguage=language==='auto'?'fa-IR':language;
  try{localStorage.setItem('timo.voice.language',language);}catch(_){}
  cancelReply('language_change');cancelInput();if(enabled)schedule(0);buttons();
 };
 check.onchange=()=>{
  barge=check.checked;try{localStorage.setItem('timo.voice.barge',String(barge));}catch(_){}
  if(!barge&&busy())cancelInput();else schedule(0);buttons();
 };
 window.TimoVoice={
  language:()=>detectedLanguage,
  state:()=>({enabled,ready,listening:!!liveId,busy:busy(),speaking,barge,language,detectedLanguage,rms:lastRms,version:'1.3'}),
  policy:{normalize,echoLike},cancelReply:()=>{cancelReply('external');schedule(0);}
 };
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});window.addEventListener('beforeunload',stop);
 buttons();show('گفتار آماده است؛ شروع گفتگو را بزنید. [NC1.3]');
})();
