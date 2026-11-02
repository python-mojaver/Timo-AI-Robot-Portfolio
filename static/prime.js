/* HTN Prime: one active answer; microphone remains available during playback. */

const $ = id => document.getElementById(id);

const greeting = 'سلام، من ربات HTN Prime هستم. چطور می‌تونم کمکتون کنم؟';



let active = false, recognizing = false, starting = false, epoch = 0;

let controller = null, audio = null, finishAudio = null, restartTimer = null;

let greeted = false;
let hostSpeechUntil = 0;



const sessionId = (() => {
    try {
        const saved = window.localStorage.getItem('timo-conversation-id');
        if (saved && saved.length <= 128) return saved;
    } catch (_) {}
    const value = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    try { window.localStorage.setItem('timo-conversation-id', value); } catch (_) {}
    return value;
})();



const Native = window.AndroidRobot;



const nativeWhisperAvailable = !!(

    Native?.startNativeWhisperMic &&

    Native?.stopNativeWhisperMic &&

    Native?.isNativeWhisperMicRunning

);



function startNativeWhisperMic() {

    if (!nativeWhisperAvailable || !active) return true;



    try {

        const ok = Native.startNativeWhisperMic();



        if (!ok) {

            status('میکروفن ربات شروع نشد.');

            return false;

        }



        return true;



    } catch (err) {

        console.error('startNativeWhisperMic failed', err);

        status('میکروفن ربات شروع نشد.');

        return false;

    }

}



function stopNativeWhisperMic() {

    if (!nativeWhisperAvailable) return;



    try {

        Native.stopNativeWhisperMic();

    } catch (_) {}

}



function nativeSpeechAvailable() {

    try {

        return !!Native?.isSpeechRecognitionAvailable?.();

    } catch (_) {

        return false;

    }

}



let nativeAvailable = nativeSpeechAvailable();



const Recognition =

    window.SpeechRecognition || window.webkitSpeechRecognition;



/*

 \* روی WebView خود ربات اگر AndroidRobot وجود داشته باشد،

 \* عمداً PrimeMicrophone ساخته نمی‌شود تا WebView میکروفن

 \* را دائماً اشغال نکند و Native SpeechRecognizer بتواند

 \* از میکروفن استفاده کند.

 */

const recognition =

    !Native && Recognition

        ? new Recognition()

        : null;



const localMic =

    !nativeWhisperAvailable &&

    window.PrimeMicrophone &&

    window.MediaRecorder &&

    navigator.mediaDevices?.getUserMedia

        ? new PrimeMicrophone(

            beginUserSpeech,

            transcribeSegment,

            () => {

                stopConversation();



                status(

                    'میکروفن در دسترس نیست؛ اجازه دسترسی را بررسی کنید.'

                );

            }

        )

        : null;





async function transcribeSegment(blob) {



    if (!active) return;



    const token = epoch;



    controller = new AbortController();



    status(

        'در حال پردازش گفت‌وگو…'

    );



    try {



        const result = await fetch(

            '/api/transcribe',

            {

                method: 'POST',

                body: blob,
                headers: {'Content-Type': blob.type || 'application/octet-stream'},

                signal: controller.signal

            }

        );





        if (!result.ok) {

            throw new Error(

                'Transcription failed'

            );

        }





        const data =

            await result.json();
        if (data.status === 'error') throw new Error(data.message || 'پردازش صدا ناموفق بود.');





        if (

            !active ||

            token !== epoch

        ) {

            return;

        }





        controller = null;





        if (data.text?.trim()) {



            const recognizedText =

                data.text.trim();





            /*

             \* اول بررسی فرمان‌های مستقیم ربات

             */



            if (

                handleRobotCommand(

                    recognizedText

                )

            ) {



                addMessage(

                    recognizedText,

                    'user'

                );



                status(

                    'درخواست لغو ناوبری دریافت شد؛ توقف واقعی را بررسی کنید.'

                );



            } else {



                await sendMessage(

                    recognizedText, "voice"

                );

            }



        } else {



            status(

                'صدایی تشخیص داده نشد؛ دوباره بگید.'

            );

        }



    } catch (err) {



        if (

            token === epoch &&

            err.name !== 'AbortError'

        ) {



            console.error(

                'Whisper transcription error',

                err

            );



            status(

                err.message || 'پردازش صدا ناموفق بود؛ دوباره تلاش کنید.'

            );

        }

    }

}





