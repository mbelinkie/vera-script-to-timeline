import assert from "node:assert/strict";
import test from "node:test";

test("meter counts disconnected input as silence, finishes its window, and does not flood reports", async () => {
  const globals = ["AudioWorkletProcessor", "registerProcessor", "sampleRate", "currentFrame", "currentTime"];
  const original = new Map(globals.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const messages = [];
  let MeterProcessor;
  const sampleRate = 48000;
  globalThis.AudioWorkletProcessor = class {
    constructor() {
      this.port = { onmessage: null, postMessage: (message) => messages.push(message) };
    }
  };
  globalThis.registerProcessor = (name, processor) => {
    assert.equal(name, "meter");
    MeterProcessor = processor;
  };
  globalThis.sampleRate = sampleRate;

  const runBlock = (processor, frame, input) => {
    globalThis.currentFrame = frame;
    globalThis.currentTime = frame / sampleRate;
    const output = new Float32Array(128);
    assert.equal(processor.process(input, [[output]]), true);
    return output;
  };

  try {
    await import(`./meter.mjs?test=${Date.now()}`);

    const disconnected = new MeterProcessor();
    disconnected.port.onmessage({ data: { start: 0, end: 256 / sampleRate } });
    assert.deepEqual(runBlock(disconnected, 0, [[]]), new Float32Array(128));
    assert.deepEqual(runBlock(disconnected, 128, [[]]), new Float32Array(128));
    assert.equal(messages.length, 1);
    assert.deepEqual(messages[0], {
      blocks: 2,
      silentBlocks: 2,
      expectedFrames: 256,
      observedFrames: 256,
      longestSilenceMs: 256 / sampleRate * 1000,
      windowComplete: true,
    });
    for (let frame = 256; frame < 256 + 128 * 80; frame += 128) runBlock(disconnected, frame, [[]]);
    assert.equal(messages.length, 1, "completed windows should post only one final report");

    messages.length = 0;
    const tone = new MeterProcessor();
    tone.port.onmessage({ data: { start: 1, end: 1 + 256 / sampleRate } });
    for (let frame = 0; frame < 128 * 40; frame += 128) runBlock(tone, frame, [[]]);
    assert.equal(messages.length, 0, "an inactive window should not flood reports while its counters stay at zero");
    const signal = new Float32Array(128).fill(0.1);
    runBlock(tone, sampleRate, [[signal]]);
    runBlock(tone, sampleRate + 128, [[signal]]);
    assert.equal(messages.length, 1);
    assert.equal(messages[0].silentBlocks, 0, "a continuous tone is the negative control for silence detection");
    assert.equal(messages[0].expectedFrames, 256);
    assert.equal(messages[0].observedFrames, 256);
    assert.equal(messages[0].windowComplete, true);
  } finally {
    for (const name of globals) {
      const descriptor = original.get(name);
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
});
