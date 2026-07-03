from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runfeeti.directions import Step
    from runfeeti.routing import RoutedPath


@dataclass(frozen=True)
class RouteBuildResult:
    """Report text plus objects needed for turtle map / further use."""

    report_text: str
    routed: RoutedPath
    steps: list[Step]