function normalizePersianCommand(value) {



    return (value || '')



        .replace(

            /ي/g,

            'ی'

        )



        .replace(

            /ك/g,

            'ک'

        )



        .replace(

            /\u200c/g,

            ' '

        )



        .replace(

            /\s+/g,

            ' '

        )



        .trim();

}





function handleRobotCommand(value) {
    const text = normalizePersianCommand(value).trim();
    if (['توقف', 'بایست', 'وایسا', 'حرکت نکن', 'توقف حرکت', 'توقف ربات'].includes(text)
        && Native?.stopAgentNavigation) {
        window.TimoAgent?.cancelProposal();
        Native.stopAgentNavigation();
        return true;
    }
    return false;
}


function status(text) {



    const statusElement =

        $('status');



    if (statusElement) {

        statusElement.textContent =

            text;

    }

}





function addMessage(

    text,

    kind

) {



    const row =

        document.createElement(

            'div'

        );



    row.className =

        'message-row ' + kind;





    const bubble =

        document.createElement(

            'div'

        );



    bubble.className =

        'message ' + kind;



    bubble.style.whiteSpace =

        'pre-wrap';



    bubble.textContent =

        text;





    row.appendChild(

        bubble

    );





    if (

        kind === 'bot'

    ) {



        const avatar =

            document.createElement(

                'div'

            );



        avatar.className =

            'avatar';



        row.appendChild(

            avatar

        );

    }





    $('messages')

        .appendChild(

            row

        );





    $('messages')

        .scrollTop =

        $('messages')

            .scrollHeight;

}





function interrupt() {
    epoch++;
    window.TimoFace?.cancel();
    controller?.abort(); controller = null;
    const player = audio, finish = finishAudio;
    audio = null; finishAudio = null;
    if (player) {
        try { player.pause(); } catch (_) {}
        try { player.removeAttribute('src'); player.load(); } catch (_) {}
    }
    finish?.('cancelled');
}

function scheduleListening() {



    clearTimeout(

        restartTimer

    );





    /*

     \* Native Whisper Mic خودش

     \* دائم گوش می‌دهد.

     */



    if (

        localMic ||

        nativeWhisperAvailable

    ) {

        return;

    }





    if (active) {



        restartTimer =

            setTimeout(

                startListening,

                300

            );

    }

}





function startListening() {



    if (

        localMic ||

        nativeWhisperAvailable

    ) {

        return;

    }





    if (

        !active ||

        recognizing ||

        starting

    ) {

        return;

    }





    starting =

        true;





    nativeAvailable =

        nativeSpeechAvailable();





    try {



        if (

            nativeAvailable

        ) {



            Native

                .startNativeSpeechRecognition();



        } else if (

            recognition

        ) {



            recognition

                .start();



        } else {



            throw new Error(

                'Speech recognition unavailable'

            );

        }



    } catch (err) {



        starting =

            false;





        console.error(

            err

        );





        status(

            'تشخیص گفتار در دسترس نیست؛ از کادر متن استفاده کنید.'

        );

    }

}





function beginUserSpeech() {
    hostSpeechUntil = performance.now() + 30000;



    if (!active) return;





    interrupt();





    status(

        '🎤 گوش می‌دم؛ ادامه بدید…'

    );

}





async function requestJSON(

    url,

    body,

    signal

) {



    const response =

        await fetch(

            url,

            {

                method: 'POST',

                signal,



                headers: {

                    'Content-Type':

                        'application/json'

                },



                body:

                    JSON.stringify(

                        body

                    )

            }

        );





    if (!response.ok) {



        throw new Error(

            `HTTP ${response.status}`

        );

    }





    return response.json();

}





