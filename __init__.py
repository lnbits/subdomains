import asyncio

from fastapi import APIRouter
from loguru import logger

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import create_permanent_unique_task

db = Database("ext_subdomains")

subdomains_ext: APIRouter = APIRouter(prefix="/subdomains", tags=["subdomains"])

subdomains_static_files = [
    {
        "path": "/subdomains/static",
        "name": "subdomains_static",
    }
]


def subdomains_renderer():
    return template_renderer(["subdomains/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


scheduled_tasks: list[asyncio.Task] = []


def subdomains_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def subdomains_start():
    task = create_permanent_unique_task("ext_subdomains", wait_for_paid_invoices)
    scheduled_tasks.append(task)
