class Meter extends AudioWorkletProcessor {
  constructor() {
    super();
    this.reset();
    this.startFrame = Infinity;
    this.endFrame = 0;
    this.port.onmessage = ({ data }) => {
      this.reset();
      if (data !== "reset") {
        this.startFrame = Math.round(data.start * sampleRate);
        this.endFrame = Math.round(data.end * sampleRate);
        this.expectedFrames = Math.max(0, this.endFrame - this.startFrame);
      } else {
        this.startFrame = Infinity;
        this.endFrame = 0;
      }
    };
  }

  reset() {
    this.blocks = 0;
    this.silentBlocks = 0;
    this.longestSilenceFrames = 0;
    this.silenceRunFrames = 0;
    this.expectedFrames = 0;
    this.observedFrames = 0;
    this.lastPostedFrames = 0;
    this.windowComplete = false;
  }

  report() {
    return {
      blocks: this.blocks,
      silentBlocks: this.silentBlocks,
      expectedFrames: this.expectedFrames,
      observedFrames: this.observedFrames,
      longestSilenceMs: this.longestSilenceFrames / sampleRate * 1000,
      windowComplete: this.windowComplete,
    };
  }

  process(inputs, outputs) {
    const input = inputs[0] ?? [];
    const output = outputs[0] ?? [];
    const frames = output[0]?.length ?? input[0]?.length ?? 128;
    for (let channel = 0; channel < output.length; channel++) {
      const source = input[channel] ?? input[0];
      if (source) output[channel].set(source);
      else output[channel].fill(0);
    }

    if (this.windowComplete || this.startFrame === Infinity) return true;

    const blockStart = currentFrame;
    const blockEnd = blockStart + frames;
    const overlapStart = Math.max(blockStart, this.startFrame);
    const overlapEnd = Math.min(blockEnd, this.endFrame);
    const measuredFrames = Math.max(0, overlapEnd - overlapStart);

    if (measuredFrames > 0) {
      const first = overlapStart - blockStart;
      const last = overlapEnd - blockStart;
      let power = 0;
      let samples = 0;
      for (const channel of input) {
        if (!channel) continue;
        const end = Math.min(last, channel.length);
        for (let frame = first; frame < end; frame++) power += channel[frame] * channel[frame];
        samples += Math.max(0, end - first);
      }

      this.blocks++;
      this.observedFrames += measuredFrames;
      if (samples === 0 || power / samples < 0.000001) {
        this.silentBlocks++;
        this.silenceRunFrames += measuredFrames;
        this.longestSilenceFrames = Math.max(this.longestSilenceFrames, this.silenceRunFrames);
      } else {
        this.silenceRunFrames = 0;
      }
    }

    if (blockEnd >= this.endFrame) this.windowComplete = true;
    if (this.windowComplete || (this.blocks > 0 && this.blocks % 40 === 0 && this.observedFrames !== this.lastPostedFrames)) {
      this.lastPostedFrames = this.observedFrames;
      this.port.postMessage(this.report());
    }
    return true;
  }
}

registerProcessor("meter", Meter);