async function speak(text, token, signal, responseLanguage) {
    if (!String(text || '').trim() || token !== epoch) return;
    if (window.TimoFace && window.TimoFace.state().turn !== token) {
        window.TimoFace.begin(token);
        window.TimoFace.response({expression: 'happy'}, token);
    }
    if (nativeWhisperAvailable) stopNativeWhisperMic();
    status('در حال آماده‌سازی صدای پاسخ…');
    let result;
    try {
        result = await requestJSON('/api/speak/prepare', {
            text, language: responseLanguage || window.TimoVoice?.language() || 'auto'
        }, signal);
    } catch (error) {
        if (signal?.aborted || token !== epoch || error.name === 'AbortError') return;
        // Compatibility for installations whose Python update was not applied.
        if (!String(error.message).includes('HTTP 404')) throw error;
        result = await requestJSON('/api/speak', {text}, signal);
    }
    if (token !== epoch || signal?.aborted) return;
    if (!result.audio_url) throw new Error('Audio generation failed');
    const player = new Audio(); player.preload = 'none';
    player.src = new URL(result.audio_url, location.origin).href;
    const releaseFace = window.TimoFace?.bindAudio(player, token) || (() => {});
    localMic?.setPlaybackActive(true); audio = player;
    await new Promise(resolve => {
        let done = false, played = false, lastTime = 0, lastProgress = performance.now();
        let watchdog = 0;
        const listeners = [];
        const on = (type, fn) => { player.addEventListener(type, fn); listeners.push([type, fn]); };
        const notify = (state, reason) => document.dispatchEvent(new CustomEvent('timo:audio-state', {
            detail: {state, reason, text, token}
        }));
        function finish(reason = 'ended') {
            if (done) return; done = true;
            clearInterval(watchdog);
            signal?.removeEventListener('abort', aborted);
            for (const [name, fn] of listeners) player.removeEventListener(name, fn);
            try { releaseFace(); } catch (e) { console.warn('Face audio cleanup failed', e); }
            try { localMic?.setPlaybackActive(false); } catch (_) {}
            if (audio === player) audio = null;
            if (finishAudio === finish) finishAudio = null;
            if (reason !== 'ended') {
                try { player.pause(); player.removeAttribute('src'); player.load(); } catch (_) {}
            }
            notify(reason === 'ended' ? 'ended' : reason === 'cancelled' || reason === 'paused' ? 'cancelled' : 'failed', reason);
            if (reason === 'failed') console.warn('[TIMO-AUDIO] playback ended with an error');
            resolve();
        }
        const aborted = () => finish('cancelled');
        finishAudio = finish;
        on('playing', () => { played = true; lastProgress = performance.now(); notify('playing'); status('🔊 در حال پاسخ ربات…'); });
        on('ended', () => finish('ended'));
        on('error', () => finish('failed'));
        on('pause', () => { if (played) finish('paused'); });
        on('emptied', () => finish('cancelled'));
        on('timeupdate', () => { if (player.currentTime > lastTime + .005) { lastTime = player.currentTime; lastProgress = performance.now(); } });
        signal?.addEventListener('abort', aborted, {once: true});
        watchdog = setInterval(() => {
            if (signal?.aborted || token !== epoch) return finish('cancelled');
            if (player.ended) return finish('ended');
            if (played && player.paused && !player.seeking) return finish('paused');
            if (played && Number.isFinite(player.duration) && player.duration > 0 && player.currentTime >= player.duration - .015) return finish('ended');
            if (performance.now() - lastProgress > 15000) finish('failed');
        }, 250);
        if (signal?.aborted) return finish('cancelled');
        player.play().catch(() => finish('failed'));
    });
}

