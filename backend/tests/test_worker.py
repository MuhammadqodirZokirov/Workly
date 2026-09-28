from pathlib import Path

import pytest
from sqlalchemy import select

from workly.infrastructure.db.models import AuditLog, StateTransition, User, UserRole, WorkerProfile

API = "/api/v1"


def _blobs(root: str) -> list[Path]:
    return [p for p in Path(root).rglob("*") if p.is_file()]


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
PDF = b"%PDF-1.7\n" + b"\x00" * 200


@pytest.fixture
async def catalog(client):
    cats = {c["code"]: c for c in (await client.get(f"{API}/catalog/categories")).json()}
    districts = (await client.get(f"{API}/catalog/districts")).json()
    return cats, districts


@pytest.fixture
async def worker(client, login, redis):
    """Ishchi rolidagi, roziliklari berilgan foydalanuvchi."""

    async def _make(phone="+998901234567"):
        await redis.delete(f"otp:cooldown:{phone}")
        body, h = await login(phone)
        await client.post(f"{API}/me/roles", json={"role": "worker"}, headers=h)
        await client.post(
            f"{API}/me/consents",
            headers=h,
            json={"items": [{"doc_type": d, "version": "1.0"} for d in ("terms", "privacy", "worker_contract")]},
        )
        return body["user"]["id"], h

    return _make


def full_profile(cats, districts):
    c = cats["construction"]
    return {
        "full_name": "Jasur  Toshmatov",
        "birth_date": "1995-05-10",
        "gender": "male",
        "district_ids": [districts[0]["id"], districts[1]["id"]],
        "home_point": {"lat": 41.31, "lon": 69.24},
        "skills": [
            {
                "category_id": c["id"],
                "experience": "3_5",
                "specialization_ids": [c["specializations"][0]["id"], c["specializations"][5]["id"]],
            }
        ],
        "emergency_contact": {"name": "Ota", "phone": "+998907654321"},
    }


async def complete_worker(client, h, cats, districts):
    assert (await client.put(f"{API}/worker/profile", json=full_profile(cats, districts), headers=h)).status_code == 200
    for kind in ("id_card_front", "id_card_back", "selfie"):
        r = await client.post(
            f"{API}/worker/files", headers=h, data={"kind": kind}, files={"file": ("a.jpg", JPEG, "image/jpeg")}
        )
        assert r.status_code == 201, r.text


@pytest.fixture
async def moderator(client, login, redis, db):
    await redis.delete("otp:cooldown:+998909999999")
    body, h = await login("+998909999999")
    db.add(UserRole(user_id=body["user"]["id"], role="moderator"))
    await db.commit()
    return body["user"]["id"], h


