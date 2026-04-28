__all__ = [
    "Gemini",
    "TranslationRequest",
    "TranslationResult",
    "GeminiTranslationError",
]


def __getattr__(name: str):
    if name in __all__:
        from .errors import GeminiTranslationError
        from .gemini import Gemini, TranslationRequest, TranslationResult

        exports = {
            "Gemini": Gemini,
            "TranslationRequest": TranslationRequest,
            "TranslationResult": TranslationResult,
            "GeminiTranslationError": GeminiTranslationError,
        }
        return exports[name]
    raise AttributeError(name)
