"""Silero VAD engine: speech regions for one 16 kHz mono WAV, as JSON on stdout.

Runs in a runtime with silero-vad and soundfile installed (not the repo env).
Settings match the word-timing v2 study (silero-vad 6.2.1, ONNX).
"""

import json
import sys

SETTINGS = {
    "threshold": 0.5,
    "min_speech_duration_ms": 100,
    "min_silence_duration_ms": 150,
    "speech_pad_ms": 0,
}


def main() -> None:
    import soundfile
    from silero_vad import get_speech_timestamps, load_silero_vad, read_audio

    path = sys.argv[1]
    model = load_silero_vad(onnx=True)
    wav = read_audio(path, sampling_rate=16000)
    stamps = get_speech_timestamps(
        wav, model, sampling_rate=16000, return_seconds=True, **SETTINGS
    )
    print(
        json.dumps(
            {
                "durationSec": soundfile.info(path).duration,
                "model": "silero-vad",
                "onnx": True,
                "settings": SETTINGS,
                "speechRegions": [
                    [round(float(s["start"]), 3), round(float(s["end"]), 3)]
                    for s in stamps
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
