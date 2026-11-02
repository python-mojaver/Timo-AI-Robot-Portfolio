/* DOM integration tests; these do not assert pixel layout or native robot behavior. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname,'..');
const tick = () => new Promise(resolve => setImmediate(resolve));

async function managerTests(){
  const dom = new JSDOM(fs.readFileSync(path.join(root,'templates/agent.html'),'utf8'),{url:'http://localhost:8000/agent',runScripts:'outside-only'});
  const w = dom.window, d=w.document;
  const state={memories:[{id:1,title:'<img src=x onerror=alert(1)>',body:'اطلاعات',kind:'fact'}],rooms:[],skills:[],motion_config:{map_name:'office',revision:'r1',configured:true}};
  const calls=[];let poseRequest;
  w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.confirm=()=>true;
  w.AndroidRobot={captureAgentPosition(id){poseRequest=id;}};
  w.fetch=async(url,options={})=>{
    calls.push({url,options});
    if(options.headers['X-Agent-Key']!=='manager-key')return{ok:false,json:async()=>({detail:'کلید اشتباه'})};
    if(url.endsWith('/state'))return{ok:true,json:async()=>state};
    if(options.method==='POST'&&url.endsWith('/memories'))state.memories.unshift({id:2,...JSON.parse(options.body).data});
    return{ok:true,json:async()=>({status:'ok',id:2})};
  };
  w.eval(fs.readFileSync(path.join(root,'static/agent-manager.js'),'utf8'));
  const submit=id=>d.getElementById(id).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  d.getElementById('managerKey').value='wrong';submit('managerLogin');await tick();
  assert.equal(d.getElementById('managerContent').hidden,true);
  d.getElementById('managerKey').value='manager-key';submit('managerLogin');await tick();
  assert.equal(d.getElementById('managerContent').hidden,false);
  assert.equal(w.sessionStorage.getItem('timo-agent-manager-key'),'manager-key');
  assert.equal(d.getElementById('memoryList').querySelectorAll('img').length,0,'stored text cannot create HTML');
  const memory=d.getElementById('memoryForm');
  memory.elements.namedItem('title').value='ساعت کاری';memory.elements.namedItem('body').value='۹ تا ۵';submit('memoryForm');await tick();
  assert.equal(state.memories[0].title,'ساعت کاری');
  assert.ok(d.getElementById('memoryList').textContent.includes('۹ تا ۵'));
  d.getElementById('capturePosition').click();
  w.onTimoAgentPosition({request_id:poseRequest,ok:true,pose:{x:1,y:2,z:0,rotation:1},map_name:'office'});
  const room=d.getElementById('roomForm');
  assert.equal(room.elements.namedItem('x').value,'1');
  assert.equal(room.elements.namedItem('map_name').value,'office');
  assert.equal(room.elements.namedItem('enabled').checked,false,'captured pose still needs review');
  d.getElementById('managerLogout').click();
  assert.equal(w.sessionStorage.getItem('timo-agent-manager-key'),null);
  assert.equal(d.getElementById('memoryList').children.length,0);
  dom.window.close();
}

async function chatTests(){
  const dom=new JSDOM('<div id="messages"></div><span id="agentMotionStatus"></span><button id="agentStopBtn"></button><button id="agentRobotSettings"></button>',{url:'http://localhost:8000',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,d=w.document;
  let navigation=0,stops=0,dismiss=0;
  w.fetch=async()=>({ok:true,json:async()=>({configured:true,map_name:'A',revision:'r1'})});
  w.AndroidRobot={agentMotionMode(){return 'direct-v2';},requestAgentNavigation(command){
    const payload=JSON.parse(command);
    if(payload.type==='sync_map'){w.onTimoAgentMotion({event:'map_synced',request_id:payload.request_id});return;}
    navigation++;assert.equal(payload.name,'اتاق فروش');assert.equal(payload.map_revision,'r1');
  },stopAgentNavigation(){stops++;},dismissAgentNavigation(){dismiss++;}};
  w.eval(fs.readFileSync(path.join(root,'static/agent-chat.js'),'utf8'));
  const proposal={action:{type:'navigate',name:'اتاق فروش',map_name:'A',pose:{x:1,y:2,z:0,rotation:0}}};
  await w.TimoAgent.handle(proposal,'session');
  assert.equal(navigation,1,'explicit command dispatches without a confirmation click');
  assert.equal(d.querySelectorAll('.agent-notice button').length,1,'only the stop button remains');
  assert.equal(d.querySelector('.agent-notice button').textContent,'توقف');
  await w.TimoAgent.handle(proposal,'session');
  assert.equal(navigation,1,'same response cannot dispatch twice');
  w.onTimoAgentMotion({message:'نام نقشه یکی نیست'});
  assert.ok(d.querySelector('.agent-notice').textContent.includes('نام نقشه یکی نیست'),'native rejection appears next to destination');
  d.querySelector('.agent-notice button').click();assert.equal(stops,1);
  await w.TimoAgent.handle({action:{...proposal.action}},'session');
  assert.equal(navigation,2,'a fresh user command can dispatch');
  const mode=w.AndroidRobot.agentMotionMode;delete w.AndroidRobot.agentMotionMode;
  await w.TimoAgent.handle({action:{...proposal.action}},'session');
  assert.equal(navigation,2,'old Android app cannot accidentally use the new direct flow');
  assert.ok(d.querySelector('.agent-notice').textContent.includes('نصب کنید'));
  w.AndroidRobot.agentMotionMode=mode;
  Object.defineProperty(d,'hidden',{configurable:true,value:true});
  await w.TimoAgent.handle({action:{...proposal.action}},'session');
  assert.equal(navigation,2,'background page cannot start navigation');
  Object.defineProperty(d,'hidden',{configurable:true,value:false});
  await w.TimoAgent.handle({response:'پاسخ معمولی'} ,'session');
  assert.equal(navigation,2,'ordinary/model text has no robot effect');
  w.TimoAgent.cancelProposal();assert.equal(d.querySelector('.agent-notice'),null);assert.equal(dismiss,1);
  await w.TimoAgent.handle({action:{type:'stop'}},'session');assert.equal(stops,2);
  await w.TimoAgent.handle({proposal:{id:'draft',kind:'memory',payload:{title:'<script>alert(1)</script>',body:'متن'}}},'session');
  assert.equal(d.querySelectorAll('script').length,0);
  let body;
  w.fetch=async(url,options)=>{body=JSON.parse(options.body);assert.equal(options.headers['X-Agent-Key'],'key');return{ok:true,json:async()=>({status:'ok'})};};
  d.querySelector('.agent-key-input').value='key';d.querySelector('.agent-notice button').click();await tick();
  assert.deepEqual(body,{proposal_id:'draft',session_id:'session'});
  assert.ok(d.querySelector('.agent-notice').textContent.includes('ثبت شد'));
  dom.window.close();
}

(async()=>{await managerTests();await chatTests();console.log('PASS: manager login/save/logout, text escaping, pose review, direct navigation/replay/compatibility/background checks, native feedback, memory confirmation, stop');})().catch(e=>{console.error(e);process.exitCode=1;});
