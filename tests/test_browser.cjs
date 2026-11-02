const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const elements = new Map();
const make = () => ({style: {}, value: '', children: [], appendChild(x) {this.children.push(x);},
    after() {}, addEventListener() {}});
const pending = [];
const players = [];
const navigation = [];
const context = vm.createContext({
    document: {dispatchEvent() {}, getElementById(id) {if (!elements.has(id)) elements.set(id, make()); return elements.get(id);}, createElement: make},
    window: {addEventListener() {}, TimoAgent:{cancelProposal(){},handle(result){if(result.action?.type==='navigate')navigation.push(result.action);}}}, navigator: {}, crypto: {randomUUID: () => 'test'}, console,
    AbortController, URL, performance, CustomEvent, location: {origin: 'http://localhost:8000'}, setTimeout, clearTimeout, setInterval, clearInterval,
    fetch(url, options) { return new Promise(resolve => pending.push({url, options, resolve})); },
    Audio: class extends EventTarget {
        constructor() {super(); players.push(this);}
        play() {this.paused=false;this.dispatchEvent(new Event('playing'));return Promise.resolve();}
        pause() {this.paused=true;this.dispatchEvent(new Event('pause'));}
        removeAttribute() {} load() {}
    }
});
const root = path.resolve(__dirname, '..');
vm.runInContext(fs.readFileSync(path.join(root, 'static/prime.js'), 'utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
const respond = (request, data) => request.resolve({ok: true, json: async () => data});
(async () => {
    const first = vm.runInContext('sendMessage("first")', context);
    vm.runInContext('interrupt()', context);
    respond(pending.shift(), {response: 'stale answer',action:{type:'navigate',name:'old room'}});
    await first;
    assert.equal(elements.get('messages').children.length, 1, 'stale response must not enter the UI');
    assert.equal(players.length, 0);
    assert.equal(navigation.length,0,'interrupted request must not dispatch stale navigation');
    const second = vm.runInContext('sendMessage("second")', context);
    respond(pending.shift(), {response: 'fresh answer',action:{type:'navigate',name:'current room'}});
    await flush();
    respond(pending.shift(), {audio_url: '/generated_audio/test.mp3'});
    await flush();
    assert.equal(players.length, 1);
    assert.equal(navigation.length,1,'latest explicit command reaches direct dispatcher exactly once');
    vm.runInContext('interrupt()', context);
    await second;
    assert.equal(players[0].paused, true, 'interruption must stop playback');
    const third = vm.runInContext('sendMessage("third")', context);
    respond(pending.shift(), {response: 'text remains'});
    await flush();
    vm.runInContext('stopConversation()', context);
    respond(pending.shift(), {audio_url: '/generated_audio/late.mp3'});
    await third;
    assert.equal(players.length, 1, 'late TTS must never resume playback');
    const workflow = JSON.parse(fs.readFileSync(path.join(root, 'HTN_Prime_Workflow.json')));
    const prompt = workflow.nodes.find(n => n.name === 'HTN Prime Conversation').parameters.text;
    const evaluated = vm.runInNewContext(prompt.slice(3, -2), {$json: {body: {system_prompt: 'system', history: [], message: 'hello'}}});
    assert.ok(evaluated.includes('hello') && evaluated.includes('system'));
    console.log('PASS: stale response, speech interruption, late TTS, workflow expression');
})().catch(error => {console.error(error); process.exitCode = 1;});