# ---------------- profil ----------------
async def test_worker_role_required(client, login):
    _, h = await login()
    r = await client.get(f"{API}/worker/profile", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "NOT_A_WORKER"


async def test_profile_roundtrip(client, worker, catalog):
    cats, districts = catalog
    _, h = await worker()
    r = await client.put(f"{API}/worker/profile", json=full_profile(cats, districts), headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["full_name"] == "Jasur Toshmatov"
    assert p["skills"][0]["experience"] == "3_5" and len(p["skills"][0]["specialization_ids"]) == 2
    assert p["home_point"] == {"lat": 41.31, "lon": 69.24}
    assert p["verification"]["status"] == "not_submitted"

    # qisman yangilash: faqat jins; null — uy nuqtasini o'chiradi
    r = await client.put(f"{API}/worker/profile", json={"gender": "female", "home_point": None}, headers=h)
    p = r.json()
    assert p["gender"] == "female" and p["home_point"] is None and p["birth_date"] == "1995-05-10"


@pytest.mark.parametrize(
    "patch,code",
    [
        ({"birth_date": "2015-01-01"}, "UNDERAGE"),
        ({"birth_date": "2090-01-01"}, "INVALID_BIRTH_DATE"),
        ({"district_ids": [99999]}, "INVALID_DISTRICT"),
        ({"district_ids": []}, "DISTRICTS_REQUIRED"),
        ({"emergency_contact": {"phone": "+998901234567"}}, "INVALID_EMERGENCY"),
    ],
)
async def test_profile_validation(client, worker, patch, code):
    _, h = await worker()
    r = await client.put(f"{API}/worker/profile", json=patch, headers=h)
    assert r.status_code == 422 and r.json()["code"] == code


async def test_skills_validation(client, worker, catalog):
    cats, _ = catalog
    _, h = await worker()
    cargo_spec = cats["cargo"]["specializations"][0]["id"]
    r = await client.put(
        f"{API}/worker/profile",
        headers=h,
        json={
            "skills": [
                {"category_id": cats["construction"]["id"], "experience": "none", "specialization_ids": [cargo_spec]}
            ]
        },
    )
    assert r.json()["code"] == "INVALID_SPECIALIZATION"
    r = await client.put(
        f"{API}/worker/profile",
        headers=h,
        json={"skills": [{"category_id": 9999, "experience": "none", "specialization_ids": [cargo_spec]}]},
    )
    assert r.json()["code"] == "INVALID_CATEGORY"


async def test_inactive_category_rejected(client, worker, db):
    from workly.infrastructure.db.models import Category

    childcare = await db.scalar(select(Category).where(Category.code == "childcare"))
    _, h = await worker()
    r = await client.put(
        f"{API}/worker/profile",
        headers=h,
        json={"skills": [{"category_id": childcare.id, "experience": "none", "specialization_ids": [1]}]},
    )
    assert r.json()["code"] == "INVALID_CATEGORY"


# ---------------- jadval ----------------
async def test_availability(client, worker):
    _, h = await worker()
    slots = [
        {"weekday": 0, "start": "08:00", "end": "12:00"},
        {"weekday": 0, "start": "13:00", "end": "18:00"},
        {"weekday": 5, "start": "09:00", "end": "14:00"},
    ]
    r = await client.put(f"{API}/worker/availability", json={"slots": slots}, headers=h)
    assert r.status_code == 200 and len(r.json()["availability"]) == 3

    bad = [{"weekday": 1, "start": "08:00", "end": "12:00"}, {"weekday": 1, "start": "11:00", "end": "15:00"}]
    assert (await client.put(f"{API}/worker/availability", json={"slots": bad}, headers=h)).status_code == 422
    bad = [{"weekday": 1, "start": "12:00", "end": "08:00"}]
    assert (await client.put(f"{API}/worker/availability", json={"slots": bad}, headers=h)).status_code == 422


# ---------------- fayllar ----------------
async def test_file_upload_encrypted_and_replaced(client, worker, settings, db):
    uid, h = await worker()
    r = await client.post(
        f"{API}/worker/files", headers=h, data={"kind": "selfie"}, files={"file": ("s.png", PNG, "image/png")}
    )
    assert r.status_code == 201 and r.json()["content_type"] == "image/png"
    blobs = _blobs(settings.media_dir)
    assert len(blobs) == 1 and PNG not in blobs[0].read_bytes()  # diskda shifrlangan

    # qayta yuklash — eski nusxa o'chadi
    await client.post(
        f"{API}/worker/files", headers=h, data={"kind": "selfie"}, files={"file": ("s.jpg", JPEG, "image/jpeg")}
    )
    blobs = _blobs(settings.media_dir)
    assert len(blobs) == 1
    prof = (await client.get(f"{API}/worker/profile", headers=h)).json()
    assert [f["kind"] for f in prof["files"]] == ["selfie"] and prof["files"][0]["content_type"] == "image/jpeg"


@pytest.mark.parametrize(
    "kind,content,code",
    [
        ("selfie", b"hello world", "UNSUPPORTED_FILE"),
        ("selfie", PDF, "UNSUPPORTED_FILE"),  # PDF faqat guvohnoma uchun
        ("selfie", b"", "EMPTY_FILE"),
    ],
)
async def test_file_validation(client, worker, kind, content, code):
    _, h = await worker()
    r = await client.post(f"{API}/worker/files", headers=h, data={"kind": kind}, files={"file": ("x", content)})
    assert r.status_code == 422 and r.json()["code"] == code


async def test_file_too_large(client, worker, app):
    app.state.settings = app.state.settings.model_copy(update={"max_upload_mb": 1})
    _, h = await worker()
    big = JPEG + b"\x00" * (1024 * 1024)
    r = await client.post(f"{API}/worker/files", headers=h, data={"kind": "selfie"}, files={"file": ("x", big)})
    assert r.json()["code"] == "FILE_TOO_LARGE"


async def test_qualification_pdf_allowed(client, worker):
    _, h = await worker()
    r = await client.post(
        f"{API}/worker/files", headers=h, data={"kind": "qualification"}, files={"file": ("g.pdf", PDF)}
    )
    assert r.status_code == 201


# ---------------- verifikatsiyaga yuborish ----------------
async def test_submit_incomplete(client, worker):
    _, h = await worker()
    await client.get(f"{API}/worker/profile", headers=h)
    r = await client.post(
        f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "AA1234567"}, headers=h
    )
    assert r.status_code == 422 and r.json()["code"] == "PROFILE_INCOMPLETE"
    missing = r.json()["details"]
    assert {"birth_date", "gender", "skills", "districts", "file:selfie", "file:id_card_front"} <= set(missing)


async def test_submit_and_locks(client, worker, catalog, db):
    cats, districts = catalog
    uid, h = await worker()
    await complete_worker(client, h, cats, districts)
    r = await client.post(
        f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "aa 1234567"}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["verification"]["status"] == "pending"

    profile = await db.get(WorkerProfile, uid)
    assert profile.doc_number_enc and "AA1234567" not in profile.doc_number_enc  # shifrlangan

    # tekshiruv davomida hujjat va shaxsiy ma'lumot o'zgarmaydi, qayta yuborib bo'lmaydi
    r = await client.post(f"{API}/worker/files", headers=h, data={"kind": "selfie"}, files={"file": ("a", JPEG)})
    assert r.status_code == 409 and r.json()["code"] == "FILES_LOCKED"
    r = await client.put(f"{API}/worker/profile", json={"full_name": "Boshqa Odam"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "PROFILE_LOCKED"
    r = await client.put(f"{API}/worker/profile", json={"district_ids": [districts[2]["id"]]}, headers=h)
    assert r.status_code == 200  # tumanlarni o'zgartirish mumkin
    r = await client.post(
        f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "AA1234567"}, headers=h
    )
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATE"

    tr = (await db.scalars(select(StateTransition))).all()
    assert [(t.from_state, t.to_state) for t in tr] == [("not_submitted", "pending")]


async def test_bad_doc_number(client, worker, catalog):
    cats, districts = catalog
    _, h = await worker()
    await complete_worker(client, h, cats, districts)
    r = await client.post(
        f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "123456789"}, headers=h
    )
    assert r.json()["code"] == "INVALID_DOC_NUMBER"


# ---------------- moderator ----------------
async def test_moderation_flow(client, worker, catalog, moderator, notifier, db):
    cats, districts = catalog
    uid, h = await worker()
    await complete_worker(client, h, cats, districts)
    await client.post(f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "AA1234567"}, headers=h)
    mod_id, mh = moderator

    # oddiy foydalanuvchi navbatni ko'rolmaydi
    assert (await client.get(f"{API}/admin/verifications", headers=h)).status_code == 403

    q = (await client.get(f"{API}/admin/verifications", headers=mh)).json()
    assert [i["user_id"] for i in q] == [uid] and q[0]["age"] >= 18

    case = (await client.get(f"{API}/admin/verifications/{uid}", headers=mh)).json()
    assert case["doc_number"] == "AA1234567" and case["phone"] == "+998901234567"
    assert {f["kind"] for f in case["files"]} == {"id_card_front", "id_card_back", "selfie"}

    # imzoli havola asl faylni qaytaradi; imzo buzilsa — 403
    url = case["files"][0]["url"].replace("http://test", "")
    r = await client.get(url)
    assert r.status_code == 200 and r.content == JPEG and r.headers["cache-control"] == "no-store"
    assert (await client.get(url.replace("sig=", "sig=0"))).status_code == 403

    logs = (await db.scalars(select(AuditLog).where(AuditLog.action == "verification.view"))).all()
    assert len(logs) == 1 and logs[0].actor_id == mod_id

    # belgi uchun guvohnoma yo'q
    r = await client.post(f"{API}/admin/verifications/{uid}/approve", json={"badges": ["qualified"]}, headers=mh)
    assert r.json()["code"] == "BADGE_WITHOUT_FILE"

    r = await client.post(f"{API}/admin/verifications/{uid}/approve", json={}, headers=mh)
    assert r.status_code == 200 and r.json()["verification"]["status"] == "verified"
    assert notifier.calls == [(uid, True, None)]
    # ikki marta tasdiqlab bo'lmaydi
    assert (await client.post(f"{API}/admin/verifications/{uid}/approve", json={}, headers=mh)).status_code == 409