async function sendMessage(value, inputSource = "text") {
    hostSpeechUntil = 0;
    window.TimoAgent?.cancelProposal();



    const text =

        (value || '')

            .trim();





    if (!text) {

        return;

    }





    interrupt();





    const token =

        epoch;
    window.TimoFace?.begin(token);





    controller =

        new AbortController();





    const signal =

        controller.signal;





    addMessage(

        text,

        'user'

    );





    status(

        'در حال آماده‌کردن پاسخ…'

    );





    try {



        const result =

            await requestJSON(

                '/api/chat',



                {

                    message:

                        text,



                    session_id:

                        sessionId,

                    input_source: inputSource,
                    response_language: window.TimoVoice?.language() || "fa-IR"

                },



                signal

            );





        if (

            token !== epoch

        ) {

            return;

        }





        addMessage(

            result.response,

            'bot'

        );





        window.TimoFace?.response(result.face, token);
        window.TimoAgent?.handle(result, sessionId);

        await speak(

            result.response,

            token,

            signal,

            result.response_language || window.TimoVoice?.language() || "fa-IR"

        );





        /*

         \* بعد از پایان پاسخ صوتی

         \* دوباره Mic را روشن می‌کنیم.

         */



        if (

            token === epoch &&

            active &&

            nativeWhisperAvailable

        ) {



            startNativeWhisperMic();

        }





        if (

            token === epoch

        ) {



            status(

                active

                    ? '🎤 منتظر صحبت شما هستم…'

                    : 'آماده پیام بعدی'

            );

        }



    } catch (err) {



        if (

            err.name !==

                'AbortError'



            &&



            token === epoch

        ) {



            status(

                'پاسخ یا صدا دریافت نشد؛ ترمینال برنامه را بررسی کنید.'

            );





            console.error(

                err

            );





            if (

                active &&

                nativeWhisperAvailable

            ) {



                startNativeWhisperMic();

            }

        }



    } finally {



        if (

            token === epoch

        ) {
            window.TimoFace?.complete(token);



            controller =

                null;

        }





        scheduleListening();

    }

}





/*

 \* Browser SpeechRecognition fallback

 */



if (recognition) {



    recognition.lang =

        'fa-IR';





    recognition.continuous =

        true;





    recognition.interimResults =

        true;





    recognition.onstart =

        () => {



            starting =

                false;



            recognizing =

                true;

        };





    recognition.onspeechstart =

        beginUserSpeech;





    recognition.onresult =

        event => {



            if (!active) {

                return;

            }





            let finalText =

                '';



            let interim =

                '';





            for (

                let i =

                    event.resultIndex;



                i <

                event.results.length;



                i++

            ) {



                const text =

                    event

                        .results[i][0]

                        .transcript;





                if (

                    event

                        .results[i]

                        .isFinal

                ) {



                    finalText +=

                        text + ' ';



                } else {



                    interim +=

                        text;

                }

            }





            if (

                interim.trim()

            ) {



                if (

                    audio ||

                    controller

                ) {



                    beginUserSpeech();

                }





                $('messageInput')

                    .value =

                    interim;

            }





            if (

                finalText.trim()

            ) {



                $('messageInput')

                    .value =

                    '';





                sendMessage(

                    finalText

                );

            }

        };





    recognition.onend =

        () => {



            recognizing =

                false;



            starting =

                false;





            scheduleListening();

        };





    recognition.onerror =

        event => {



            if (

                [

                    'not-allowed',

                    'service-not-allowed',

                    'audio-capture'

                ]

                    .includes(

                        event.error

                    )

            ) {



                stopConversation();





                status(

                    'دسترسی میکروفن را بررسی کنید؛ گفتگو با متن همچنان فعال است.'

                );



            } else if (

                event.error ===

                'network'

            ) {



                status(

                    'ارتباط سرویس تشخیص گفتار قطع است؛ با متن ادامه دهید.'

                );

            }

        };

}





/*

 \* =============================================

 \* Android AudioRecord -> Whisper callbacks

 \* =============================================

 */



window.onNativeWhisperSpeechStarted =

    () => {



        if (!active) {

            return;

        }





        beginUserSpeech();

    };





window.onNativeWhisperAudio =

    base64Wav => {



        if (

            !active ||

            !base64Wav

        ) {

            return;

        }





        try {



            const binary =

                atob(

                    base64Wav

                );





            const bytes =

                new Uint8Array(

                    binary.length

                );





            for (

                let i = 0;

                i < binary.length;

                i++

            ) {



                bytes[i] =

                    binary

                        .charCodeAt(

                            i

                        );

            }





            const blob =

                new Blob(

                    [bytes],

                    {

                        type:

                            'audio/wav'

                    }

                );





            console.log(

                '[HTN_NATIVE_MIC] WAV received:',

                blob.size

            );





            transcribeSegment(

                blob

            );



        } catch (err) {



            console.error(

                'Native WAV decode failed',

                err

            );





            status(

                'پردازش صدای ربات ناموفق بود.'

            );

        }

    };





