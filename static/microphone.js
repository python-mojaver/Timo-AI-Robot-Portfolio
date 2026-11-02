/* Continuous PCM capture: no recorder restarts at idle/speech boundaries. */
class PrimeMicrophone {
    constructor(onSpeech, onAudio, onError, options = {}) {
        Object.assign(this, {onSpeech, onAudio, onError, running: false, generation: 0});
        this.options = options;
        this.threshold = 0.015;
        this.silenceMs = 950;
        // کمی صدای پیش از تشخیص شروع گفتار حفظ می‌شود تا ابتدای کلمه قطع نشود.
        this.preRollMs = 450;
        this.maxSpeechMs = 20000;
        this.playbackActive = false;
        this.listenAfter = 0;
        this.resetSegment();
    }
    resetSegment() {
        this.speech = false;
        this.loudMs = 0;
        this.quietMs = 0;
        this.elapsedMs = 0;
        this.parts = [];
        this.preRoll = [];
        this.preRollSamples = 0;
    }
    async start() {
        this.stop();
        const generation = this.generation;
        const processed = this.options.processed === true;
        const constraints = {
            echoCancellation: processed, noiseSuppression: processed, autoGainControl: processed
        };
        if (this.options.deviceId) constraints.deviceId = {exact: this.options.deviceId};
        const stream = await navigator.mediaDevices.getUserMedia({audio: constraints});
        if (generation !== this.generation) {stream.getTracks().forEach(t => t.stop()); return;}
        this.stream = stream;
        const context = new (window.AudioContext || window.webkitAudioContext)();
        this.context = context;
        try {
            await context.resume();
            if (generation !== this.generation) return;
            this.sampleRate = context.sampleRate;
            this.trackSettings = stream.getAudioTracks()[0]?.getSettings?.() || {};
            this.source = context.createMediaStreamSource(stream);
            let processor;
            if (context.audioWorklet && window.AudioWorkletNode) {
                await context.audioWorklet.addModule('/static/pcm-capture.js?v=voice2');
                if (generation !== this.generation) return;
                processor = new window.AudioWorkletNode(context, 'prime-pcm-capture');
                processor.port.onmessage = event => {
                    if (this.running && generation === this.generation) this.ingest(event.data);
                };
                processor.onprocessorerror = () => {
                    if (generation === this.generation) {this.stop(); this.onError(new Error('Audio capture failed'));}
                };
            } else {
                // Compatibility for older WebViews. Current Chrome uses AudioWorklet.
                processor = context.createScriptProcessor(2048, 1, 1);
                processor.onaudioprocess = event => {
                    if (this.running && generation === this.generation)
                        this.ingest(new Float32Array(event.inputBuffer.getChannelData(0)));
                };
            }
            this.processor = processor;
            this.mute = context.createGain();
            this.mute.gain.value = 0;
            this.resetSegment();
            this.running = true;
            this.source.connect(processor);
            processor.connect(this.mute).connect(context.destination);
            console.info('[MIC] Continuous PCM', {sampleRate: this.sampleRate,
                device: stream.getAudioTracks()[0]?.label, silenceMs: this.silenceMs,
                settings: this.trackSettings});
        } catch (error) {
            if (generation === this.generation) this.stop();
            throw error;
        }
    }
    ingest(input) {
        if (!this.running || !input.length) return;
        // صدای بلندگوی ربات و دنبالهٔ کوتاه پژواک وارد قطعهٔ جدید گفتار نمی‌شوند.
        if (this.playbackActive || Date.now() < this.listenAfter) return;
        const samples = new Float32Array(input);
        const ms = samples.length * 1000 / this.sampleRate;
        // در حالت دستی، پایان ضبط با کاربر یا سقف مدت است؛ تشخیص سکوت تصمیم‌گیر نیست.
        if (this.options.manual) {
            this.parts.push(samples);
            this.elapsedMs += ms;
            if (this.elapsedMs >= this.maxSpeechMs) this.finishRecording();
            return;
        }
        const rms = Math.sqrt(samples.reduce((sum, x) => sum + x * x, 0) / samples.length);
        if (!this.speech) {
            this.preRoll.push(samples);
            this.preRollSamples += samples.length;
            const limit = this.sampleRate * this.preRollMs / 1000;
            while (this.preRoll.length > 1 && this.preRollSamples - this.preRoll[0].length >= limit)
                this.preRollSamples -= this.preRoll.shift().length;
            this.loudMs = rms >= this.threshold ? this.loudMs + ms : 0;
            if (this.loudMs < 120) return;
            this.speech = true;
            this.parts = this.preRoll;
            this.preRoll = [];
            this.preRollSamples = 0;
            this.elapsedMs = this.parts.reduce((sum, part) => sum + part.length, 0) * 1000 / this.sampleRate;
            this.onSpeech();
            return;
        }
        this.parts.push(samples);
        this.elapsedMs += ms;
        // Hysteresis keeps quieter word endings after speech has started.
        this.quietMs = rms >= this.threshold * 0.65 ? 0 : this.quietMs + ms;
        if (this.quietMs >= this.silenceMs || this.elapsedMs >= this.maxSpeechMs) {
            const blob = this.wav(this.parts);
            console.info('[MIC] Speech segment', {durationMs: Math.round(this.elapsedMs), bytes: blob.size});
            this.resetSegment();
            this.onAudio(blob);
        }
    }
    finishRecording() {
        if (!this.parts.length) return;
        const blob = this.wav(this.parts);
        this.resetSegment();
        this.onAudio(blob);
    }
    setPlaybackActive(value) {
        this.playbackActive = !!value;
        // Discard speaker output and the short room echo tail before listening again.
        this.listenAfter = value ? 0 : Date.now() + 250;
        this.resetSegment();
    }
    wav(parts) {
        const count = parts.reduce((sum, part) => sum + part.length, 0);
        const buffer = new ArrayBuffer(44 + count * 2);
        const view = new DataView(buffer);
        const write = (offset, text) => {for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));};
        write(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); write(8, 'WAVE');
        write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
        view.setUint16(22, 1, true); view.setUint32(24, this.sampleRate, true);
        view.setUint32(28, this.sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
        write(36, 'data'); view.setUint32(40, count * 2, true);
        let offset = 44;
        for (const part of parts) for (const value of part) {
            const sample = Math.max(-1, Math.min(1, value));
            view.setInt16(offset, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
            offset += 2;
        }
        return new Blob([buffer], {type: 'audio/wav'});
    }
    stop() {
        this.running = false;
        this.playbackActive = false;
        this.listenAfter = 0;
        this.generation++;
        if (this.processor?.port) this.processor.port.onmessage = null;
        this.processor?.disconnect();
        this.source?.disconnect();
        this.mute?.disconnect();
        this.stream?.getTracks().forEach(t => t.stop());
        this.context?.close().catch(() => {});
        this.processor = this.source = this.mute = this.stream = this.context = null;
        this.resetSegment();
    }
}
window.PrimeMicrophone = PrimeMicrophone;
