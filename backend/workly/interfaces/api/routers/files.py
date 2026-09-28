from fastapi import APIRouter, Response

from workly.domain.errors import Forbidden, NotFound
from workly.infrastructure.storage import verify_file_signature

from ..deps import SettingsDep, StorageDep

router = APIRouter(prefix="/files", tags=["files"], include_in_schema=False)

_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp", b"%PDF": "application/pdf"}


@router.get("/{key:path}", name="get_file")
async def get_file(key: str, exp: int, sig: str, storage: StorageDep, settings: SettingsDep):
    """Imzoli havola (5 daqiqa). Ruxsat havolani bergan endpointda tekshirilgan va audit qilingan."""
    if not verify_file_signature(key, exp, sig, settings.jwt_secret.get_secret_value()):
        raise Forbidden("Havola yaroqsiz yoki muddati tugagan", code="INVALID_SIGNATURE")
    try:
        data = await storage.read(key)
    except (FileNotFoundError, ValueError):
        raise NotFound() from None
    media = next((m for magic, m in _TYPES.items() if data.startswith(magic)), "application/octet-stream")
    return Response(
        data,
        media_type=media,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
