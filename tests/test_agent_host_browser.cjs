const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..');
const flush = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  const html = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
  const dom = new JSDOM(html, {url:'http://localhost:8000', runScripts:'outside-only', pretendToBeVisual:true});
  const w = dom.window;
  const intervals = [], calls = [], players = [];
  let event = {id:'event-1', response:'سلام آقای مجاور', display_name:'آقای مجاور'};
  let nextChat;
  w.setInterval = (callback, ms) => {intervals.push({callback,ms}); return intervals.length;};
  w.AndroidRobot = {startNativeWhisperMic(){return true;},stopNativeWhisperMic(){},isNativeWhisperMicRunning(){return false;}};
  w.Audio = class extends w.EventTarget {
    constructor(){super();players.push(this);}
    play(){this.paused=false;this.dispatchEvent(new w.Event('playing'));return Promise.resolve();}
    pause(){this.paused=true;this.dispatchEvent(new w.Event('pause'));}
    removeAttribute(){} load(){}
  };
  w.fetch = async (url, options={}) => {
    calls.push({url,options});
    const result = body => ({ok:true,json:async()=>body});
    if (url.endsWith('/pair')) {
      assert.equal(options.headers['X-Agent-Key'],'manager-key');
      return result({token:'paired-token'});
    }
    if (url.endsWith('/next')) {
      assert.equal(options.headers['X-Host-Token'],'paired-token');
      return result({event});
    }
    if (url.endsWith('/claim')) return result({status:'claimed'});
    if (url.endsWith('/ack') || url.endsWith('/unpair')) return result({status:'ok'});
    if (url === '/api/speak/prepare') return result({audio_url:'/generated_audio/test.mp3'});
    if (url === '/api/chat') return new Promise(resolve => {nextChat = body=>resolve(result(body));});
    throw new Error('Unexpected request: '+url);
  };
  w.sessionStorage.setItem('timo-agent-manager-key','manager-key');
  w.eval(fs.readFileSync(path.join(root,'static/prime.js'),'utf8'));
  assert.equal(w.localStorage.getItem('timo-conversation-id'),w.TimoDialogue.sessionId,'browser retains its conversation ID across reloads');
  w.eval(fs.readFileSync(path.join(root,'static/agent-host.js'),'utf8'));
  assert.equal(w.TimoDialogue.canGreet(),true);
  w.document.getElementById('agentHostButton').click();
  await flush();
  const poll = intervals.find(x=>x.ms===1000).callback;
  const speaking = poll();
  await flush();await flush();
  assert.equal(players.length,1);
  assert.equal(w.TimoDialogue.canGreet(),false);
  assert.equal(calls.filter(x=>x.url==='/api/chat').length,0,'recognition bypasses conversational intent routing');
  await poll();
  assert.equal(players.length,1,'concurrent poll cannot duplicate greeting');
  players[0].dispatchEvent(new w.Event('ended'));
  await speaking;
  assert.equal(JSON.parse(calls.find(x=>x.url.endsWith('/ack')).options.body).delivered,true);
  await poll();
  assert.equal(players.length,1,'same recognition event is consumed once');

  event = {id:'event-2',response:'سلام مهمان',display_name:'مهمان'};
  const message = w.eval('sendMessage("چه محصولاتی دارید؟")');
  await flush();
  const claims = calls.filter(x=>x.url.endsWith('/claim')).length;
  await poll();
  assert.equal(calls.filter(x=>x.url.endsWith('/claim')).length,claims,'pending user answer has priority over greeting');
  w.eval('interrupt()');
  nextChat({response:'پاسخ قدیمی'});
  await message;
  assert.equal(players.length,1,'interrupted chat cannot resume stale audio');

  const greeting = w.TimoDialogue.greet('سلام دوباره');
  await flush();
  w.eval('interrupt()');
  assert.equal(await greeting,false,'interrupted greeting is not reported as delivered');
  assert.equal(players[1].paused,true);
  w.document.getElementById('agentHostButton').click();
  await flush();
  assert.ok(calls.some(x=>x.url.endsWith('/unpair')));
  const before=calls.length;
  await poll();
  assert.equal(calls.length,before,'disabled host does not fetch or speak');
  dom.window.close();
  console.log('PASS: paired recognition, shared TTS, no duplicate greeting, user-answer priority, stale reply, interruption, disable');
})().catch(error=>{console.error(error);process.exitCode=1;});
