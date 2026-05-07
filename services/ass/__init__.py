__all__ = [
    "convert_file",
]


def __getattr__(name: str):
    if name == "convert_file":
        from .converter import convert_file

        return convert_file
    raise AttributeError(name)
