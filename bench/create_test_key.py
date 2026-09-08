import asyncio
import sys

from switchboard.auth.keys import generate_api_key
from switchboard.core.config import get_settings
from switchboard.db.models import ApiKey, Tenant
from switchboard.db.session import build_engine, build_sessionmaker


async def main(tenant_name: str) -> None:
    engine = build_engine(get_settings())
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as session:
        tenant = Tenant(name=tenant_name)
        session.add(tenant)
        await session.flush()

        generated = generate_api_key()
        session.add(
            ApiKey(
                tenant_id=tenant.id,
                key_prefix=generated.key_prefix,
                key_hash=generated.key_hash,
            )
        )
        await session.commit()

        print(f"tenant_id: {tenant.id}")
        print(f"api_key:   {generated.key}")
    await engine.dispose()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "load-test-tenant"
    asyncio.run(main(name))