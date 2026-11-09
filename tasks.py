import asyncio

from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener
from lnbits.utils.safe_http import SafeHttpClient
from loguru import logger

from .cloudflare import cloudflare_create_subdomain
from .crud import get_domain, set_subdomain_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while settings.lnbits_running:
        payment = await invoice_queue.get()
        try:
            await on_invoice_paid(payment)
        except Exception as exc:
            # One bad payment must not kill the listener for all later payments.
            logger.error(
                f"failed to process subdomain payment {payment.payment_hash}: {exc}"
            )


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "lnsubdomain":
        return
    subdomain = await set_subdomain_paid(payment_hash=payment.payment_hash)
    domain = await get_domain(subdomain.domain)
    assert domain, "domain for subdomain does not exist"

    ### Create subdomain
    try:
        cf_response = await cloudflare_create_subdomain(
            domain=domain,
            subdomain=subdomain.subdomain,
            record_type=subdomain.record_type,
            ip=subdomain.ip,
        )
    except Exception as exc:
        logger.error(exc)
        logger.error("could not create subdomain on cloudflare")
        return

    ### Use webhook to notify about cloudflare registration
    if domain and domain.webhook:
        async with SafeHttpClient(read_body=False) as client:
            try:
                r = await client.post(
                    domain.webhook,
                    json={
                        "domain": subdomain.domain_name,
                        "subdomain": subdomain.subdomain,
                        "record_type": subdomain.record_type,
                        "email": subdomain.email,
                        "ip": subdomain.ip,
                        "cost:": str(subdomain.sats) + " sats",
                        "duration": str(subdomain.duration) + " days",
                        "cf_response": cf_response,
                    },
                    timeout=6,
                )
                r.raise_for_status()
            except Exception as exc:
                logger.error(f"""
                    failed to send webhook for subdomain {subdomain.subdomain},
                    with error type {type(exc).__name__}
                    """)
