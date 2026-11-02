/* Local mic comparison. Each transcription uses exactly the audio offered for playback. */
const el = id => document.getElementById(id);
let currentMic = null, timer = null, generation = 0;
const urls = [];
function state(text, busy = false) {
    el('status').textContent = text;
    el('record').disabled = busy;
    el('stop').disabled = !busy;
    el('device').disabled = el('profile').disabled = busy;
}
function finish() {
    clearTimeout(timer);
    if (currentMic) {
        currentMic.finishRecording();
        currentMic.stop();
        currentMic = null;
    }
    generation++;
    state('ضبط تمام شد؛ فایل را پخش و با حالت دیگر مقایسه کنید.');
}
function offer(blob, title, filename, settings = null) {
    const article = document.createElement('article');
    const h = document.createElement('h2'); h.textContent = title; h.style.fontSize = '18px';
    const url = URL.createObjectURL(blob); urls.push(url);
    const player = document.createElement('audio'); player.controls = true; player.src = url;
    const link = document.createElement('a'); link.href = url; link.download = filename; link.textContent = 'دانلود همین فایل صدا';
    const button = document.createElement('button'); button.textContent = 'تبدیل همین فایل به متن';
    const text = document.createElement('p'); text.setAttribute('aria-live','polite');
    button.onclick = async () => {
        button.disabled = true; text.textContent = 'در حال تشخیص متن…';
        const started = performance.now();
        try {
            const response = await fetch('/api/transcribe', {method:'POST', body:blob, headers:{'Content-Type':blob.type || 'application/octet-stream'}});
            if (!response.ok) throw new Error('HTTP '+response.status);
            const result = await response.json();
            text.textContent = (result.text || result.message || 'متنی تشخیص داده نشد.') + ' — زمان: ' + ((performance.now()-started)/1000).toFixed(2) + ' ثانیه';
        } catch (error) {text.textContent = 'تبدیل صدا ناموفق بود. اتصال به سرور را بررسی کنید.';}
        finally {button.disabled = false;}
    };
    article.append(h, player, link, document.createElement('br'), button, text);
    if (settings) {
        const details = document.createElement('details'), summary = document.createElement('summary'), pre = document.createElement('pre');
        summary.textContent = 'مشخصات واقعی ضبط'; pre.textContent = JSON.stringify(settings, null, 2);
        details.append(summary, pre); article.append(details);
    }
    el('recordings').prepend(article);
}
el('record').onclick = async () => {
    const token = ++generation;
    state('اجازه دسترسی به میکروفن را تأیید کنید…', true);
    const processed = el('profile').value === 'processed';
    const mic = new PrimeMicrophone(() => {}, blob => {
        if (token !== generation) return;
        offer(blob, processed ? 'ضبط با پردازش مرورگر' : 'ضبط صدای طبیعی', processed ? 'mic-processed.wav' : 'mic-natural.wav',
              {wavSampleRate:mic.sampleRate, ...mic.trackSettings});
    }, () => {finish(); state('ضبط صدا متوقف شد؛ دوباره تلاش کنید.');},
    {manual:true, processed, deviceId:el('device').value});
    currentMic = mic;
    try {
        await mic.start();
        if (token !== generation) {mic.stop(); return;}
        state('در حال ضبط؛ جمله را بگویید…', true);
        timer = setTimeout(finish, 6000);
        const devices = await navigator.mediaDevices.enumerateDevices();
        if (token !== generation) return;
        const selected = mic.trackSettings.deviceId || el('device').value;
        const defaults = document.createElement('option'); defaults.value = ''; defaults.textContent = 'میکروفن پیش‌فرض مرورگر';
        el('device').replaceChildren(defaults);
        for (const device of devices.filter(d => d.kind === 'audioinput')) {
            const option = document.createElement('option'); option.value = device.deviceId; option.textContent = device.label || 'میکروفن';
            el('device').append(option);
        }
        el('device').value = selected;
    } catch (error) {
        if (token !== generation) return;
        finish(); state('میکروفن در دسترس نیست؛ مجوز و دستگاه انتخاب‌شده را بررسی کنید.');
    }
};
el('stop').onclick = finish;
el('existing').onchange = event => {
    const file = event.target.files[0];
    if (file) offer(file, 'فایل انتخاب‌شده: '+file.name, file.name);
};
window.addEventListener('beforeunload', () => {currentMic?.stop(); clearTimeout(timer); urls.forEach(url => URL.revokeObjectURL(url));});
