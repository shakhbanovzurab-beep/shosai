"""`images.draw` as the model sees it (AG-D10; agent step 16b2): the operator's own toolset,
since `platform` holds its eight tools (Leo §8.1).

A picture for the operator: an illustration of a report or an idea, never a person's content.
The answer shows it by reference under the text.
"""

from datetime import timedelta
from typing import Final

from shosai.core.agent_tools.spec import CostClass, ToolEffect, ToolSpec
from shosai.features.agent.application.platform_images import DrawImageIn, DrawImageOut
from shosai.features.agent.domain.operator import IMAGES_TOOLSET

DRAW_IMAGE: Final = ToolSpec(
    name=f"{IMAGES_TOOLSET}.draw", toolset=IMAGES_TOOLSET,
    description=(
        "Draw a picture for the operator: an illustration of a report, an idea or a layout. "
        "It appears under your answer; describe it in words only briefly. Never draw a chart "
        "of numbers: the reports already give one."
    ),
    input=DrawImageIn, output=DrawImageOut, effect=ToolEffect.READ, cost_class=CostClass.METERED,
    timeout=timedelta(seconds=100), step_detail="caption",
)  # fmt: skip
IMAGE_TOOLS: Final = (DRAW_IMAGE,)
