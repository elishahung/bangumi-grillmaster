__all__ = [
    "CodexInvocationError",
    "CodexNotInstalledError",
    "CoverFileMissingError",
    "GlossaryCheckError",
    "RefinementValidationError",
    "generate_cover",
    "glossary_check_subtitles",
    "refine_subtitles",
    "run_codex_exec",
]


def __getattr__(name: str):
    if name in {"CodexInvocationError", "CodexNotInstalledError", "run_codex_exec"}:
        from .client import (
            CodexInvocationError,
            CodexNotInstalledError,
            run_codex_exec,
        )

        return {
            "CodexInvocationError": CodexInvocationError,
            "CodexNotInstalledError": CodexNotInstalledError,
            "run_codex_exec": run_codex_exec,
        }[name]
    if name in {"RefinementValidationError", "refine_subtitles"}:
        from .refine import RefinementValidationError, refine_subtitles

        return {
            "RefinementValidationError": RefinementValidationError,
            "refine_subtitles": refine_subtitles,
        }[name]
    if name in {"CoverFileMissingError", "generate_cover"}:
        from .cover import CoverFileMissingError, generate_cover

        return {
            "CoverFileMissingError": CoverFileMissingError,
            "generate_cover": generate_cover,
        }[name]
    if name in {"GlossaryCheckError", "glossary_check_subtitles"}:
        from .glossary_check import (
            GlossaryCheckError,
            glossary_check_subtitles,
        )

        return {
            "GlossaryCheckError": GlossaryCheckError,
            "glossary_check_subtitles": glossary_check_subtitles,
        }[name]
    raise AttributeError(name)
