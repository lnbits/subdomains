import httpx

from .models import Domain


async def cloudflare_create_subdomain(
    domain: Domain, subdomain: str, record_type: str, ip: str
):
    # Call to cloudflare sort of a dry-run
    # if success delete the domain and wait for payment
    ### SEND REQUEST TO CLOUDFLARE
    url = f"https://api.cloudflare.com/client/v4/zones/{domain.cf_zone_id}/dns_records"
    header = {
        "Authorization": f"Bearer {domain.cf_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers=header,
            json={
                "type": record_type,
                "name": f"{subdomain}.{domain.domain}",
                "content": ip,
                "ttl": 0,
                "proxied": False,
            },
            timeout=6,
        )
        r.raise_for_status()
        return r.json()


async def cloudflare_deletesubdomain(domain: Domain, domain_id: str):
    url = f"https://api.cloudflare.com/client/v4/zones/{domain.cf_zone_id}/dns_records/{domain_id}"
    header = {
        "Authorization": f"Bearer {domain.cf_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        await client.delete(url, headers=header, timeout=6)
