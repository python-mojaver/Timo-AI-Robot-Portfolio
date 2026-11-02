/* Exercise continuous PCM capture, silence boundaries and playback suppression. */
const vm = require('vm'), fs = require('fs'), path = require('path'), assert = require('assert/strict');
let speechCount = 0;
const delivered = [];
const context = vm.createContext({window:{}, Float32Array, ArrayBuffer, DataView, Blob, Date, console});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/microphone.js'), 'utf8'), context);
const mic = new context.window.PrimeMicrophone(() => speechCount++, blob => delivered.push(blob), error => {throw error;});
mic.running = true; mic.sampleRate = 16000;
const chunk = amplitude => new Float32Array(640).fill(amplitude); // 40 ms
const feed = (amplitude, count) => {for(let i=0;i<count;i++)mic.ingest(chunk(amplitude));};
(async () => {
  feed(.06,2); assert.equal(speechCount,0,'short transient noise does not start a turn');
  feed(.06,1); assert.equal(speechCount,1,'sustained speech starts a turn');
  feed(.06,4); assert.equal(speechCount,1,'one notification per utterance');
  feed(0,24); assert.equal(delivered.length,1,'silence ends the speech segment');
  const bytes = new DataView(await delivered[0].arrayBuffer());
  assert.equal(String.fromCharCode(...new Uint8Array(bytes.buffer,0,4)),'RIFF');
  assert.equal(bytes.getUint16(22,true),1,'WAV is mono');
  assert.equal(bytes.getUint32(24,true),16000,'WAV preserves capture sample rate');
  assert.equal(bytes.getUint32(40,true),bytes.byteLength-44,'data length matches encoded samples');
  feed(0,100); assert.equal(delivered.length,1,'idle silence is not uploaded');
  mic.setPlaybackActive(true); feed(.1,50);
  assert.equal(speechCount,1,'robot playback cannot create a new voice turn');
  mic.setPlaybackActive(false); feed(.1,5);
  assert.equal(speechCount,1,'echo tail is ignored');
  mic.listenAfter=0; feed(.06,3);
  assert.equal(speechCount,2,'listening resumes after playback');
  mic.stop(); assert.equal(mic.running,false); assert.equal(mic.parts.length,0);
  console.log('PASS: PCM onset, silence, valid mono WAV, idle discard, playback/echo suppression, restart');
})().catch(error=>{console.error(error);process.exitCode=1;});
