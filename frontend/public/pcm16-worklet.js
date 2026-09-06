class Pcm16Worklet extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const settings = options.processorOptions;
    this.targetSampleRate = settings.sampleRate;
    this.targetChunkSamples = (this.targetSampleRate * settings.chunkMs) / 1000;
    this.sourceSamples = [];
    this.sourcePosition = 0;
    this.outputSamples = [];
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;

    this.sourceSamples.push(...input);
    const ratio = sampleRate / this.targetSampleRate;
    while (this.sourcePosition + ratio <= this.sourceSamples.length) {
      this.outputSamples.push(this.sourceSamples[Math.floor(this.sourcePosition)]);
      this.sourcePosition += ratio;
    }

    const consumed = Math.floor(this.sourcePosition);
    this.sourceSamples = this.sourceSamples.slice(consumed);
    this.sourcePosition -= consumed;
    this.flushFullChunks();
    return true;
  }

  flushFullChunks() {
    while (this.outputSamples.length >= this.targetChunkSamples) {
      const samples = this.outputSamples.splice(0, this.targetChunkSamples);
      const pcm = new Int16Array(samples.length);
      samples.forEach((sample, index) => {
        const clamped = Math.max(-1, Math.min(1, sample));
        pcm[index] = clamped < 0 ? clamped * 32768 : clamped * 32767;
      });
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
  }
}

registerProcessor("pcm16-worklet", Pcm16Worklet);
