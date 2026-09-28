import pytest

from .conftest import complete_worker
from .test_worker import JPEG

API = "/api/v1"


@pytest.fixture
async def verified_worker(client, worker, catalog, moderator):
    cats, districts = catalog
    uid, h = await worker()
    await complete_worker(client, h, cats, districts)
    await client.post(f"{API}/worker/verification", json={"doc_type": "id_card", "doc_number": "AA1234567"}, headers=h)
    _, mh = moderator
    await client.post(f"{API}/admin/verifications/{uid}/approve", json={}, headers=mh)
    return uid, h


@pytest.fixture
async def employer_headers(client, login, redis):
    await redis.delete("otp:cooldown:+998977777777")
    _, h = await login("+998977777777")
    await client.post(f"{API}/me/roles", json={"role": "employer"}, headers=h)
    return h


async def test_resume_public_fields_only(client, verified_worker, employer_headers):
    uid, _ = verified_worker
    r = await client.get(f"{API}/workers/{uid}", headers=employer_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_name"] == "Jasur T."
    assert body["is_new"] is True and body["stats"]["reliability"] == 100 and body["stats"]["rating"] is None
    assert body["skills"][0]["experience"] == "3_5" and len(body["district_ids"]) == 2
    assert body["avatar_url"] is None
    # maxfiy ma'lumot yo'q
    text = r.text
    for secret in ("+998901234567", "AA1234567", "1995-05-10", "41.31", "Toshmatov", "emergency"):
        assert secret not in text


async def test_resume_avatar(client, verified_worker, employer_headers):
    uid, h = verified_worker
    # avatar tasdiqlangandan keyin ham yuklanadi
    r = await client.post(f"{API}/worker/files", headers=h, data={"kind": "avatar"}, files={"file": ("a", JPEG)})
    assert r.status_code == 201
    url = (await client.get(f"{API}/workers/{uid}", headers=employer_headers)).json()["avatar_url"]
    r = await client.get(url.replace("http://test", ""))
    assert r.status_code == 200 and r.content == JPEG


async def test_resume_access(client, verified_worker, worker, login, redis):
    uid, wh = verified_worker
    # ishchi boshqa ishchining rezyumesini ko'ra olmaydi (faqat employer/moderator)
    assert (await client.get(f"{API}/workers/{uid}", headers=wh)).status_code == 403
    assert (await client.get(f"{API}/workers/{uid}")).status_code == 401


async def test_unverified_worker_hidden(client, worker, employer_headers):
    uid, _ = await worker("+998901000009")
    r = await client.get(f"{API}/workers/{uid}", headers=employer_headers)
    assert r.status_code == 404 and r.json()["code"] == "WORKER_NOT_FOUND"
