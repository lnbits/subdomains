from fastapi import Query
from pydantic import BaseModel


class CreateDomain(BaseModel):
    wallet: str = Query(...)
    domain: str = Query(...)
    cf_token: str = Query(...)
    cf_zone_id: str = Query(...)
    webhook: str = Query("")
    description: str = Query(..., min_length=0)
    cost: int = Query(..., ge=0)
    allowed_record_types: str = Query(...)


class CreateSubdomain(BaseModel):
    domain: str = Query(...)
    subdomain: str = Query(...)
    email: str = Query(...)
    ip: str = Query(...)
    sats: int = Query(..., ge=0)
    duration: int = Query(...)
    record_type: str = Query(...)


class Domain(BaseModel):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: str
    description: str
    cost: int
    time: int
    allowed_record_types: str
    amountmade: int = 0


class Subdomain(BaseModel):
    id: str
    wallet: str
    domain: str
    domain_name: str
    subdomain: str
    email: str
    ip: str
    sats: int
    duration: int
    time: int
    record_type: str
    paid: bool = False
