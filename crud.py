from typing import Optional, Union

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import CreateDomain, CreateSubdomain, Domain, Subdomain

db = Database("ext_subdomains")


async def create_subdomain(payment_hash, wallet, data: CreateSubdomain) -> Subdomain:
    subdomain = Subdomain(
        id=payment_hash,
        wallet=wallet,
        **data.dict(),
    )
    await db.insert("subdomains.subdomain", subdomain)
    return subdomain


async def set_subdomain_paid(payment_hash: str) -> Subdomain:
    subdomain = await db.fetchone(
        "SELECT * FROM subdomains.subdomain WHERE id = :id",
        {"id": payment_hash},
        Subdomain,
    )
    if subdomain.paid is False:
        subdomain.paid = True
        await db.update("subdomains.subdomain", subdomain)
        domain = await get_domain(subdomain.domain)
        assert domain, "Couldn't get domain from paid subdomain"
        domain.amountmade += subdomain.sats
        await db.update("subdomains.domain", domain)

    return subdomain


async def get_subdomain(subdomain_id: str) -> Optional[Subdomain]:
    return await db.fetchone(
        """
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.id = :id
        """,
        {"id": subdomain_id},
        Subdomain,
    )


async def get_subdomain_by_subdomain(subdomain: str) -> Optional[Subdomain]:
    return await db.fetchone(
        """
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.subdomain = :id
        """,
        {"id": subdomain},
        Subdomain,
    )


async def get_subdomains(wallet_ids: Union[str, list[str]]) -> list[Subdomain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"""
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.wallet IN ({q})
        """,
        model=Subdomain,
    )


async def delete_subdomain(subdomain_id: str) -> None:
    await db.execute(
        "DELETE FROM subdomains.subdomain WHERE id = :id",
        {"id": subdomain_id},
    )


async def create_domain(data: CreateDomain) -> Domain:
    domain = Domain(
        id=urlsafe_short_hash(),
        **data.dict(),
    )
    await db.insert("subdomains.domain", domain)
    return domain


async def update_domain(domain: Domain) -> Domain:
    await db.update("subdomains.domain", domain)
    return domain


async def get_domain(domain_id: str) -> Optional[Domain]:
    return await db.fetchone(
        "SELECT * FROM subdomains.domain WHERE id = :id",
        {"id": domain_id},
        Domain,
    )


async def get_domains(wallet_ids: Union[str, list[str]]) -> list[Domain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"SELECT * FROM subdomains.domain WHERE wallet IN ({q})", model=Domain
    )


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM subdomains.domain WHERE id = :id", {"id": domain_id})
