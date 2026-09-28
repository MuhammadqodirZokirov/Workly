API = "/api/v1"


async def test_patch_me(client, login):
    _, h = await login()
    r = await client.patch(f"{API}/me", json={"full_name": "  Jasur Toshmatov ", "lang": "uz_cyrl"}, headers=h)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Jasur Toshmatov" and r.json()["lang"] == "uz_cyrl"


async def test_roles(client, login):
    _, h = await login()
    r = await client.post(f"{API}/me/roles", json={"role": "worker"}, headers=h)
    assert r.json()["roles"] == ["worker"]
    r = await client.post(f"{API}/me/roles", json={"role": "employer"}, headers=h)
    r = await client.post(f"{API}/me/roles", json={"role": "worker"}, headers=h)  # idempotent
    assert r.json()["roles"] == ["employer", "worker"]
    r = await client.post(f"{API}/me/roles", json={"role": "admin"}, headers=h)
    assert r.status_code == 403 and r.json()["code"] == "ROLE_NOT_ALLOWED"


async def test_consents(client, login):
    _, h = await login()
    r = await client.post(
        f"{API}/me/consents",
        headers=h,
        json={"items": [{"doc_type": "terms", "version": "1.0"}, {"doc_type": "privacy", "version": "1.0"}]},
    )
    assert r.status_code == 204
    r = await client.post(f"{API}/me/consents", headers=h, json={"items": [{"doc_type": "x", "version": "1"}]})
    assert r.status_code == 422


async def test_delete_me(client, login):
    body, h = await login()
    assert (await client.delete(f"{API}/me", headers=h)).status_code == 204
    assert (await client.get(f"{API}/me", headers=h)).status_code == 401
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


async def test_catalog(client):
    cats = (await client.get(f"{API}/catalog/categories")).json()
    assert [c["code"] for c in cats] == ["construction", "cargo", "cleaning", "other"]  # qolganlari o'chiq
    construction = cats[0]
    assert construction["name"] == {"uz_latn": "Qurilish", "uz_cyrl": "Қурилиш", "ru": "Строительство"}
    assert len(construction["specializations"]) == 7

    regions = (await client.get(f"{API}/catalog/regions")).json()
    assert [r["code"] for r in regions] == ["tashkent_city"]
    districts = (await client.get(f"{API}/catalog/districts", params={"region_id": regions[0]["id"]})).json()
    assert len(districts) == 12
