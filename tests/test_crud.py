import pytest

from ..crud import (
    create_subdomain,
    db,
    get_domain,
    get_subdomain,
    set_subdomain_paid,
    update_domain,
)


@pytest.mark.asyncio
async def test_create_subdomain_persists_and_reads_joined_domain_name(
    wallet, domain_factory, subdomain_factory
):
    domain = await domain_factory()
    data = subdomain_factory(domain.id)

    subdomain = await create_subdomain(
        payment_hash="pay_hash_1",
        wallet=wallet.id,
        data=data,
        domain=domain,
    )

    assert subdomain.domain_name == domain.domain
    fetched = await get_subdomain("pay_hash_1")
    assert fetched is not None
    assert fetched.domain_name == domain.domain

    # domain_name is derived from the join; it must never be written as a column.
    raw = await db.fetchone(
        "SELECT * FROM subdomains.subdomain WHERE id = :id", {"id": "pay_hash_1"}
    )
    assert "domain_name" not in dict(raw)


@pytest.mark.asyncio
async def test_create_subdomain_ignores_forged_domain_from_request_body(
    wallet, domain_factory, subdomain_factory
):
    domain = await domain_factory()
    other_domain = await domain_factory()
    # A hand-crafted payload can point the FK at a different domain; the
    # resolved domain must win so the paid task cannot use another domain's
    # Cloudflare credentials.
    data = subdomain_factory(other_domain.id)

    subdomain = await create_subdomain(
        payment_hash="pay_hash_forged",
        wallet=wallet.id,
        data=data,
        domain=domain,
    )

    assert subdomain.domain == domain.id
    fetched = await get_subdomain("pay_hash_forged")
    assert fetched is not None
    assert fetched.domain == domain.id
    assert fetched.domain_name == domain.domain


@pytest.mark.asyncio
async def test_set_subdomain_paid_is_idempotent(
    wallet, domain_factory, subdomain_factory
):
    domain = await domain_factory()
    data = subdomain_factory(domain.id)
    await create_subdomain(
        payment_hash="pay_hash_2",
        wallet=wallet.id,
        data=data,
        domain=domain,
    )

    settled = await set_subdomain_paid("pay_hash_2")
    assert settled.paid is True
    assert settled.domain_name == domain.domain

    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == data.sats

    # Settling the same invoice twice must not double count the revenue.
    await set_subdomain_paid("pay_hash_2")
    domain_after = await get_domain(domain.id)
    assert domain_after is not None
    assert domain_after.amountmade == data.sats


@pytest.mark.asyncio
async def test_set_subdomain_paid_rejects_unknown_subdomain():
    with pytest.raises(ValueError, match="does not exist"):
        await set_subdomain_paid("missing_payment_hash")


@pytest.mark.asyncio
async def test_renamed_domain_is_reflected_in_subdomain(
    wallet, domain_factory, subdomain_factory
):
    domain = await domain_factory()
    await create_subdomain(
        payment_hash="pay_hash_3",
        wallet=wallet.id,
        data=subdomain_factory(domain.id),
        domain=domain,
    )

    domain.domain = f"renamed-{domain.domain}"
    await update_domain(domain)

    fetched = await get_subdomain("pay_hash_3")
    assert fetched is not None
    assert fetched.domain_name == domain.domain
