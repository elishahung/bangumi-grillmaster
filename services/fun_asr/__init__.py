__all__ = ["FunASR"]


def __getattr__(name: str):
    if name == "FunASR":
        from .fun_asr import FunASR

        return FunASR
    raise AttributeError(name)
