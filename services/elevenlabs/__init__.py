__all__ = [
    "ElevenLabsASR",
    "ElevenLabsTranscriptionResult",
    "SrtFormatOptions",
    "convert_file",
]


def __getattr__(name: str):
    if name == "ElevenLabsASR":
        from .asr import ElevenLabsASR

        return ElevenLabsASR
    if name == "ElevenLabsTranscriptionResult":
        from .asr import ElevenLabsTranscriptionResult

        return ElevenLabsTranscriptionResult
    if name == "SrtFormatOptions":
        from .srt import SrtFormatOptions

        return SrtFormatOptions
    if name == "convert_file":
        from .srt import convert_file

        return convert_file
    raise AttributeError(name)
