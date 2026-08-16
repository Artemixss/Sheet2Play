from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorContext:
    code: str
    stage: str
    message: str
    page: int | None = None


class ResearchError(RuntimeError):
    def __init__(
        self,
        code: str,
        stage: str,
        message: str,
        *,
        page: int | None = None,
    ) -> None:
        super().__init__(message)
        self.context = ErrorContext(code=code, stage=stage, message=message, page=page)

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def stage(self) -> str:
        return self.context.stage

    @property
    def page(self) -> int | None:
        return self.context.page

