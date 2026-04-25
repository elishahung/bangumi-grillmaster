__all__ = ["Gemini", "TranslationResult"]


def __getattr__(name: str):
    if name in __all__:
        from .gemini import Gemini, TranslationResult

        exports = {
            "Gemini": Gemini,
            "TranslationResult": TranslationResult,
        }
        return exports[name]
    raise AttributeError(name)
