import os
import uuid
from typing import Any, cast

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from lnbits.core import migrations as core_migrations
from lnbits.core.db import db as core_db
from lnbits.core.helpers import run_migration
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account_no_ckeck
from lnbits.settings import settings

from .. import migrations as ext_migrations
from .. import subdomains_ext
from ..crud import create_domain, db
from ..models import CreateDomain, CreateSubdomain, Domain


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_ext():
    if os.path.isfile(core_db.path):
        os.remove(core_db.path)
    async with core_db.connect() as conn:
        await run_migration(conn, core_migrations, "core")

    if os.path.isfile(db.path):
        os.remove(db.path)
    async with db.connect() as conn:
        await run_migration(conn, ext_migrations, "subdomains")


@pytest_asyncio.fixture(autouse=True)
def no_callback_rules(monkeypatch):
    monkeypatch.setattr(settings, "lnbits_callback_url_rules", [])


@pytest_asyncio.fixture
async def wallet():
    account = Account(id=uuid.uuid4().hex, username=f"subdomain_{uuid.uuid4().hex[:8]}")
    user = await create_user_account_no_ckeck(account=account, default_exts=[])
    return user.wallets[0]


@pytest_asyncio.fixture
async def domain_factory(wallet):
    async def factory(webhook: str = "") -> Domain:
        return await create_domain(
            CreateDomain(
                wallet=wallet.id,
                domain=f"d{uuid.uuid4().hex[:8]}.example.com",
                cf_token="cf-token",
                cf_zone_id="cf-zone-id",
                webhook=webhook,
                description="Test domain",
                cost=21,
                allowed_record_types="A,AAAA,TXT",
            )
        )

    return factory


@pytest_asyncio.fixture
def subdomain_factory():
    def factory(domain_id: str) -> CreateSubdomain:
        return CreateSubdomain(
            domain=domain_id,
            subdomain=f"s{uuid.uuid4().hex[:8]}",
            email="buyer@example.com",
            ip="93.184.216.34",
            sats=21,
            duration=30,
            record_type="A",
        )

    return factory


@pytest_asyncio.fixture
async def client():
    app = FastAPI()
    app.include_router(subdomains_ext)
    transport = ASGITransport(app=cast(Any, app))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
