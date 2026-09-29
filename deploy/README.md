# Serverga joylash (Faza 1-lite)

Bitta server: PostgreSQL + Redis + API (bot va scheduler shu jarayonda) + web ilova + HTTPS (Caddy) + kunlik zaxira.
Hammasi `deploy/docker-compose.yml` da.

## Talablar

- Ubuntu 22.04/24.04, kamida 2 vCPU, 4 GB RAM, 40 GB disk
- Domen (masalan `app.workly.uz`): **A yozuvi** server IP'siga
- Ochiq portlar: 22 (SSH), 80, 443 (TCP va UDP)

## 1. Serverni tayyorlash

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # qayta kiring
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
git clone https://github.com/MuhammadqodirZokirov/Workly.git && cd Workly
```

## 2. `.env`

```bash
cp .env.example .env
```

Majburiy (prod'da namuna qiymatlar bilan API **ishga tushmaydi** — xato ro'yxatini chiqaradi):

| O'zgaruvchi | Qiymat |
|---|---|
| `ENV` | `prod` |
| `DOMAIN`, `ACME_EMAIL` | domen va Let's Encrypt uchun e-mail |
| `WEBAPP_URL`, `PUBLIC_BASE_URL` | `https://<DOMAIN>` (web, API va webhook bitta domenda) |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `DATA_ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATA_HASH_KEY` | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` |
| `BOT_TOKEN`, `BOT_MODE=webhook`, `BOT_WEBHOOK_SECRET` | asosiy bot; secret — `openssl rand -hex 16` |
| `ADMIN_BOT_TOKEN` | admin bot (ixtiyoriy) |
| `SMS_PROVIDER=eskiz`, `ESKIZ_EMAIL`, `ESKIZ_PASSWORD`, `ESKIZ_FROM` | SMS |
| `VITE_BOT_URL` | `https://t.me/<bot_username>` |
| `DATABASE_URL`, `REDIS_URL`, `MEDIA_DIR`, `CORS_ORIGINS` | compose o'zi beradi — o'chirib qo'ying yoki tegmang |

> **`DATA_ENCRYPTION_KEY` ni serverdan tashqarida xavfsiz saqlang** (parol menejeri). Yo'qolsa, hujjat va selfie fayllarini ochib bo'lmaydi — zaxira ham yordam bermaydi.

## 3. Ishga tushirish

```bash
docker compose -f deploy/docker-compose.yml --env-file .env up -d --build
docker compose -f deploy/docker-compose.yml ps          # hammasi Up, api — healthy
curl https://<DOMAIN>/health                             # {"status":"ok","db":"ok","redis":"ok"}
```

API ishga tushganda migratsiyalar (`alembic upgrade head`) va boshlang'ich katalog avtomatik qo'llanadi.
Caddy birinchi so'rovda Let's Encrypt sertifikatini oladi (DNS server IP'siga ko'rsatishi shart).

## 4. Birinchi admin

1. Telefoningizdan asosiy botga `/start` → telefonni ulashing (yoki web ilovaga SMS bilan kiring)
2. Serverda:
   ```bash
   docker compose -f deploy/docker-compose.yml exec api python -m workly.cli grant-role --phone +998XXXXXXXXX --role super_admin
   docker compose -f deploy/docker-compose.yml exec api python -m workly.cli totp-setup --phone +998XXXXXXXXX
   ```
   URI'ni Google Authenticator / Authy'ga qo'shing → `https://<DOMAIN>/admin`

## 5. BotFather

- Asosiy bot: **Bot Settings → Menu Button → Configure** → URL `https://<DOMAIN>`, matn "Workly"
- **Bot Settings → Configure Mini App** → shu URL (Telegram ichida ochiladi)
- `/setdomain` → `<DOMAIN>` (Telegram Login uchun)
- Admin bot uchun menyu shart emas — `/start` yetarli

## Zaxira nusxa

`backup` servisi har kuni 03:00 (Toshkent) da baza (`pg_dump`) va shifrlangan media'ni `backups` volume'ga yozadi, `BACKUP_KEEP_DAYS` (14) kundan eskilarini o'chiradi.

```bash
docker compose -f deploy/docker-compose.yml exec backup sh /backup.sh once   # hozir olish
docker compose -f deploy/docker-compose.yml exec backup ls -lh /backups
docker compose -f deploy/docker-compose.yml cp backup:/backups ./backups-copy  # serverdan tashqariga
```

Server buzilsa zaxira ham yo'qoladi — **haftasiga kamida bir marta nusxani boshqa joyga ko'chiring** (boshqa server, S3, shaxsiy kompyuter).

### Zaxiradan tiklash

```bash
C="docker compose -f deploy/docker-compose.yml"
$C stop api
$C exec backup sh -c 'dropdb --if-exists workly && createdb workly && pg_restore -d workly --no-owner /backups/db_YYYY-MM-DD_HHMM.dump'
$C run --rm -v "$(pwd)/backups-copy:/restore" --entrypoint sh api -c 'tar -xzf /restore/media_YYYY-MM-DD_HHMM.tar.gz -C /data/media'
$C start api
```

## Yangilash

```bash
git pull
docker compose -f deploy/docker-compose.yml --env-file .env up -d --build
```

Migratsiyalar API ishga tushganda qo'llanadi. Yangilashdan oldin `sh /backup.sh once` qiling.

## Monitoring

- `https://<DOMAIN>/health` — baza va Redis tekshiruvi (xato bo'lsa 503). UptimeRobot yoki shunga o'xshash xizmatga 5 daqiqalik tekshiruv qo'ying
- Loglar: `docker compose -f deploy/docker-compose.yml logs -f api`
- Admin signallari (T+30, nizolar, verifikatsiya) — admin botga keladi
