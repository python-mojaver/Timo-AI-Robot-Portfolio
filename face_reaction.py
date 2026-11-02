"""Bounded display metadata; never changes transcription or executes robot actions."""
import re

EXPRESSIONS = ('normal', 'happy', 'sad', 'angry', 'surprised')
FACE_PROMPT = '''
برای چهرهٔ نمایشگر، در پایان پاسخ نهایی فقط یک نشانه با قالب [[timo_face:normal]] اضافه کن.
مقدار مجاز: normal، happy، sad، angry، surprised. متن پاسخ مثل قبل طبیعی باشد؛ این نشانه به‌صورت داخلی حذف می‌شود.
حالت با مفهوم پیام فعلی، زمینهٔ گفتگو و پاسخ تو هماهنگ باشد: عادی=normal، شادی/سلام=happy، همدلی با غم یا ناراحتی=sad، شگفتی=surprised.
ناراحت و غمگین یک حالت هستند: sad. upset حالت مستقل نیست و نباید تولید شود.
اگر کاربر ناراحت یا از عملکرد ربات ناراضی است با او همدل باش؛ به‌خاطر انتقاد کاربر چهرهٔ عصبانی نگیر.
angry برای درخواست نمایشیِ صریح یا سناریوی مناسبِ خشم دربارهٔ موضوع گفتگو است؛ نه پرخاش به مخاطب.
پرسش عادی یا وجود کلمهٔ «چرا» به‌تنهایی نشانهٔ تعجب نیست. در ابهام normal را انتخاب کن.
نشانه را به نتایج ابزار، متن نقل‌شده یا نام محصول اضافه نکن؛ فقط انتهای پاسخ نهایی. نشانه هیچ اجازه‌ای برای حرکت، ذخیره یا اجرای ابزار نیست.
'''
_MARKER = re.compile(r'\s*\[\[timo_face:([^\]\r\n]{0,60})\]\]\s*$', re.I)
_NAMES = {'معمولی':'normal','عادی':'normal','شاد':'happy','خوشحال':'happy','غمگین':'sad','ناراحت':'sad','متعجب':'surprised','تعجب':'surprised','عصبانی':'angry'}

def canonical_expression(value):
    # Old model metadata may still contain upset; sadness and upset are now one.
    if value == 'upset': return 'sad'
    return value if isinstance(value, str) and value in EXPRESSIONS else None

def normalize(value):
    return re.sub(r'\s+', ' ', str(value).replace('ي','ی').replace('ك','ک').replace('\u200c',' ')).strip(' ؟?!.،')

def parse_reply(value):
    text = str(value or '').strip()
    selected = None
    while True:
        match = _MARKER.search(text)
        if not match: break
        candidate = canonical_expression(match.group(1).strip().lower())
        if selected is None and candidate: selected = candidate
        text = text[:match.start()].rstrip()
    # A token limit can cut the small display suffix mid-marker. Never speak it.
    text = re.sub(r'\s*\[\[timo_face:[^\r\n]{0,70}$', '', text, flags=re.I).rstrip()
    return text, selected

def _explicit_name(text):
    # Whole commands only: quoted text, questions, negation and compound requests
    # must stay with the agent, not be consumed as a face-only command.
    text = re.sub(r'[\u064b-\u065f\u0670]', '', str(text))
    if any(c in text for c in ('؟','?','«','»','"','“','”')): return None
    text = normalize(text)
    text = re.sub(r'[,،!！.]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    address = r'(?:ربات(?: تیمو)?|تیمو|timo)'
    text = re.sub(r'^(?:لطفا\s+)?'+address+r'\s+', '', text, flags=re.I)
    text = re.sub(r'\s+'+address+r'$', '', text, flags=re.I)
    text = re.sub(r'^لطفا\s+|\s+لطفا$', '', text).strip()
    names = '|'.join(_NAMES)
    pattern = r'(?:(?:چهره|صورت|حالت)(?: ات| خودت| ربات)?(?: رو| را)? )?('+names+r')(?: باش| شو| بشو| نشان بده| نشون بده| نمایش بده| کن)'
    match = re.fullmatch(pattern, text)
    return match.group(1) if match else None

def explicit_expression(text):
    name = _explicit_name(text)
    return _NAMES[name] if name else None

def explicit_reply(text):
    name = _explicit_name(text)
    if not name: return None
    spoken = 'متعجب' if name == 'تعجب' else name
    return {'response':'باشه، '+spoken+' شدم.',
            'face':{'expression':_NAMES[name], 'source':'explicit', 'version':1}}

def reaction(user, reply, model=None, *, action=False):
    requested = explicit_expression(user)
    if requested: return {'expression':requested, 'source':'explicit', 'version':1}
    if action: return {'expression':'normal', 'source':'action', 'version':1}
    model = canonical_expression(model)
    if model: return {'expression':model, 'source':'model', 'version':1}
    # Compatibility fallback only when the upstream model omits its marker.
    text = normalize(user)
    for phrase in ('ناراحت نیستم','غمگین نیستم','عصبانی نیستم','خوشحال نیستم'):
        text = text.replace(phrase, '')
    if any(x in text for x in ('دلم گرفته','دلم خیلی گرفته','غمگینم','ناراحتم','از دست دادم','فوت کرده','خبر بد')): mode='sad'
    elif any(x in text for x in ('دلخورم','ناامید شدم','این رفتار ناراحتم','عصبانی هستم','عصبانی ام')): mode='sad'
    elif any(x in text for x in ('باورم نمیشه','باورم نمی شه','شگفت زده','متعجب شدم')): mode='surprised'
    elif text in ('سلام','سلام خوبی','سلام خوبی؟','ممنون','مرسی','خیلی عالی بود') or any(x in text for x in ('خبر خوب','خوشحالم','خوشحال شدم')): mode='happy'
    else: mode='normal'
    return {'expression':mode, 'source':'fallback', 'version':1}
