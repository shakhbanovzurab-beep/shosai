"""The startup heap kept out of the cyclic garbage collector's passes (ADR 0065).

A process imports every slice and builds its apps before it serves: hundreds of thousands
of objects that live as long as it does. Each full pass of the cyclic collector walks them
all — about 300 ms on the composed API — and pauses whatever request runs then. Once the
role has started, the startup garbage is collected and the rest frozen, so later passes
walk only what the work itself allocates.
"""

import gc

import structlog

log = structlog.stdlib.get_logger(__name__)


def freeze_startup_heap() -> int:
    """Collect the startup garbage and freeze what lives on; how many objects were frozen."""
    gc.collect()
    gc.freeze()
    frozen = gc.get_freeze_count()
    log.info("Куча старта заморожена для сборщика", frozen_objects=frozen)
    return frozen
