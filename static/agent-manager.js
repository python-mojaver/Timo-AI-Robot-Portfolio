/* All text from the knowledge store is rendered as text, never HTML. */
(() => {
  const $ = id => document.getElementById(id);
  const keyName = 'timo-agent-manager-key';
  let key = sessionStorage.getItem(keyName) || '', state = null;
  const forms = {memories: $('memoryForm'), rooms: $('roomForm'), skills: $('skillForm')};
  function report(text, error=false) { $('managerStatus').textContent=text; $('managerStatus').classList.toggle('error',error); }
  async function api(path, method='GET', data) {
    const res=await fetch('/api/agent/'+path,{method,headers:{'X-Agent-Key':key,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
    const value=await res.json();
    if(!res.ok) throw new Error(typeof value.detail==='string'?value.detail:'درخواست معتبر نیست.');
    return value;
  }
  function tab(name){document.querySelectorAll('[data-section]').forEach(x=>x.hidden=x.dataset.section!==name);document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===name));}
  document.querySelectorAll('[data-tab]').forEach(x=>x.addEventListener('click',()=>tab(x.dataset.tab)));
  function field(form,name){return form.elements.namedItem(name);}
  function edit(table,row) {
    const form=forms[table];form.reset();
    Object.entries(row).forEach(([name,value])=>{
      const el=field(form,name);if(!el)return;
      if(el.type==='checkbox')el.checked=!!value;
      else el.value=Array.isArray(value)?value.join('\n'):value??'';
    });tab(table);skillKind();form.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function render(){
    for(const [table,listId] of Object.entries({memories:'memoryList',rooms:'roomList',skills:'skillList'})) {
      const host=$(listId);host.replaceChildren();
      if(!state[table].length){const p=document.createElement('p');p.textContent='هنوز موردی ثبت نشده است.';host.append(p);}
      for(const row of state[table]){
        const card=document.createElement('article');card.className='card record';
        const title=document.createElement('h3');title.textContent=row.title||row.name;
        const meta=document.createElement('div');meta.className='meta';meta.textContent=table==='memories'?(row.kind==='qa'?'سؤال و پاسخ':'اطلاعات ثبت‌شده'):(row.enabled?'فعال':'غیرفعال / پیش‌نویس');
        const body=document.createElement('pre');
        body.textContent=table==='memories'?row.body:table==='rooms'?`نقشه: ${row.map_name||'تأیید نشده'}\nX: ${row.x}  Y: ${row.y}  Z: ${row.z}\nRotation: ${row.rotation} rad\nنام‌های جایگزین: ${row.aliases.join('، ')}`:`عبارت‌ها: ${row.triggers.join('، ')}\n${row.kind==='reply'?row.reply:'مقصد: '+(state.rooms.find(r=>r.id===row.room_id)?.name||'حذف شده')}`;
        const actions=document.createElement('div');actions.className='actions';
        const change=document.createElement('button');change.textContent='ویرایش';change.className='secondary';change.addEventListener('click',()=>edit(table,row));
        const remove=document.createElement('button');remove.textContent='حذف';remove.className='danger';
        remove.addEventListener('click',async()=>{if(!confirm(`«${row.title||row.name}» حذف شود؟`))return;try{await api(`${table}/${row.id}`,'DELETE');await load();report('حذف شد.');}catch(e){report(e.message,true);}});
        actions.append(change,remove);card.append(title,meta,body,actions);host.append(card);
      }
    }
    const selected=$('skillRoom').value;$('skillRoom').replaceChildren();
    for(const room of state.rooms){const op=document.createElement('option');op.value=room.id;op.textContent=room.name+(room.enabled?'':' (غیرفعال)');$('skillRoom').append(op);}
    if(selected)$('skillRoom').value=selected;
  }
  async function load(){
    state=await api('state');$('managerContent').hidden=false;render();
    const cfg=state.motion_config||{};
    $('sharedMapName').value=cfg.map_name||'';
    $('sharedMapStatus').textContent=cfg.configured?'نقشهٔ مشترک ذخیره‌شده: '+cfg.map_name:'نام نقشهٔ مشترک را یک‌بار ذخیره کنید.';
    if(!field(forms.rooms,'map_name').value)field(forms.rooms,'map_name').value=cfg.map_name||'';
  }
  $('sharedMapForm').addEventListener('submit',async e=>{
    e.preventDefault();const button=$('sharedMapForm').querySelector('button');button.disabled=true;
    try {
      const cfg=await api('motion-config','POST',{data:{map_name:$('sharedMapName').value.trim(),expected_revision:state.motion_config?.revision||''}});
      await load();report('نقشهٔ مشترک ذخیره شد؛ اپ پیش از حرکت بعدی آن را دریافت می‌کند. مختصات اتاق‌ها تغییر نکرد.');
    }catch(err){report(err.message,true);}finally{button.disabled=false;}
  });
  forms.rooms.addEventListener('reset',()=>setTimeout(()=>{
    if(state && !field(forms.rooms,'id').value)field(forms.rooms,'map_name').value=state.motion_config?.map_name||'';
  },0));
  $('managerLogin').addEventListener('submit',async e=>{e.preventDefault();key=$('managerKey').value.trim();try{await load();sessionStorage.setItem(keyName,key);$('managerKey').value='';report('دسترسی مدیر فعال است.');}catch(err){key='';$('managerContent').hidden=true;report(err.message,true);}});
  $('managerLogout').addEventListener('click',()=>{key='';state=null;sessionStorage.removeItem(keyName);$('managerContent').hidden=true;$('managerKey').value='';Object.values(forms).forEach(f=>f.reset());for(const id of ['memoryList','roomList','skillList'])$(id).replaceChildren();report('از بخش مدیریت خارج شدید.');});
  for(const [table,form] of Object.entries(forms)){
    form.addEventListener('submit',async e=>{
      e.preventDefault();const data={};
      for(const el of form.elements){if(!el.name||el.name==='id')continue;data[el.name]=el.type==='checkbox'?el.checked:el.value.trim();}
      for(const name of ['aliases','triggers'])if(name in data)data[name]=data[name].split('\n').map(x=>x.trim()).filter(Boolean);
      const id=field(form,'id').value;
      const button=form.querySelector('button:not([type])');button.disabled=true;
      try{await api(table+(id?'/'+id:''),id?'PUT':'POST',{data});form.reset();await load();report('ذخیره شد؛ تیمو از اطلاعات جدید استفاده می‌کند.');}
      catch(err){report(err.message,true);}finally{button.disabled=false;skillKind();}
    });
  }
  function skillKind(){const nav=$('skillKind').value==='navigate';$('skillReplyLabel').hidden=nav;$('skillRoomLabel').hidden=!nav;}
  $('skillKind').addEventListener('change',skillKind);$('skillForm').addEventListener('reset',()=>setTimeout(skillKind,0));
  let poseRequest=null;
  $('capturePosition').addEventListener('click',()=>{
    if(!window.AndroidRobot?.captureAgentPosition){$('poseStatus').textContent='این دکمه فقط داخل اپ به‌روز‌شدهٔ ربات کار می‌کند؛ مختصات را از AlphaMap وارد کنید.';return;}
    poseRequest=Date.now().toString();$('capturePosition').disabled=true;$('poseStatus').textContent='در حال دریافت موقعیت از SDK…';
    window.AndroidRobot.captureAgentPosition(poseRequest);
    const requestId=poseRequest;setTimeout(()=>{if(poseRequest===requestId){poseRequest=null;$('capturePosition').disabled=false;$('poseStatus').textContent='پاسخ موقعیت نرسید؛ اتصال SDK را بررسی کنید.';}},7000);
  });
  window.onTimoAgentPosition = result=>{
    if(result.request_id!==poseRequest)return;poseRequest=null;$('capturePosition').disabled=false;
    if(!result.ok){$('poseStatus').textContent=result.message;return;}
    for(const name of ['x','y','z','rotation'])field(forms.rooms,name).value=result.pose[name];
    field(forms.rooms,'map_name').value=state?.motion_config?.map_name||'';field(forms.rooms,'enabled').checked=false;
    $('poseStatus').textContent='موقعیت دریافت شد. نام نقشه و محل ربات را بررسی کنید؛ هنوز ذخیره نشده است.';
  };
  const roomName=sessionStorage.getItem('timo-room-draft');if(roomName){field(forms.rooms,'name').value=roomName;sessionStorage.removeItem('timo-room-draft');tab('rooms');}
  if(key)load().then(()=>report('دسترسی مدیر فعال است.')).catch(()=>{key='';sessionStorage.removeItem(keyName);report('کلید قبلی معتبر نیست؛ دوباره وارد شوید.',true);});
})();
