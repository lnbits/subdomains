from unittest.mock import AsyncMock

import pytest
from lnbits.core.crud import get_payment

from .. import tasks as subdomains_tasks
from .. import views_api as subdomains_views_api
from ..crud import get_domain, get_subdomain


@pytest.mark.asyncio
async def test_create_invoice_and_settle_subdomain_end_to_end(
    client, monkeypatch, wallet, domain_factory, subdomain_factory
):
    monkeypatch.setattr(
        subdomains_views_api,
        "cloudflare_create_subdomain",
        AsyncMock(return_value={"result": {"id": "cf-record-id"}}),
    )
    monkeypatch.setattr(subdomains_views_api, "cloudflare_deletesubdomain", AsyncMock())
    monkeypatch.setattr(
        subdomains_tasks,
        "cloudflare_create_subdomain",
        AsyncMock(return_value={"result": {"id": "cf-record-id"}}),
    )

    domain = await domain_factory()
    data = subdomain_factory(domain.id)

    response = await client.post(
        f"/subdomains/api/v1/subdomains/{domain.id}",
        json=data.model_dump(),
    )

    assert response.status_code == 200, response.text
    invoice = response.json()
    assert invoice["payment_hash"]
    assert invoice["payment_request"]

    subdomain = await get_subdomain(invoice["payment_hash"])
    assert subdomain is not None
    assert subdomain.domain_name == domain.domain
    assert subdomain.subdomain == data.subdomain
    assert subdomain.paid is False

    status_response = await client.get(
        f"/subdomains/api/v1/subdomains/{invoice['payment_hash']}"
    )
    assert status_response.status_code == 200
    assert status_response.json() == {"paid": False}

    payment = await get_payment(invoice["payment_hash"])
    assert payment is not None
    assert payment.extra.get("tag") == "lnsubdomain"

    await subdomains_tasks.on_invoice_paid(payment)

    subdomain = await get_subdomain(invoice["payment_hash"])
    assert subdomain is not None
    assert subdomain.paid is True
    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == 21
