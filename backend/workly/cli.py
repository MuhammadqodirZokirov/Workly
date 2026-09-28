"""Boshqaruv buyruqlari.

python -m workly.cli grant-role --phone +998901234567 --role super_admin
python -m workly.cli revoke-role --phone +998901234567 --role moderator
"""

import argparse
import asyncio

from sqlalchemy import select

from workly.application.audit import audit
from workly.domain.phone import normalize_phone
from workly.domain.users import Role
from workly.infrastructure.config import get_settings
from workly.infrastructure.db.models import User, UserRole
from workly.infrastructure.db.session import make_engine, make_sessionmaker


async def _run(args: argparse.Namespace) -> None:
    engine = make_engine(get_settings().database_url)
    try:
        async with make_sessionmaker(engine)() as db:
            user = await db.scalar(select(User).where(User.phone == normalize_phone(args.phone)))
            if user is None:
                raise SystemExit("Foydalanuvchi topilmadi — avval ilovaga kirsin (SMS yoki Telegram)")
            role = Role(args.role)
            if args.command == "grant-role":
                if role in user.role_names:
                    print(f"{user.phone}: '{role}' roli allaqachon bor")
                    return
                user.roles.append(UserRole(role=role))
            else:
                user.roles = [r for r in user.roles if r.role != role]
            audit(db, None, f"cli.{args.command}", "user", user.id, after={"role": role})
            await db.commit()
            print(f"{user.phone}: rollar = {', '.join(map(str, user.role_names))}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="workly")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("grant-role", "revoke-role"):
        p = sub.add_parser(name)
        p.add_argument("--phone", required=True)
        p.add_argument("--role", required=True, choices=[r.value for r in Role])
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
