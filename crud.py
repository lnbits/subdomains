from typing import Optional, Union

from lnbits.db import Database
from lnbits.helpers import insert_query, update_query, urlsafe_short_hash

from .models import CreateDomain, CreateSubdomain, Domain, Subdomain

db = Database("ext_subdomains")


async def create_subdomain(payment_hash, wallet, data: CreateSubdomain) -> Subdomain:
    subdomain = Subdomain(
        id=payment_hash,
        wallet=wallet,
        **data.dict(),
    )
    await db.execute(
        insert_query("subdomains.subdomain", subdomain),
        subdomain.dict(),
    )
    return subdomain


async def set_subdomain_paid(payment_hash: str) -> Subdomain:
    row = await db.fetchone(
        """
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.id = :id
        """,
        {"id": payment_hash},
    )
    if row["paid"] is False:
        await db.execute(
            "UPDATE subdomains.subdomain SET paid = true WHERE id = :id",
            {"id": payment_hash},
        )

        domaindata = await get_domain(row["id"])
        assert domaindata, "Couldn't get domain from paid subdomain"

        amount = domaindata.amountmade + row["sats"]
        await db.execute(
            """
            UPDATE subdomains.domain
            SET amountmade = :amount
            WHERE id = :id
            """,
            {"amount": amount, "id": row["id"]},
        )

    new_subdomain = await get_subdomain(payment_hash)
    assert new_subdomain, "Newly paid subdomain couldn't be retrieved"
    return new_subdomain


async def get_subdomain(subdomain_id: str) -> Optional[Subdomain]:
    row = await db.fetchone(
        """
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.id = :id
        """,
        {"id": subdomain_id},
    )
    return Subdomain(**row) if row else None


async def get_subdomain_by_subdomain(subdomain: str) -> Optional[Subdomain]:
    row = await db.fetchone(
        """
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.subdomain = :id
        """,
        {"id": subdomain},
    )
    return Subdomain(**row) if row else None


async def get_subdomains(wallet_ids: Union[str, list[str]]) -> list[Subdomain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    rows = await db.fetchall(
        f"""
        SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s
        INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.wallet IN ({q})
        """
    )

    return [Subdomain(**row) for row in rows]


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
    await db.execute(
        insert_query("subdomains.domain", domain),
        domain.dict(),
    )
    return domain


async def update_domain(domain: Domain) -> Domain:
    await db.execute(
        update_query("subdomains.domain", domain),
        domain.dict(),
    )
    return domain


async def get_domain(domain_id: str) -> Optional[Domain]:
    row = await db.fetchone(
        "SELECT * FROM subdomains.domain WHERE id = :id", {"id": domain_id}
    )
    return Domain(**row) if row else None


async def get_domains(wallet_ids: Union[str, list[str]]) -> list[Domain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    rows = await db.fetchall(f"SELECT * FROM subdomains.domain WHERE wallet IN ({q})")

    return [Domain(**row) for row in rows]


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM subdomains.domain WHERE id = :id", {"id": domain_id})
