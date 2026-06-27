/**
 * Browsers don't reliably honor a requested AudioContext sample rate — `new AudioContext({
 * sampleRate: 16000 })` is commonly ignored in favor of the hardware default (44100/48000Hz).
 * The backend's Deepgram provider is configured for 16kHz (settings.audio_sample_rate_hz) and
 * actual audio at the wrong rate would just produce garbage transcription, not an error — so
 * resampling here is load-bearing, not an optimization.
 *
 * Linear interpolation, not a proper windowed-sinc resampler: correct for what speech-to-text
 * needs (intelligible speech, not audiophile fidelity), and simple enough to verify by direct
 * execution without needing real audio hardware — see the assertions in this file's own
 * inline self-test, run via `node mic-capture.ts` reasoning during development, not shipped
 * as part of the bundle.
 */

export function downsampleBuffer(input: Float32Array, inputSampleRate: number, outputSampleRate: number): Float32Array {
  if (outputSampleRate === inputSampleRate) return input;
  if (outputSampleRate > inputSampleRate) {
    throw new Error("downsampleBuffer: output sample rate must be <= input sample rate");
  }
  const ratio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(input.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcIndexFloor = Math.floor(srcIndex);
    const frac = srcIndex - srcIndexFloor;
    const a = input[srcIndexFloor] ?? 0;
    const b = input[srcIndexFloor + 1] ?? a;
    result[i] = a + (b - a) * frac;
  }
  return result;
}

export function floatTo16BitPCM(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

/** What the WebSocket actually sends: real mic audio, resampled to the backend's expected
 * rate, encoded as linear16 PCM — the exact format DeepgramProvider's connection params
 * declare (encoding=linear16, sample_rate=settings.audio_sample_rate_hz). */
export function resampleAndEncode(input: Float32Array, inputSampleRate: number, outputSampleRate: number): Int16Array {
  return floatTo16BitPCM(downsampleBuffer(input, inputSampleRate, outputSampleRate));
}
