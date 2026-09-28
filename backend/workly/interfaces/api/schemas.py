from pydantic import BaseModel, ConfigDict, Field

from workly.domain.users import ConsentDoc, Lang, Role


class Names(BaseModel):
    uz_latn: str
    uz_cyrl: str
    ru: str

    @classmethod
    def of(cls, obj) -> "Names":
        return cls(uz_latn=obj.name_uz_latn, uz_cyrl=obj.name_uz_cyrl, ru=obj.name_ru)


# ---------- auth ----------
class TelegramLoginIn(BaseModel):
    init_data: str = Field(min_length=1, max_length=4096)


class OtpSendIn(BaseModel):
    phone: str = Field(max_length=32)


class OtpSendOut(BaseModel):
    expires_in: int


class OtpVerifyIn(BaseModel):
    phone: str = Field(max_length=32)
    code: str = Field(max_length=6)


class RefreshIn(BaseModel):
    refresh_token: str = Field(max_length=200)


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str | None
    phone_verified: bool
    telegram_id: int | None
    full_name: str | None
    lang: Lang
    status: str
    roles: list[str]

    @classmethod
    def of(cls, user) -> "MeOut":
        return cls(
            id=user.id,
            phone=user.phone,
            phone_verified=user.phone_verified_at is not None,
            telegram_id=user.telegram_id,
            full_name=user.full_name,
            lang=user.lang,
            status=user.status,
            roles=user.role_names,
        )


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: MeOut

    @classmethod
    def of(cls, pair) -> "TokenOut":
        return cls(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            expires_in=pair.expires_in,
            user=MeOut.of(pair.user),
        )


# ---------- profil ----------
class MePatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    lang: Lang | None = None


class RoleIn(BaseModel):
    role: Role


class ConsentItem(BaseModel):
    doc_type: ConsentDoc
    version: str = Field(min_length=1, max_length=16)


class ConsentIn(BaseModel):
    items: list[ConsentItem] = Field(min_length=1, max_length=10)


# ---------- katalog ----------
class SpecializationOut(BaseModel):
    id: int
    code: str
    name: Names


class CategoryOut(BaseModel):
    id: int
    code: str
    name: Names
    specializations: list[SpecializationOut]


class RegionOut(BaseModel):
    id: int
    code: str
    name: Names


class DistrictOut(BaseModel):
    id: int
    region_id: int
    code: str
    name: Names