async def test_reject_and_resubmit(client, worker, catalog, moderator, notifier):
    cats, districts = catalog
    uid, h = await worker()
    await complete_worker(client, h, cats, districts)
    doc = {"doc_type": "id_card", "doc_number": "AA1234567"}
    await client.post(f"{API}/worker/verification", json=doc, headers=h)
    _, mh = moderator

    r = await client.post(f"{API}/admin/verifications/{uid}/reject", json={"reason": "other"}, headers=mh)
    assert r.json()["code"] == "COMMENT_REQUIRED"
    r = await client.post(f"{API}/admin/verifications/{uid}/reject", json={"reason": "blurry"}, headers=mh)
    assert r.json()["verification"]["status"] == "rejected"
    assert notifier.calls == [(uid, False, "blurry")]

    prof = (await client.get(f"{API}/worker/profile", headers=h)).json()
    assert prof["verification"]["rejection_reason"] == "blurry"
    # qayta yuklab, qayta yuboradi
    r = await client.post(f"{API}/worker/files", headers=h, data={"kind": "selfie"}, files={"file": ("a", JPEG)})
    assert r.status_code == 201
    r = await client.post(f"{API}/worker/verification", json=doc, headers=h)
    assert r.json()["verification"]["status"] == "pending"
    assert r.json()["verification"]["rejection_reason"] is None


async def test_duplicate_document_flagged(client, worker, catalog, moderator):
    cats, districts = catalog
    doc = {"doc_type": "id_card", "doc_number": "AB7654321"}
    first, h1 = await worker("+998901000001")
    await complete_worker(client, h1, cats, districts)
    await client.post(f"{API}/worker/verification", json=doc, headers=h1)

    second, h2 = await worker("+998901000002")
    await complete_worker(client, h2, cats, districts)
    await client.post(f"{API}/worker/verification", json=doc, headers=h2)

    _, mh = moderator
    q = {i["user_id"]: i for i in (await client.get(f"{API}/admin/verifications", headers=mh)).json()}
    assert q[first]["duplicate_of_user_id"] is None
    assert q[second]["duplicate_of_user_id"] == first


async def test_super_admin_can_moderate(client, login, db):
    body, h = await login("+998908888888")
    db.add(UserRole(user_id=body["user"]["id"], role="super_admin"))
    await db.commit()
    assert (await client.get(f"{API}/admin/verifications", headers=h)).status_code == 200
    user = await db.get(User, body["user"]["id"])
    assert user is not None
