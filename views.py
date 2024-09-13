from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from .crud import get_domain

subdomains_generic_router = APIRouter()


def subdomains_renderer():
    return template_renderer(["subdomains/templates"])


@subdomains_generic_router.get("/", response_class=HTMLResponse)
async def index(
    request: Request, user: User = Depends(check_user_exists)  # type:ignore
):
    return subdomains_renderer().TemplateResponse(
        "subdomains/index.html", {"request": request, "user": user.dict()}
    )


@subdomains_generic_router.get("/{domain_id}")
async def display(request: Request, domain_id):
    domain = await get_domain(domain_id)
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )
    allowed_records = (
        domain.allowed_record_types.replace('"', "").replace(" ", "").split(",")
    )

    return subdomains_renderer().TemplateResponse(
        "subdomains/display.html",
        {
            "request": request,
            "domain_id": domain.id,
            "domain_domain": domain.domain,
            "domain_desc": domain.description,
            "domain_cost": domain.cost,
            "domain_allowed_record_types": allowed_records,
        },
    )
