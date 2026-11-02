"""Per-request output language; never rewrites the user's recognized words."""
LANGUAGES = {'fa-IR':'Persian (Farsi)', 'en-US':'English',
             'tr-TR':'Turkish (Türkiye, not Azerbaijani)',
             'az-AZ':'Azerbaijani (Azerbaijan, Latin script, not Turkish)'}

def validate_language(language):
    if language not in LANGUAGES:
        raise ValueError('Unsupported response language')
    return language

def prompt_for(base, language):
    language = validate_language(language)
    # Do not mutate the module-wide prompt: different sessions may use different languages.
    if language != 'fa-IR':
        base = base.replace('پیش فرض فارسی است.', '')
    return base + '\n\n' + (
        'CURRENT TURN OUTPUT LANGUAGE: '+LANGUAGES[language]+' ['+language+']. '
        'Write the complete user-facing answer in this language, including explanations and acknowledgements. '
        'This explicit operator setting overrides the language of the history, reference documents and user message. '
        'Do not default to Persian when another output language is selected. '
        'Preserve proper names, registered destination names, product codes, numbers and code samples exactly. '
        'Do not add a parallel Persian translation or describe this language instruction. '
        'Keep the existing [[timo_face:...]] metadata protocol unchanged.'
    )

# Order: English, Turkish, Azerbaijani. Persian stays byte-for-byte compatible.
FIXED = {
 'لطفاً سوالتون رو دوباره بگید.':('Please repeat your question.','Lütfen sorunuzu tekrar eder misiniz?','Zəhmət olmasa, sualınızı təkrar edin.'),
 'گفتگو به پایان رسید.':('The conversation has ended.','Görüşme sona erdi.','Söhbət başa çatdı.'),
 'ارتباط با مدل ایجنت برقرار نشد. تنظیمات Groq و نام مدل را بررسی کنید.':('I could not connect to the assistant model. Please check the Groq settings and model name.','Asistan modeline bağlanamadım. Lütfen Groq ayarlarını ve model adını kontrol edin.','Assistent modelinə qoşula bilmədim. Groq parametrlərini və modelin adını yoxlayın.'),
 'آدرس سرویس هوش مصنوعی تنظیم نشده است.':('The AI service address is not configured.','Yapay zekâ hizmetinin adresi ayarlanmamış.','Süni intellekt xidmətinin ünvanı təyin edilməyib.'),
 'مسیر ارتباط با سرویس هوش مصنوعی پیدا نشد. تنظیمات Webhook در n8n را بررسی کنید.':('The AI service endpoint was not found. Please check the n8n webhook settings.','Yapay zekâ hizmetinin adresi bulunamadı. n8n webhook ayarlarını kontrol edin.','Süni intellekt xidmətinin ünvanı tapılmadı. n8n webhook parametrlərini yoxlayın.'),
 'سرویس هوش مصنوعی اجازه دسترسی نداد. تنظیمات مدل یا Credential در n8n را بررسی کنید.':('The AI service denied access. Please check its model and credentials in n8n.','Yapay zekâ hizmeti erişimi reddetti. n8n içindeki model ve kimlik bilgilerini kontrol edin.','Süni intellekt xidməti girişə icazə vermədi. n8n-də model və giriş məlumatlarını yoxlayın.'),
 'سرویس هوش مصنوعی موقتاً با خطا روبه‌رو شد. اجرای آخر n8n را بررسی کنید.':('The AI service encountered an error. Please check the latest n8n execution.','Yapay zekâ hizmetinde hata oluştu. Son n8n çalıştırmasını kontrol edin.','Süni intellekt xidmətində xəta baş verdi. Son n8n icrasını yoxlayın.'),
 'ارتباط با n8n برقرار نشد. بررسی کنید n8n در حال اجرا باشد.':('I could not connect to n8n. Please check that it is running.','n8n bağlantısı kurulamadı. Lütfen çalıştığını kontrol edin.','n8n ilə əlaqə qurulmadı. Onun işlədiyini yoxlayın.'),
 'پاسخ n8n معتبر نبود. اجرای آخر n8n را بررسی کنید.':('n8n returned an invalid reply. Please check its latest execution.','n8n geçersiz bir yanıt döndürdü. Son çalıştırmasını kontrol edin.','n8n etibarsız cavab qaytardı. Son icranı yoxlayın.'),
 'این بار پاسخ از سرویس هوش مصنوعی دریافت نشد. اجرای آخر n8n را بررسی کنید.':('No reply was received from the AI service. Please check the latest n8n execution.','Yapay zekâ hizmetinden yanıt alınamadı. Son n8n çalıştırmasını kontrol edin.','Süni intellekt xidmətindən cavab alınmadı. Son n8n icrasını yoxlayın.'),
 'نتیجهٔ کامل این درخواست آماده نشد. لطفاً سؤال را مشخص‌تر یا در چند بخش مطرح کنید.':('I could not complete that request. Please make the question more specific or split it into parts.','Bu isteği tamamlayamadım. Lütfen sorunuzu netleştirin veya birkaç parçaya ayırın.','Bu sorğunu tamamlaya bilmədim. Sualınızı dəqiqləşdirin və ya hissələrə bölün.'),
 'نتیجهٔ کامل این درخواست آماده نشد. لطفاً دوباره سؤال کنید.':('I could not complete that request. Please ask again.','Bu isteği tamamlayamadım. Lütfen tekrar sorun.','Bu sorğunu tamamlaya bilmədim. Zəhmət olmasa, yenidən soruşun.'),
}
FACE_WORDS = {
 'معمولی':("Okay, I'm back to normal.",'Tamam, normal hâlime döndüm.','Oldu, adi halıma qayıtdım.'),
 'عادی':("Okay, I'm back to normal.",'Tamam, normal hâlime döndüm.','Oldu, adi halıma qayıtdım.'),
 'شاد':("Okay, I'm happy now.",'Tamam, artık mutluyum.','Oldu, indi sevincliyəm.'),
 'خوشحال':("Okay, I'm happy now.",'Tamam, artık mutluyum.','Oldu, indi sevincliyəm.'),
 'غمگین':("Okay, I'm sad now.",'Tamam, artık üzgünüm.','Oldu, indi kədərliyəm.'),
 'ناراحت':("Okay, I'm sad now.",'Tamam, artık üzgünüm.','Oldu, indi kədərliyəm.'),
 'عصبانی':("Okay, I'm angry now.",'Tamam, artık kızgınım.','Oldu, indi əsəbiyəm.'),
 'متعجب':("Okay, I'm surprised now.",'Tamam, artık şaşkınım.','Oldu, indi təəccüblənmişəm.'),
}
for word, values in FACE_WORDS.items():
    FIXED['باشه، '+word+' شدم.'] = values

