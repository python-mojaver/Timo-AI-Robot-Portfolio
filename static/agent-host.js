/* Pair one operator-approved page; greetings share the existing voice lifecycle. */
(() => {
  const button = document.getElementById('agentHostButton');
  const label = document.getElementById('agentHostStatus');
  if (!button || !window.TimoDialogue) return;
  let token = null, enabled = false, polling = false, generation = 0;
  const handled = new Set();
  if (window.AndroidRobot) button.textContent = 'اتصال صدای ربات';
  async function api(path, body, headers = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch('/api/agent/host/' + path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {'Content-Type': 'application/json', 'X-Host-Token': token || '', ...headers},
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'ارتباط حالت میزبان برقرار نشد.');
      return result;
    } finally {clearTimeout(timeout);}
  }
  function disabled(text) {
    generation++; enabled = false; token = null;
    button.textContent = window.AndroidRobot ? 'اتصال صدای ربات' : 'فعال‌کردن سلام شخصی'; label.textContent = text;
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (enabled) {
        const oldToken = token;
        disabled('سلام شخصی غیرفعال است.');
        await api('unpair', {}, {'X-Host-Token': oldToken});
        return;
      }
      if (!window.AndroidRobot) {label.textContent = 'این گزینه را روی صفحهٔ خود ربات فعال کنید.'; return;}
      const key = sessionStorage.getItem('timo-agent-manager-key') || window.prompt('کلید مدیر ایجنت را برای فعال‌کردن سلام شخصی وارد کنید:');
      if (!key) return;
      const result = await api('pair', {session_id: window.TimoDialogue.sessionId}, {'X-Agent-Key': key.trim()});
      window.stopConversation?.();
      token = result.token; enabled = true; generation++; handled.clear();
      button.textContent = 'قطع اتصال صدا';
      label.textContent = 'آمادهٔ دریافت متن از لپ‌تاپ و سلام شخصی هستم.';
    } catch (error) {disabled(error.message);}
    finally {button.disabled = false;}
  });
  async function poll() {
    if (!enabled || polling || document.hidden) return;
    polling = true;
    const version = generation;
    try {
      const result = await api('next');
      if (!enabled || version !== generation) return;
      const event = result.event;
      if (!event || handled.has(event.id) || !window.TimoDialogue.canGreet()) return;
      const claim = await api('claim', {event_id: event.id});
      if (!enabled || version !== generation || claim.status !== 'claimed') return;
      handled.add(event.id);
      if (handled.size > 100) handled.delete(handled.values().next().value);
      const delivered = await window.TimoDialogue.greet(event.response);
      if (enabled && version === generation) {
        await api('ack', {event_id: event.id, delivered});
        label.textContent = delivered ? (event.type === 'operator_speech' ? 'متن لپ‌تاپ از ربات پخش شد.' : `سلام به ${event.display_name} پخش شد.`) : 'صدا کامل پخش نشد؛ اتصال صدا را بررسی کنید.';
      }
    } catch (error) {
      if (version === generation) disabled(error.message);
    } finally {polling = false;}
  }
  // Poll during playback as heartbeat too; never deliver a second greeting.
  setInterval(() => { if (enabled && polling && !document.hidden) api('next').catch(() => {}); }, 3000);
  setInterval(poll, 1000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) return;
    const previous = token;
    disabled('برای ادامه، سلام شخصی را دوباره فعال کنید.');
    if (previous) api('unpair', {}, {'X-Host-Token': previous}).catch(() => {});
  });
  // Operator panel: the laptop submits literal text; only the paired robot plays it.
  if (!window.AndroidRobot) {
    const toggle = document.createElement('button');
    toggle.id = 'timoRemoteSpeechToggle'; toggle.type = 'button';
    toggle.textContent = 'گفتن متن از ربات';
    button.insertAdjacentElement('afterend', toggle);
    const panel = document.createElement('section');
    panel.id = 'timoRemoteSpeechPanel'; panel.hidden = true; panel.dir = 'rtl';
    panel.style.cssText = 'padding:16px;margin:12px 0;border:1px solid #6ca5b2;border-radius:12px;background:#102b37;color:#fff';
    panel.innerHTML = `<h3 style="margin:0 0 10px">گفتن متن از بلندگوی ربات</h3>
      <p>روی ربات «اتصال صدای ربات» را فعال کنید. متن را اینجا بنویسید و بفرستید.</p>
      <form id="timoRemoteSpeechForm">
        <label>کلید مدیرِ آموزش ایجنت <input id="timoRemoteSpeechKey" type="password" autocomplete="off" required style="display:block;width:100%;box-sizing:border-box;margin:6px 0 12px"></label>
        <label>متنی که ربات دقیقاً می‌گوید <textarea id="timoRemoteSpeechText" rows="3" maxlength="2000" required style="display:block;width:100%;box-sizing:border-box;margin:6px 0 12px">خیلی عالی داری توضیح میدی</textarea></label>
        <button id="timoRemoteSpeechSend" type="submit">پخش از ربات</button>
      </form><p id="timoRemoteSpeechStatus" role="status">متن مستقیماً خوانده می‌شود.</p>`;
    const chatHeader = button.closest('.header');
    if (chatHeader) chatHeader.insertAdjacentElement('afterend', panel);
    else button.parentElement.insertAdjacentElement('afterend', panel);
    const form = panel.querySelector('form');
    const key = panel.querySelector('#timoRemoteSpeechKey');
    const text = panel.querySelector('#timoRemoteSpeechText');
    const send = panel.querySelector('#timoRemoteSpeechSend');
    const state = panel.querySelector('#timoRemoteSpeechStatus');
    key.value = sessionStorage.getItem('timo-agent-manager-key') || '';
    let lastRequest = null, checking = false;
    const stateText = {
      queued: 'متن ارسال شد؛ در انتظار پخش از ربات…',
      playing: 'ربات در حال آماده‌سازی یا پخش صداست…',
      delivered: 'پخش متن در ربات تمام شد.',
      failed: 'پخش کامل نشد؛ وضعیت صدای ربات را بررسی کنید.',
      expired: 'مهلت دریافت یا پخش متن تمام شد؛ اتصال ربات را بررسی و دوباره ارسال کنید.',
      cancelled: 'اتصال ربات تغییر کرد یا قطع شد؛ متن پخش نشد.'
    };
    async function operatorApi(path, body) {
      const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 7000);
      try {
        const response = await fetch('/api/agent/host/' + path, {
          method: body === undefined ? 'GET' : 'POST',
          headers: {'Content-Type':'application/json','X-Agent-Key':key.value.trim()},
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: abort.signal, cache: 'no-store'
        });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'ارسال متن ناموفق بود.');
        sessionStorage.setItem('timo-agent-manager-key', key.value.trim());
        return result;
      } finally { clearTimeout(timeout); }
    }
    function showReceipt(value) {
      state.textContent = stateText[value] || 'وضعیت پخش مشخص نیست.';
      if (lastRequest) lastRequest.done = ['delivered','failed','expired','cancelled'].includes(value);
    }
    async function check() {
      if (panel.hidden || checking || !key.value.trim()) return;
      checking = true;
      try {
        const result = await operatorApi('speech-status');
        const receipt = lastRequest && result.receipts.find(x => x.request_id === lastRequest.request_id);
        if (receipt) showReceipt(receipt.state);
        else state.textContent = result.robot_connected ? 'ربات متصل است؛ متن را بفرستید.' : 'روی ربات، «اتصال صدای ربات» را فعال کنید.';
      } catch (error) { state.textContent = error.message || 'ارتباط با سرور برقرار نشد.'; }
      finally { checking = false; }
    }
    toggle.addEventListener('click', () => { panel.hidden = !panel.hidden; if (!panel.hidden) check(); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (send.disabled) return;
      const value = text.value.trim();
      if (!value || !key.value.trim()) { state.textContent = 'متن و کلید مدیر را وارد کنید.'; return; }
      if (!lastRequest || lastRequest.text !== value || lastRequest.done) {
        lastRequest = {request_id: window.crypto?.randomUUID?.() || ('speech_' + Date.now() + '_' + Math.random().toString(36).slice(2)), text: value, done: false};
      }
      send.disabled = true;
      try {
        const result = await operatorApi('say', {text:value,request_id:lastRequest.request_id});
        showReceipt(result.status);
      } catch (error) { state.textContent = error.message || 'ارسال انجام نشد؛ دوباره امتحان کنید.'; }
      finally { send.disabled = false; }
    });
    setInterval(check, 2000);
  }
})();
