# Runbook: zaxira nusxa, PITR va tiklash sinovi

**Maqsad:** PostgreSQL zaxira nusxasi (WAL arxivi + kunlik bazaviy backup), boshqa provayderdagi nusxa, PITR tiklash va har chorakdagi staging tiklash sinovini bosqichma-bosqich bajarish.
**Kim uchun:** DevOps (yoki shu vazifani bajaradigan rol), asoschi (⛔ tashqi qadamlar).
**Bog'liq fayllar:** `spec/kod-uchun/15-xavfsizlik-va-audit.md` §7, §10; `23-backend-arxitekturasi.md` §7, §8, §9; `25-nofunksional-talablar.md` §5; `01-qarorlar.md` #51, #65; `backend/ops/backup/*`; `.sops.yaml`.
**Holat:** joriy, 2026-10-17.

> **Belgilar.** ⛔ **tashqi** — repozitoriy/kod bilan bajarib bo'lmaydigan, faqat asoschi (hisob egasi) bajaradigan qadam. Bajarilmaguncha zaxira tizimi **ishlamaydi** deb hisoblanadi.

---

## 0. Talablar (qisqa)

| Talab | Qiymat | Manba |
|---|---|---|
| RPO | ≤ 5 daqiqa (WAL PITR) | qaror #51, 15 §7.1 |
| RTO | ≤ 4 soat (to'liq restore + tekshirish) | qaror #51, 15 §7.1 |
| Bazaviy backup | kuniga 1 marta, to'liq | 15 §7.1 |
| Operatsion saqlash | 30 kun (sozlanadi) | 15 §7.1 |
| Arxiv saqlash | ≥ 5 yil (O'RQ-404, 29-modda) | qaror #51, 15 §7.1 |
| Boshqa provayderda nusxa | kamida bitta, UzCloud'dan tashqarida | qaror #65 |
| Shifrlash | backup arxivi tinch holatda shifrlangan | 15 §8 |
| Tiklash sinovi | har chorakda staging'da, natija `docs/ops/restore-log.md` | qaror #51, 15 §7.2 |
| PITR | DBaaS PITR'ga tayanilmaydi — o'z WAL arxivi | qaror #65 |

---

## 1. Arxitektura va vosita tanlovi

```
UzCloud DBaaS (PostgreSQL 16, primary)
   │  replikatsiya protokoli (rol: erp_backup, REPLICATION)
   ▼
Backup VM (UzCloud, Ops VM bilan birga bo'lishi mumkin)
   ├─ erp-wal-receive.service ── wal-g wal-receive ──► UzCloud S3 Cold: s3://<bucket>/<env>/wal_005/
   ├─ cron 21:00 UTC ─────────── wal-g backup-push ──► UzCloud S3 Cold: s3://<bucket>/<env>/basebackups_005/
   ├─ cron */4 daq ───────────── pg_switch_wal()  (sokin bazada ham RPO ≤ 5 daq)
   ├─ cron har daqiqa ────────── wal-lag-metric.sh ─► node_exporter textfile → Prometheus alert
   └─ cron 23:00 UTC ─────────── rclone copy ───────► Ikkinchi provayder (S3-mos bucket, object lock)
```

**Nega WAL-G (pgBackRest emas).** Spec ikkalasiga ruxsat beradi (15 §7.1, 23 §9: "pgBackRest yoki WAL-G"). Baza — **UzCloud DBaaS** (managed), unda server shell'i va `archive_command`ni o'zgartirish imkoni kafolatlanmagan. pgBackRest bazaviy backup va WAL arxivi uchun Postgres serverining o'zida (yoki SSH/TLS orqali unga ulangan agentda) ishlashni talab qiladi. WAL-G esa tashqi VM'dan **replikatsiya protokoli** orqali ishlaydi: `wal-g backup-push` ma'lumotlar katalogisiz chaqirilsa — masofaviy `BASE_BACKUP`, `wal-g wal-receive` — WAL oqimini fizik slot orqali qabul qilib S3'ga yuklaydi. Shu sababli DBaaS bilan ham, keyinchalik o'z VM'imizdagi Postgres bilan ham bir xil skriptlar ishlaydi.

**Shifrlash.** 15 §7.1/§8 dagi "pgBackRest shifrlashi" talabi WAL-G'da **libsodium** mijoz tomoni shifrlashi bilan bajariladi (`WALG_LIBSODIUM_KEY`, 32 bayt, hex): S3'ga (UzCloud ham, ikkinchi provayder ham) faqat shifrlangan obyektlar tushadi. Kalit — sir, SOPS/age bilan saqlanadi (§3); kalit yo'qolsa backup'lar o'qib bo'lmaydi → asoschi offline nusxasi majburiy (§2, 4-qadam). *Izoh:* 15 §7.1 va §8 matnidagi "pgBackRest shifrlashi" iborasi vosita nomini emas, talabni bildiradi deb qabul qilindi; spec egasi matnni "backup vositasining mijoz tomoni shifrlashi" deb umumlashtirishi tavsiya etiladi.

**Muqobil yo'l (B).** Agar UzCloud DBaaS `REPLICATION` huquqli rol bermasa (⛔ §2, 2-qadam), Postgres o'z VM'imizda ko'tariladi va WAL `archive_command = 'wal-g wal-push %p'` + `archive_timeout = 60` bilan yuboriladi; `wal-receive.sh`/`wal-switch.sh` kerak bo'lmaydi, qolgan skriptlar o'zgarishsiz.

---

## 2. ⛔ Tashqi qadamlar (faqat asoschi)

| # | Qadam | Nega | Tekshirish |
|---|---|---|---|
| 1 | ⛔ **tashqi** — UzCloud hisobi: **avto-to'lov yoki oldindan to'lov** yoqish; billing ogohlantirishini (hisob-faktura 5-sanada, muddat +10 kun) Telegram/email'ga ulash | Oferta 4.4: to'lov kechiksa server o'chiriladi, "Suspended"dan 20 kun o'tib ma'lumot qaytarib bo'lmaydigan tarzda o'chiriladi (qaror #65) | UzCloud kabinetida avto-to'lov "yoqilgan"; sinov ogohlantirishi kelgan |
| 2 | ⛔ **tashqi** — UzCloud DBaaS'dan so'rash: (a) `REPLICATION` huquqli rol (`erp_backup`) va fizik replikatsiya slotiga ruxsat; (b) `GRANT EXECUTE ON FUNCTION pg_switch_wal() TO erp_backup`; (c) DBaaS disk shifrlashi bayonoti; (d) PITR/HA yozma kafolati (bo'lsa ham, unga tayanmaymiz) | §1 — WAL-G masofaviy rejimi; 15 §8 shifrlash qatori | `psql "replication=database" -c "IDENTIFY_SYSTEM"` backup VM'dan ishlaydi |
| 3 | ⛔ **tashqi** — UzCloud S3 **Cold** bucket (`erp-pg-backup`), alohida kirish kalitlari: backup VM uchun **yozish**, staging tiklash uchun **faqat o'qish** | 15 §7.1; staging prod arxivini buzib qo'ymasligi kerak | `rclone lsd uzcloud:` ikkala kalit bilan; o'qish kaliti bilan yozish rad etiladi |
| 4 | ⛔ **tashqi** — **age kalitlari**: `age-keygen` bilan (a) prod deploy, (b) staging deploy, (c) backup-prod, (d) backup-staging, (e) asoschining **break-glass** kaliti. (e) ning maxfiy qismi — faqat offline (qog'oz/shifrlangan USB, seyf), UzCloud'dan tashqarida; ochiq kalitlar `.sops.yaml`dagi `PLACEHOLDER` o'rniga yoziladi | qaror #65: master kalit UzCloud'dan tashqarida | `sops --decrypt deploy/secrets/prod.enc.yaml` break-glass kaliti bilan ochiladi |
| 5 | ⛔ **tashqi** — `WALG_LIBSODIUM_KEY` (`openssl rand -hex 32`) yaratish, `deploy/secrets/backup-*.enc.env`ga SOPS bilan yozish **va** asoschi offline nusxasini saqlash | Kalitsiz backup — foydasiz shifrlangan baytlar | Staging tiklash sinovi (§6) shu kalit bilan o'tadi |
| 6 | ⛔ **tashqi** — **ikkinchi provayder**da S3-mos bucket (boshqa mahalliy DC yoki sovuq arxiv): versiyalash + **object lock / retention ≥ 5 yil**, faqat yozish (delete'siz) kalit; to'lovi ham avto-to'lov | qaror #65 — UzCloud hisobi yo'qolsa ham nusxa qoladi | `rclone lsd offsite:`; obyektni o'chirishga urinish rad etiladi |
| 7 | ⛔ **tashqi** — UzCloud status sahifasi (`uzcloud.uz/status`) obunasi | 23 §8 ops ogohlantirishlari | — |

---

## 3. Sirlar: SOPS + age

- Fayllar (repoda, shifrlangan): `deploy/secrets/prod.enc.yaml`, `deploy/secrets/staging.enc.yaml` (ilova `ERP_*` sozlamalari — nomlar `backend/.env.example`da), `deploy/secrets/backup-prod.enc.env`, `deploy/secrets/backup-staging.enc.env` (backup VM). Qoidalar — repo ildizidagi `.sops.yaml`.
- Har fayl ikki qabul qiluvchiga shifrlanadi: muhit deploy kaliti + asoschi break-glass kaliti.
- Deploy paytida: `sops --decrypt deploy/secrets/backup-prod.enc.env > /etc/erp-backup/env` (egasi `erp-backup`, `chmod 600`); repozitoriyga ochiq matn **hech qachon** tushmaydi (CI'da gitleaks).
- `backup-<env>.enc.env` dagi nomlar (qiymatlar faqat shifrlangan faylda):

| O'zgaruvchi | Ma'nosi |
|---|---|
| `WALG_S3_PREFIX` | `s3://erp-pg-backup/prod` (staging: `.../staging`) |
| `AWS_ENDPOINT`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | UzCloud S3 (backup VM — yozish kaliti) |
| `WALG_LIBSODIUM_KEY` | 64 hex belgi (32 bayt) |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGSSLMODE` | DBaaS, rol `erp_backup` |
| `WALG_SLOTNAME` | fizik slot, standart `walg_erp` |
| `BACKUP_RETAIN_FULL` | operatsion saqlash, standart 30 |
| `OFFSITE_SRC`, `OFFSITE_DST`, `RCLONE_CONFIG_UZCLOUD_*`, `RCLONE_CONFIG_OFFSITE_*` | off-provider nusxa (rclone env-konfiguratsiyasi) |
| `WAL_LIST_REMOTE`, `TEXTFILE_DIR` | WAL kechikish metrikasi |

**Kalit rotatsiyasi:** yangi age kaliti → `.sops.yaml`da recipient almashtiriladi → `sops updatekeys deploy/secrets/<fayl>` → deploy → eski maxfiy kalit yo'q qilinadi. `WALG_LIBSODIUM_KEY` almashtirilsa eski kalit **eski backup'lar saqlanadigan muddat (5 yil) davomida** saqlanadi.

---

## 4. Jadval va saqlash

| Ish | Qachon (Toshkent) | Skript | Natija |
|---|---|---|---|
| WAL oqimi | doimiy | `wal-receive.sh` (`erp-wal-receive.service`) | `wal_005/` |
| WAL segmentini yopish | har 4 daqiqa | `wal-switch.sh` | sokin bazada ham RPO ≤ 5 daq |
| WAL kechikish metrikasi | har daqiqa | `wal-lag-metric.sh` | `erp_wal_archive_lag_seconds` |
| To'liq bazaviy backup | har kuni 02:00 | `base-backup.sh` | `basebackups_005/` |
| Oylik arxiv belgisi | har oyning 1-kuni (02:00 backup) | `base-backup.sh` (`wal-g backup-mark`) | permanent backup ≥ 5 yil |
| Operatsion retention | har kuni, backup'dan keyin | `base-backup.sh` (`delete retain FULL 30`) | 30 kun; permanent'lar daxlsiz |
| Off-provider nusxa | har kuni 04:00 | `offsite-copy.sh` | ikkinchi provayder (copy, delete'siz) |
| Tiklash sinovi | har chorak (yan/apr/iyul/okt 2-haftasi) | `staging-restore.sh` | `docs/ops/restore-log.md` qatori |
| 5 yildan eski arxivni olib tashlash | yiliga 1 marta, qo'lda | `wal-g backup-mark -i <name>` → `wal-g delete retain ...` | buxgalter tasdig'i bilan |

Cron fayli: `backend/ops/backup/erp-backup.cron` (UTC vaqtlarida).

---

## 5. Backup VM o'rnatish

1. Paketlar: `postgresql-client-16`, `wal-g` (≥ 3.0, masofaviy `backup-push` va `wal-receive` bilan), `rclone`, `sops`, `age`, `prometheus-node-exporter` (textfile collector yoqilgan).
2. Foydalanuvchi: `useradd --system erp-backup`; `/var/log/erp-backup`, `/etc/erp-backup` (egasi `erp-backup`, `chmod 700`).
3. Kod: repozitoriy `/opt/erp`ga; `chmod +x /opt/erp/backend/ops/backup/*.sh`.
4. Sirlar: §3 bo'yicha `/etc/erp-backup/env`.
5. Slot va ulanish tekshiruvi: `ERP_BACKUP_ENV_FILE=/etc/erp-backup/env /opt/erp/backend/ops/backup/wal-switch.sh` — xatosiz tugashi kerak.
6. `cp backend/ops/backup/erp-wal-receive.service /etc/systemd/system/ && systemctl enable --now erp-wal-receive`.
7. `cp backend/ops/backup/erp-backup.cron /etc/cron.d/erp-backup`.
8. Birinchi bazaviy backup'ni qo'lda: `sudo -u erp-backup env ERP_BACKUP_ENV_FILE=/etc/erp-backup/env /opt/erp/backend/ops/backup/base-backup.sh`; `wal-g backup-list`da ko'rinadi.
9. Darhol §6 bo'yicha staging tiklash sinovini o'tkazing — sinovdan o'tmagan backup backup hisoblanmaydi.

**Monitoring (25 §5):** Grafana alert — `erp_wal_archive_lag_seconds > 300` yoki `< 0` (5 daqiqa davomida), `time() - erp_wal_archive_lag_checked_timestamp_seconds > 300` (skript ishlamay qoldi), `erp-wal-receive` servisi `failed`, `base-backup.log`da 26 soatdan beri "backup tayyor" yo'q. Kanal — Telegram (platforma admin).

---

## 6. Har chorakdagi staging tiklash sinovi (qaror #51, 15 §7.2)

Mas'ul — DevOps. Natija (sana, muvaffaqiyatli/yo'q, o'lchangan vaqt) `docs/ops/restore-log.md`ga yoziladi.

1. **Tayyorgarlik.** Staging hostida PostgreSQL 16 binarlari va `wal-g`; prod arxivi uchun **faqat o'qish** S3 kaliti (⛔ §2, 3-qadam) bilan env fayl: `WALG_S3_PREFIX=s3://erp-pg-backup/prod`, `WALG_LIBSODIUM_KEY` (prod), `PGDATA_RESTORE=/srv/restore/$(date +%Y%m%d)` (bo'sh), `RESTORE_PORT=5433`, `RESTORE_OPERATOR=<ism>`, `RESTORE_LOG=/opt/erp/docs/ops/restore-log.md`.
2. **Maqsad vaqtini tanlash.** Sinov — oxirgi 24 soat ichidagi ixtiyoriy nuqta, masalan `RECOVERY_TARGET_TIME="2026-10-17 10:30:00+05"`. Bo'sh qoldirilsa — arxivdagi oxirgi WAL'gacha.
3. **Ishga tushirish.** `ERP_BACKUP_ENV_FILE=<env> /opt/erp/backend/ops/backup/staging-restore.sh` — skript `pitr-restore.sh`ni chaqiradi (backup-fetch → recovery sozlamalari → `pg_ctl start` → promote kutish), keyin `verify-restore.sql`ni ishga tushiradi va vaqtni o'lchaydi.
4. **Tekshiruv natijalari** (`verify-restore.sql`, superuser sifatida):
   - klaster recovery holatidan chiqqan (`pg_is_in_recovery() = false`);
   - `public.alembic_version` — joriy reliz `alembic heads` bilan bir xil;
   - `app.tenants` bo'sh emas; `tenants/users/products/sales/stock_lots/ledger_entries/audit_log` qatorlar soni prod hisobotidagi kattaliklar bilan solishtiriladi;
   - **yangilik:** `audit_log`/`ledger_entries`/`sales` dagi eng so'nggi `created_at` maqsad vaqtiga ≤ 5 daqiqa yaqin (RPO) — farq jurnalga yoziladi;
   - storno juftliklari mos (summa teng, Dt/Kt almashgan; 13 §5.2);
   - `amcheck` — `app`/`auth`/`platform` sxemalaridagi barcha B-tree indekslar butun.
   Qo'shimcha qo'lda tekshiruv: tiklangan bazaga staging API'ni ulab `/health/ready` = 200 va bitta tenant hisobotini ochish.
5. **Jurnal.** Skript chiqargan qator `docs/ops/restore-log.md`ga qo'shiladi (format: `| sana | backup | maqsad vaqt | davomiylik | natija | bajaruvchi | izoh |`) va commit qilinadi.
6. **Yakun.** `pg_ctl -D "$PGDATA_RESTORE" stop`, katalog o'chiriladi (prod ma'lumoti stagingda qolmaydi).
7. **Eskalatsiya.** Natija "muvaffaqiyatsiz" yoki o'lchangan vaqt > 4 soat → **insident** (15 §10): sabab, tuzatish, takroriy sinov 2 hafta ichida.

---

## 7. Prod PITR tiklash (insident)

Holat: ma'lumot buzildi/yo'qoldi (masalan, xato migratsiya yoki tasodifiy `DELETE`) yoki DBaaS instansi yo'qoldi.

1. **To'xtatish.** Yozuvlarni to'xtating: `api`, `worker`, `scheduler` konteynerlari to'xtatiladi (POS offline rejimda ishlashda davom etadi, cheklar navbatda qoladi — 16). Insident ochiladi (15 §10), vaqt belgilanadi.
2. **Maqsad vaqtini aniqlash.** Buzilish boshlangan vaqtdan **oldingi** nuqta (`audit_log`, ilova loglari — Loki). Masalan `RECOVERY_TARGET_TIME="2026-10-17 14:02:00+05"`.
3. **Bazaviy backup'ni tanlash.** `wal-g backup-list` — maqsad vaqtdan oldin tugagan eng so'nggi backup → `RESTORE_BACKUP=<name>` (yoki `LATEST`, agar u maqsaddan oldin bo'lsa).
4. **Tiklash.** Yangi hostda (yoki yangi DBaaS instansiga yuklash uchun oraliq VM'da): `ERP_BACKUP_ENV_FILE=<env> PGDATA_RESTORE=/srv/pitr RESTORE_BACKUP=<name> RECOVERY_TARGET_TIME="<vaqt>" /opt/erp/backend/ops/backup/pitr-restore.sh`. Skript `archive_mode=off` qo'yadi — tiklangan klaster prod arxiviga yozmaydi.
5. **Tekshirish.** `psql -X -v ON_ERROR_STOP=1 -h localhost -p 5433 -d erp -f backend/ops/backup/verify-restore.sql` + buzilgan ma'lumot haqiqatan tiklanganini qo'lda tekshirish.
6. **Ko'chirish.** Variant A (tez): tiklangan klasterni yangi primary qilish va `ERP_DATABASE_URL`/`ERP_MIGRATOR_DATABASE_URL`ni unga yo'naltirish (SOPS faylini yangilab deploy). Variant B (DBaaS'ga qaytish): `pg_dump -Fc` → yangi DBaaS instansiga `pg_restore`, keyin `initdb.sh` rollari va RLS grant'lari tekshiriladi.
7. **Qayta ishga tushirish.** `migrate` konteyneri (`alembic upgrade head` — kerak bo'lsa) → `api`/`worker`/`scheduler`. POS navbatidagi cheklar sinxronlanadi (idempotent, 16).
8. **Arxivni qayta ulash.** Yangi primary uchun `wal-receive` sloti yaratiladi (`WALG_SLOTNAME` yangi nom), darhol `base-backup.sh` qo'lda ishga tushiriladi — yangi timeline uchun birinchi bazaviy backup.
9. **Yakun.** Vaqtlar (aniqlash → tiklash → ishga tushish) insident hisobotiga; RTO > 4 soat bo'lsa sabab tahlili.

**UzCloud hisobi/bucket yo'qolgan holat:** 3-qadamdan oldin `rclone copy offsite:<bucket>/<env> <yangi-s3>:<bucket>/<env>` bilan nusxani tiklanadigan joyga ko'chiring va `WALG_S3_PREFIX`/`AWS_*`ni o'sha joyga yo'naltiring; qolgan qadamlar o'zgarmaydi (obyektlar o'sha `WALG_LIBSODIUM_KEY` bilan shifrlangan).

---

## 8. Fayllar

| Fayl | Vazifa |
|---|---|
| `backend/ops/backup/lib.sh` | umumiy yordamchilar: env fayl, `require_env`, WAL-G/libpq preflight |
| `backend/ops/backup/wal-receive.sh` | doimiy WAL oqimi (RPO) |
| `backend/ops/backup/wal-switch.sh` | WAL segmentini yopish (sokin baza) |
| `backend/ops/backup/base-backup.sh` | kunlik to'liq backup, oylik permanent belgi, retention |
| `backend/ops/backup/offsite-copy.sh` | boshqa provayderga nusxa (`rclone copy` + `check`) |
| `backend/ops/backup/pitr-restore.sh` | PITR tiklash bo'sh katalogga |
| `backend/ops/backup/staging-restore.sh` | chorak sinovi: tiklash + tekshiruv + jurnal qatori |
| `backend/ops/backup/verify-restore.sql` | tiklashdan keyingi tekshiruv so'rovlari |
| `backend/ops/backup/wal-lag-metric.sh` | `erp_wal_archive_lag_seconds` (Prometheus alert) |
| `backend/ops/backup/erp-backup.cron` | jadval (`/etc/cron.d`) |
| `backend/ops/backup/erp-wal-receive.service` | systemd servis |
| `.sops.yaml` | SOPS/age qoidalari (recipient'lar — ⛔ placeholder) |

Barcha skriptlar `set -euo pipefail`, faqat muhit o'zgaruvchilaridan o'qiydi, sir saqlamaydi; CI'da `shellcheck` (backend.yml, quality).
