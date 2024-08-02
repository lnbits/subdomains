import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import subdomains_generic_router
from .views_api import subdomains_api_router

subdomains_ext: APIRouter = APIRouter(prefix="/subdomains", tags=["subdomains"])
subdomains_ext.include_router(subdomains_generic_router)
subdomains_ext.include_router(subdomains_api_router)

subdomains_static_files = [
    {
        "path": "/subdomains/static",
        "name": "subdomains_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def subdomains_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def subdomains_start():
    from lnbits.tasks import create_permanent_unique_task

    task = create_permanent_unique_task("ext_subdomains", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "db",
    "subdomains_ext",
    "subdomains_static_files",
    "subdomains_start",
    "subdomains_stop",
]