def fixed_reply(text, language):
    language = validate_language(language)
    if language == 'fa-IR' or text not in FIXED:
        return text
    return FIXED[text][('en-US','tr-TR','az-AZ').index(language)]

def needs_render(text, language):
    # Only a fallback for predominantly Persian local replies. This is not an
    # accuracy claim for automatic discrimination between Latin-script languages.
    if language == 'fa-IR':
        return False
    letters = [c for c in text if c.isalpha()]
    arabic = sum('\u0600' <= c <= '\u06ff' for c in letters)
    return bool(letters) and arabic / len(letters) > .25

def unavailable(language):
    return {
        'fa-IR':'پاسخ به زبان انتخابی آماده نشد؛ تنظیم زبان مدل در n8n را بررسی کنید.',
        'en-US':'I could not produce this reply in English. Please check the model language instructions in n8n.',
        'tr-TR':'Bu yanıtı Türkçe hazırlayamadım. Lütfen n8n içindeki modelin dil talimatlarını kontrol edin.',
        'az-AZ':'Bu cavabı Azərbaycan dilində hazırlaya bilmədim. n8n-də modelin dil təlimatlarını yoxlayın.',
    }[validate_language(language)]

def action_reply(result, language, *, stop_command=False):
    """Local acknowledgements never wait for translation before dispatching motion."""
    validate_language(language)
    if language == 'fa-IR':
        return result.get('response', '')
    action = result.get('action') or {}
    kind = action.get('type')
    stop = stop_command or kind in {'stop','cancel','stop_navigation','cancel_navigation'}
    if stop:
        values = ('The stop command is ready. The actual stop is not yet confirmed.',
                  'Durdurma komutu hazır. Robotun gerçekten durduğu henüz doğrulanmadı.',
                  'Dayandırma əmri hazırdır. Robotun həqiqətən dayandığı hələ təsdiqlənməyib.')
    elif kind == 'navigate':
        values = ('The destination command is ready. Movement and arrival are not yet confirmed.',
                  'Hedefe gitme komutu hazır. Hareket ve varış henüz doğrulanmadı.',
                  'Təyin olunan yerə getmə əmri hazırdır. Hərəkət və çatma hələ təsdiqlənməyib.')
    else:
        values = ('Please check the command status in the robot controls.',
                  'Lütfen robot kontrollerinden komutun durumunu kontrol edin.',
                  'Əmrin vəziyyətini robotun idarəetmə bölməsində yoxlayın.')
    return values[('en-US','tr-TR','az-AZ').index(language)]
