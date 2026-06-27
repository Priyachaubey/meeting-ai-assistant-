import { describe, expect, it } from "vitest";
import { downsampleBuffer, floatTo16BitPCM, resampleAndEncode } from "./mic-capture";

function sineWave(length: number, sampleRate: number, freq = 440): Float32Array {
  const wave = new Float32Array(length);
  for (let i = 0; i < length; i++) wave[i] = Math.sin((2 * Math.PI * freq * i) / sampleRate);
  return wave;
}

describe("downsampleBuffer", () => {
  it("produces the correct length ratio when downsampling 48kHz to 16kHz", () => {
    const input = sineWave(4800, 48000);
    const result = downsampleBuffer(input, 48000, 16000);
    expect(Math.abs(result.length - 1600)).toBeLessThanOrEqual(1);
  });

  it("is a no-op passthrough when rates match", () => {
    const input = sineWave(100, 16000);
    expect(downsampleBuffer(input, 16000, 16000)).toBe(input);
  });

  it("throws if asked to upsample", () => {
    const input = sineWave(100, 16000);
    expect(() => downsampleBuffer(input, 16000, 48000)).toThrow();
  });
});

describe("floatTo16BitPCM", () => {
  it("maps the full float range to valid Int16 bounds", () => {
    const pcm = floatTo16BitPCM(new Float32Array([0, 1, -1, 0.5, -0.5]));
    expect(pcm[0]).toBe(0);
    expect(pcm[1]).toBe(0x7fff);
    expect(pcm[2]).toBe(-0x8000);
    expect(pcm[3]).toBeGreaterThan(0);
    expect(pcm[3]).toBeLessThan(0x7fff);
  });

  it("clips out-of-range input instead of overflowing", () => {
    const clipped = floatTo16BitPCM(new Float32Array([2.5, -3.0]));
    expect(clipped[0]).toBe(0x7fff);
    expect(clipped[1]).toBe(-0x8000);
  });
});

describe("resampleAndEncode", () => {
  it("produces valid Int16 samples at the resampled length", () => {
    const input = sineWave(4800, 48000);
    const encoded = resampleAndEncode(input, 48000, 16000);
    expect(encoded.length).toBe(downsampleBuffer(input, 48000, 16000).length);
    for (const v of encoded) {
      expect(v).toBeGreaterThanOrEqual(-32768);
      expect(v).toBeLessThanOrEqual(32767);
    }
  });
});
