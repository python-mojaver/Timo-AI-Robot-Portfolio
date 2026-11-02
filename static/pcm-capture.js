/* Runs on the audio rendering thread; transfers every captured sample once. */
class PrimePCMCapture extends AudioWorkletProcessor {
    constructor() {
        super();
        this.buffer = new Float32Array(2048);
        this.offset = 0;
    }
    process(inputs) {
        const channels = inputs[0];
        if (!channels?.length) return true;
        const frames = channels[0].length;
        for (let i = 0; i < frames; i++) {
            let sample = 0;
            for (const channel of channels) sample += channel[i] || 0;
            // کانال‌ها را میانگین می‌گیریم تا یک جریان تک‌کاناله با همان نرخ نمونه‌برداری داشته باشیم.
            this.buffer[this.offset++] = sample / channels.length;
            if (this.offset === this.buffer.length) {
                // مالکیت بافر منتقل می‌شود؛ برای ادامهٔ ضبط باید بافر تازه بسازیم.
                this.port.postMessage(this.buffer, [this.buffer.buffer]);
                this.buffer = new Float32Array(2048);
                this.offset = 0;
            }
        }
        return true;
    }
}
registerProcessor('prime-pcm-capture', PrimePCMCapture);
