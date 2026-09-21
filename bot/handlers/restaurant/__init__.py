from aiogram import Router

from .utils import router as utils_router
from .accept import router as accept_router
from .ready import router as ready_router
from .cancel import router as cancel_router
from .partial import router as partial_router

router = Router()
router.include_router(utils_router)
router.include_router(accept_router)
router.include_router(ready_router)
router.include_router(cancel_router)
router.include_router(partial_router)