window.onNativeWhisperError =

    message => {



        console.error(

            'Native microphone error:',

            message

        );





        stopConversation();





        status(

            message ||

            'میکروفن ربات در دسترس نیست.'

        );

    };





/*

 \* =============================================

 \* Android Native Speech callbacks

 \* =============================================

 */



window.onNativeSpeechStatus =

    state => {



        if (

            state === 'ready'

        ) {



            starting =

                false;



            recognizing =

                true;

        }





        if (

            state === 'speaking'

        ) {



            beginUserSpeech();

        }

    };





window.onNativePartialTranscription =

    text => {



        if (

            !active ||

            !text?.trim()

        ) {

            return;

        }





        if (

            audio ||

            controller

        ) {



            beginUserSpeech();

        }





        $('messageInput')

            .value =

            text;

    };





window.onNativeTranscription =

    text => {



        recognizing =

            false;



        starting =

            false;





        if (!active) {

            return;

        }





        if (

            text?.trim()

        ) {



            $('messageInput')

                .value =

                '';





            sendMessage(

                text

            );

        }





        scheduleListening();

    };





window.onNativeSpeechError =

    (

        code,

        message

    ) => {



        recognizing =

            false;



        starting =

            false;





        if (

            [

                5,

                6,

                7,

                8

            ]

                .includes(

                    Number(

                        code

                    )

                )

        ) {



            scheduleListening();



        } else {



            stopConversation();





            status(

                'تشخیص گفتار: ' +

                message

            );

        }

    };





function stopConversation() {
    hostSpeechUntil = 0;



    active =

        false;





    localMic

        ?.stop();





    stopNativeWhisperMic();





    clearTimeout(

        restartTimer

    );





    interrupt();





    try {



        if (

            !localMic &&

            nativeAvailable

        ) {



            Native

                .cancelNativeSpeechRecognition();



        } else if (

            !localMic

        ) {



            recognition

                ?.abort();

        }



    } catch (_) {}





    recognizing =

        false;





    starting =

        false;





    $('startBtn')

        .style

        .display =

        'inline-block';





    $('stopBtn')

        .style

        .display =

        'none';





    status(

        'گفتگوی صوتی متوقف شد.'

    );

}





/*

 \* =============================================

 \* START CONVERSATION

 \* =============================================

 */



$('startBtn').onclick =

    async () => {



        nativeAvailable =

            nativeSpeechAvailable();





        /*

         \* اگر Native AudioRecord موجود باشد

         \* مسیر اصلی همین است.

         */



        if (

            !nativeWhisperAvailable &&

            !nativeAvailable &&

            !recognition &&

            !localMic

        ) {



            status(

                'این دستگاه ورودی صوتی قابل استفاده ندارد.'

            );





            return;

        }





        active =

            true;





        $('startBtn')

            .style

            .display =

            'none';





        $('stopBtn')

            .style

            .display =

            'inline-block';





        /*

         \* مسیر Browser Microphone

         */



        if (

            localMic

        ) {



            try {



                await localMic

                    .start();



            } catch (err) {



                console.error(

                    'Local mic start failed',

                    err

                );





                stopConversation();





                status(

                    'اجازه دسترسی به میکروفن را فعال کنید.'

                );





                return;

            }





            if (!active) {

                return;

            }



        } else if (

            !nativeWhisperAvailable

        ) {



            startListening();

        }





        status(

            '🎤 آماده‌ام…'

        );





        /*

         \* پیام خوش‌آمدگویی فقط یک‌بار

         */



        if (

            !greeted

        ) {



            greeted =

                true;





            interrupt();





            const token =

                epoch;





            controller =

                new AbortController();





            try {



                await speak(

                    greeting,

                    token,

                    controller.signal

                );



            } catch (err) {



                if (

                    err.name !==

                    'AbortError'

                ) {



                    console.error(

                        err

                    );





                    status(

                        'برای شروع صحبت کنید.'

                    );

                }



            } finally {



                if (

                    token === epoch

                ) {



                    controller =

                        null;

                }

            }

        }





        /*

         \* بعد از Greeting

         \* Native Mic را روشن می‌کنیم

         */



        if (

            active &&

            nativeWhisperAvailable

        ) {



            if (

                !startNativeWhisperMic()

            ) {



                stopConversation();



                return;

            }





            status(

                '🎤 آماده‌ام؛ صحبت کنید…'

            );

        }

    };





