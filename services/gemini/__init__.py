__all__ = ["Gemini", "TranslationResult", "GeminiTranslationError"]


def __getattr__(name: str):
    if name in __all__:
        from .errors import GeminiTranslationError
        from .gemini import Gemini, TranslationResult

        exports = {
            "Gemini": Gemini,
            "TranslationResult": TranslationResult,
            "GeminiTranslationError": GeminiTranslationError,
        }
        return exports[name]
    raise AttributeError(name)
