/* Explicit commands to enabled destinations dispatch directly in the updated robot app. */
(() => {
  let currentNotice=null;
  let motionMessage=null;
  const handledNavigation=new WeakSet();
  let commandEpoch=0;
  const Native=window.AndroidRobot;
  const syncWaiters=new Map();
  let syncSerial=0;
  // پیش از ارسال حرکت، نسخهٔ نقشه را از سرور می‌گیریم و منتظر تأیید اپ اندروید می‌مانیم.
  async function syncMap(){
    if(!Native?.requestAgentNavigation)throw new Error('همگام‌سازی نقشه فقط داخل اپ ربات انجام می‌شود.');
    const abort=new AbortController(), timer=setTimeout(()=>abort.abort(),5000);
    let cfg;
    try {
      const response=await fetch('/api/agent/motion-config',{cache:'no-store',signal:abort.signal});
      if(!response.ok)throw new Error('دریافت نقشهٔ مشترک ناموفق بود؛ بک‌اند را بررسی کنید.');
      cfg=await response.json();
    }finally{clearTimeout(timer);}
    if(!cfg.configured||typeof cfg.map_name!=='string'||!cfg.map_name.trim()||typeof cfg.revision!=='string'||!cfg.revision)
      throw new Error('در صفحهٔ آموزش ایجنت، نقشهٔ مشترک مجموعه را یک‌بار ذخیره کنید.');
    const requestId=Date.now()+'-'+(++syncSerial);
    await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>{syncWaiters.delete(requestId);reject(new Error('اپ همگام‌سازی را تأیید نکرد؛ نسخهٔ جدید APK را نصب کنید.'));},4000);
      syncWaiters.set(requestId,{resolve,reject,timeout});
      try{Native.requestAgentNavigation(JSON.stringify({type:'sync_map',request_id:requestId,map_name:cfg.map_name,revision:cfg.revision}));}
      catch(error){clearTimeout(timeout);syncWaiters.delete(requestId);reject(error);}
    });
    return cfg;
  }
  const syncQuietly=()=>syncMap().catch(()=>{});
  function notice(){motionMessage=null;if(currentNotice)currentNotice.remove();const box=document.createElement('div');box.className='agent-notice';document.getElementById('messages').append(box);currentNotice=box;return box;}
  function paragraph(box,text){const p=document.createElement('p');p.textContent=text;box.append(p);return p;}
  function button(box,text,callback,secondary=false){const b=document.createElement('button');b.textContent=text;b.type='button';if(secondary)b.className='secondary';b.addEventListener('click',callback);box.append(b);return b;}
  const navStatus=document.getElementById('agentMotionStatus');
  function stop(){
    // افزایش شمارنده، فرمانی را که هنوز منتظر همگام‌سازی است از اعتبار می‌اندازد.
    ++commandEpoch;
    motionMessage=null;
    if(currentNotice){currentNotice.remove();currentNotice=null;}
    if(!Native?.stopAgentNavigation){navStatus.textContent='لغو حرکت فقط از داخل اپ ربات انجام می‌شود.';return;}
    Native.stopAgentNavigation();navStatus.textContent='درخواست لغو ناوبری ارسال شد؛ توقف واقعی را بررسی کنید.';
  }
  document.getElementById('agentStopBtn')?.addEventListener('click',stop);
  document.getElementById('agentRobotSettings')?.addEventListener('click',async()=>{
    if(Native?.openAgentRobotSettings){
      try{await syncMap();}catch(error){navStatus.textContent=error.message;}
      Native.openAgentRobotSettings();
    }else navStatus.textContent='تنظیمات حرکت روی خود ربات در دسترس است.';
  });
  window.onTimoAgentMotion=result=>{
    if(result.event==='map_synced'){
      const pending=syncWaiters.get(result.request_id);
      if(pending){clearTimeout(pending.timeout);syncWaiters.delete(result.request_id);pending.resolve();}
      return;
    }
    navStatus.textContent=result.message;if(motionMessage)motionMessage.textContent=result.message;
  };
  window.TimoAgent={
    cancelProposal(){++commandEpoch;motionMessage=null;if(currentNotice){currentNotice.remove();currentNotice=null;}try{Native?.dismissAgentNavigation?.();}catch(_){}},
    async handle(result,sessionId){
      if(result.action?.type==='stop'){stop();return;}
      if(result.action?.type==='navigate'){
        if(handledNavigation.has(result.action))return;
        handledNavigation.add(result.action);
        if(document.hidden){navStatus.textContent='فرمان حرکت ارسال نشد؛ صفحهٔ گفتگو را باز کنید و دستور را دوباره بدهید.';return;}
        const epoch=++commandEpoch;
        const box=notice();paragraph(box,`مقصد: ${result.action.name} · نقشه: ${result.action.map_name}`);
        if(!Native?.requestAgentNavigation){paragraph(box,'فرمان حرکت ارسال نشد. این صفحه را در اپ به‌روز‌شدهٔ ربات باز کنید.');return;}
        try{
          if(Native.agentMotionMode?.()!=='direct-v2'){paragraph(box,'فرمان ارسال نشد؛ نسخهٔ اصلاح حرکت مستقیم را روی ربات نصب کنید.');return;}
          motionMessage=paragraph(box,'در حال ارسال درخواست حرکت…');
          navStatus.textContent=motionMessage.textContent;
          const cfg=await syncMap();
          if(epoch!==commandEpoch)return; // Stop/new turn invalidated this pending command.
          // Awaiting the network must not let a now-hidden page start motion.
          if(document.hidden)throw new Error('صفحهٔ گفتگو بسته شد؛ فرمان را دوباره بدهید.');
          if(result.action.map_name!==cfg.map_name)throw new Error('نقشهٔ مقصد «'+result.action.map_name+'» با نقشهٔ مشترک «'+cfg.map_name+'» یکی نیست؛ مقصد را در آموزش بررسی کنید.');
          // ارسال درخواست به پل اندروید به معنی رسیدن ربات به مقصد نیست.
          Native.requestAgentNavigation(JSON.stringify({...result.action,map_revision:cfg.revision}));
          button(box,'توقف',stop,true);
        }catch(error){if(epoch!==commandEpoch)return;navStatus.textContent=error.message||'ارتباط با اپ ربات برقرار نشد.';if(motionMessage)motionMessage.textContent=navStatus.textContent;}
        return;
      }
      if(result.proposal?.kind==='memory'){
        window.TimoFace?.showChat();
        const box=notice(), proposal=result.proposal;
        paragraph(box,'پیش‌نویس یادگیری — قبل از ثبت بررسی کنید:');
        const text=document.createElement('pre');text.textContent=`${proposal.payload.title}\n${proposal.payload.body}`;box.append(text);
        const key=document.createElement('input');key.type='password';key.autocomplete='off';key.placeholder='کلید مدیر برای ذخیره';key.className='agent-key-input';box.append(key);
        const save=button(box,'تأیید و یادگیری',async()=>{
          save.disabled=true;
          try{
            const managerKey=key.value.trim()||sessionStorage.getItem('timo-agent-manager-key')||'';
            const response=await fetch('/api/agent/confirm-memory',{method:'POST',headers:{'Content-Type':'application/json','X-Agent-Key':managerKey},body:JSON.stringify({proposal_id:proposal.id,session_id:sessionId})});
            const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'ثبت اطلاعات ناموفق بود.');
            key.value='';box.replaceChildren();paragraph(box,'در حافظهٔ دائمی ثبت شد. برای اصلاح یا حذف، بخش آموزش را باز کنید.');
          }catch(e){paragraph(box,e.message);save.disabled=false;}
        });button(box,'ذخیره نشود',()=>box.remove(),true);return;
      }
      if(result.room_draft){window.TimoFace?.showChat();sessionStorage.setItem('timo-room-draft',result.room_draft.name);const box=notice();paragraph(box,`اتاق پیشنهادی: ${result.room_draft.name}`);const a=document.createElement('a');a.href='/agent';a.textContent='بازکردن آموزش و دریافت موقعیت';box.append(a);}
    }
  };
  if(Native?.agentHeartbeat){
    const beat=()=>{if(!document.hidden)try{Native.agentHeartbeat();}catch(_){}};
    beat();setInterval(beat,1000);
    syncQuietly();setInterval(()=>{if(!document.hidden)syncQuietly();},10000);
    document.addEventListener('visibilitychange',()=>{if(document.hidden){++commandEpoch;try{Native.stopAgentNavigation();}catch(_){}}else beat();});
    window.addEventListener('pagehide',()=>{++commandEpoch;try{Native.stopAgentNavigation();}catch(_){}});
  }
})();