$('stopBtn')

    .onclick =

    stopConversation;





$('chatForm')

    .onsubmit =

    event => {



        event.preventDefault();





        const text =

            $('messageInput')

                .value;





        $('messageInput')

            .value =

            '';





        sendMessage(

            text

        );

    };





/*

 \* تایپ کاربر پاسخ صوتی را قطع می‌کند

 */



$('messageInput')

    .addEventListener(

        'input',



        () => {



            if (

                audio ||

                controller

            ) {



                interrupt();





                status(

                    'منتظر تکمیل پیام شما هستم…'

                );

            }

        }

    );





/*

 \* دکمه قطع پاسخ

 */



const cut =

    document.createElement(

        'button'

    );





cut.id = "timoCutReplyBtn";

cut.type =

    'button';





cut.textContent =

    'قطع پاسخ';





cut.onclick =

    () => {



        interrupt();





        status(

            'پاسخ قطع شد؛ سوال بعدی را بپرسید.'

        );





        if (

            nativeWhisperAvailable

        ) {



            startNativeWhisperMic();



        } else if (

            !localMic

        ) {



            startListening();

        }

    };





$('stopBtn')

    .after(

        cut

    );





/*

 \* Slider فقط برای Browser Local Mic

 */



if (localMic) {



    const label =

        document.createElement(

            'label'

        );





    label.textContent =

        'آستانه تشخیص صدا: ';





    label.title =

        'اگر صدای آرام تشخیص داده نمی‌شود، مقدار را کمتر کنید. برای قطع پاسخ از دکمه قطع پاسخ استفاده کنید.';





    const level =

        document.createElement(

            'input'

        );





    level.type =

        'range';





    level.min =

        '10';





    level.max =

        '100';





    level.value =

        '15';





    level.style.width =

        '90px';





    level.oninput =

        () => {



            localMic.threshold =

                Number(

                    level.value

                ) / 1000;

        };





    label.appendChild(

        level

    );





    cut.after(

        label

    );

}





/*

 \* بستن تمیز Mic هنگام خروج

 */



window.addEventListener(

    'beforeunload',

    stopConversation

);


/* Recognition replies use exactly the same TTS and cancellation lifecycle as chat. */
window.TimoDialogue = {
    sessionId,
    canGreet() {
        return !document.hidden && !controller && !audio && !starting &&
            performance.now() >= hostSpeechUntil && !(active && localMic?.speech) &&
            (!active || nativeWhisperAvailable || !!localMic);
    },
    async greet(text) {
        if (!this.canGreet()) return false;
        interrupt();
        const token = epoch;
        controller = new AbortController();
        const signal = controller.signal;
        const resumeLocal = active && !!localMic;
        if (resumeLocal) localMic.stop();
        addMessage(text, 'bot');
        try {
            await speak(text, token, signal);
            return token === epoch;
        } catch (error) {
            if (token === epoch) status('صدای سلام پخش نشد؛ اتصال صدا را بررسی کنید.');
            return false;
        } finally {
            if (token === epoch) {
                controller = null;
                if (active && nativeWhisperAvailable) startNativeWhisperMic();
                if (resumeLocal && active) await localMic.start().catch(() => {});
                status(active ? '🎤 منتظر صحبت شما هستم…' : 'آماده پیام بعدی');
            }
            scheduleListening();
        }
    }
};


$('newConversationBtn')?.addEventListener('click', () => {
    stopConversation();
    try { window.localStorage.removeItem('timo-conversation-id'); } catch (_) {}
    location.reload();
});
