import asyncio
import json
import socket
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from lnbits.core.models import Payment

from .. import tasks as subdomains_tasks
from ..crud import create_subdomain, get_domain, get_subdomain

PUBLIC_IP = "93.184.216.34"


def _resolve(monkeypatch, addresses):
    infos = [
        (
            socket.AF_INET6 if ":" in ip else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (ip, 443),
        )
        for ip in addresses
    ]
    dns = AsyncMock(return_value=infos)
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    return dns


def _mock_cloudflare(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value={"result": {"id": "cf-record-id"}})
    monkeypatch.setattr(subdomains_tasks, "cloudflare_create_subdomain", mock)
    return mock


def _record_safe_http_client(monkeypatch) -> dict:
    captured: dict = {}
    real_client = subdomains_tasks.SafeHttpClient

    def recording_client(*args, **kwargs):
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(subdomains_tasks, "SafeHttpClient", recording_client)
    return captured


def _record_sends(monkeypatch, error: Exception | None = None) -> list:
    sent: list[httpx.Request] = []

    async def fake_send(self, request, **kwargs):
        sent.append(request)
        if error is not None:
            raise error
        return httpx.Response(200, request=request, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    return sent


async def _paid_subdomain(domain_factory, subdomain_factory, wallet, webhook: str):
    domain = await domain_factory(webhook=webhook)
    data = subdomain_factory(domain.id)
    payment_hash = uuid4().hex
    await create_subdomain(
        payment_hash=payment_hash,
        wallet=wallet.id,
        data=data,
        domain_name=domain.domain,
    )
    payment = Payment(
        checking_id=f"checking_{payment_hash}",
        payment_hash=payment_hash,
        wallet_id=wallet.id,
        amount=data.sats * 1000,
        fee=0,
        bolt11="lnbc1fakepaymentrequest",
        extra={"tag": "lnsubdomain"},
    )
    return domain, data, payment


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "webhook",
    [
        "http://127.0.0.1:5000/hook",
        "http://10.1.2.3/hook",
        "http://192.168.1.9/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]:5000/hook",
        "http://0.0.0.0/hook",
    ],
)
async def test_private_webhook_is_blocked_without_rolling_back_paid_state(
    monkeypatch, wallet, domain_factory, subdomain_factory, webhook
):
    domain, _, payment = await _paid_subdomain(
        domain_factory, subdomain_factory, wallet, webhook
    )
    cloudflare = _mock_cloudflare(monkeypatch)
    sent = _record_sends(monkeypatch)

    await subdomains_tasks.on_invoice_paid(payment)

    assert sent == []
    cloudflare.assert_awaited_once()

    subdomain = await get_subdomain(payment.payment_hash)
    assert subdomain is not None
    assert subdomain.paid is True
    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == 21


@pytest.mark.asyncio
async def test_private_dns_answer_for_public_hostname_is_blocked(
    monkeypatch, wallet, domain_factory, subdomain_factory
):
    domain, _, payment = await _paid_subdomain(
        domain_factory, subdomain_factory, wallet, "http://127.0.0.1.nip.io/hook"
    )
    _mock_cloudflare(monkeypatch)
    sent = _record_sends(monkeypatch)
    # A user-controlled hostname must be resolved before it is allowed; here it
    # resolves to loopback, which has to be rejected.
    _resolve(monkeypatch, ["127.0.0.1"])

    await subdomains_tasks.on_invoice_paid(payment)

    assert sent == []
    subdomain = await get_subdomain(payment.payment_hash)
    assert subdomain is not None
    assert subdomain.paid is True
    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == 21


@pytest.mark.asyncio
async def test_public_webhook_is_delivered_with_domain_name_and_no_body_read(
    monkeypatch, wallet, domain_factory, subdomain_factory
):
    domain, data, payment = await _paid_subdomain(
        domain_factory, subdomain_factory, wallet, "https://hooks.example.com/notify"
    )
    _mock_cloudflare(monkeypatch)
    captured = _record_safe_http_client(monkeypatch)
    sent = _record_sends(monkeypatch)
    _resolve(monkeypatch, [PUBLIC_IP])

    await subdomains_tasks.on_invoice_paid(payment)

    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body["domain"] == domain.domain
    assert body["subdomain"] == data.subdomain
    assert body["record_type"] == data.record_type
    assert body["email"] == data.email
    assert body["cf_response"] == {"result": {"id": "cf-record-id"}}
    # The registration webhook must never read or store the response body.
    assert captured.get("read_body") is False

    subdomain = await get_subdomain(payment.payment_hash)
    assert subdomain is not None
    assert subdomain.paid is True


@pytest.mark.asyncio
async def test_webhook_transport_error_does_not_roll_back_paid_state(
    monkeypatch, wallet, domain_factory, subdomain_factory
):
    domain, _, payment = await _paid_subdomain(
        domain_factory, subdomain_factory, wallet, "https://hooks.example.com/notify"
    )
    _mock_cloudflare(monkeypatch)
    _record_sends(monkeypatch, error=httpx.ConnectError("webhook down"))
    _resolve(monkeypatch, [PUBLIC_IP])

    await subdomains_tasks.on_invoice_paid(payment)

    subdomain = await get_subdomain(payment.payment_hash)
    assert subdomain is not None
    assert subdomain.paid is True
    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == 21
