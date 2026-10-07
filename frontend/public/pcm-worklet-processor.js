class Pcm16DownsamplerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.sourceSampleRate = sampleRate; // AudioWorklet global sampleRate
    this.ratio = this.sourceSampleRate / this.targetSampleRate;
    this.buffer = new Float32Array(0);
    this.phase = 0.0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true;
    }

    const inputChannel = input[0];
    
    // Append incoming samples to working buffer
    const newBuffer = new Float32Array(this.buffer.length + inputChannel.length);
    newBuffer.set(this.buffer, 0);
    newBuffer.set(inputChannel, this.buffer.length);
    this.buffer = newBuffer;

    const available = this.buffer.length;
    if (available < 2) {
      return true;
    }

    const outCapacity = Math.floor((available - 1 - this.phase) / this.ratio);
    if (outCapacity <= 0) {
      return true;
    }

    const pcm16 = new Int16Array(outCapacity);
    let outIdx = 0;

    while (this.phase + 1 < available && outIdx < outCapacity) {
      const idx = Math.floor(this.phase);
      const frac = this.phase - idx;

      if (idx + 1 >= available) {
        break;
      }

      const s0 = this.buffer[idx];
      const s1 = this.buffer[idx + 1];
      const interpolated = s0 + frac * (s1 - s0);

      // Clamp [-1.0, 1.0]
      const clamped = Math.max(-1.0, Math.min(1.0, interpolated));
      pcm16[outIdx++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;

      this.phase += this.ratio;
    }

    // Retain unprocessed tail samples
    const dropCount = Math.floor(this.phase);
    this.phase -= dropCount;
    this.buffer = this.buffer.slice(dropCount);

    if (outIdx > 0) {
      const sendBuffer = pcm16.buffer.slice(0, outIdx * 2);
      this.port.postMessage(sendBuffer, [sendBuffer]);
    }

    return true;
  }
}

registerProcessor("pcm16-downsampler", Pcm16DownsamplerProcessor);
