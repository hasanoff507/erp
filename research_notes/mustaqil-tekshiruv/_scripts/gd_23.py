p = r'E:/Project/erp/spec/kod-uchun/23-backend-arxitekturasi.md'
s = open(p, encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new)


SRC = "`22-ai-qatlami.md` §1 (AI porti rejimlari `fake`/`cli`/`api`; qaror #16)"

# T-178
rep("6. **AI — port naqshi** (`AiProvider`, README qarori):",
    "6. **AI — port naqshi** (`AiProvider`, " + SRC + "):")
rep("| README qarori: Claude API (Haiku 5.5), `AiProvider` porti — `fake`/`cli` (dev) / `api` (prod) |",
    "| Claude API (Haiku 5.5), `AiProvider` porti — `fake`/`cli` (dev) / `api` (prod) — " + SRC + " |")
rep("""raise ValueError("prod'da AI rejimi 'api' bo'lishi shart (README qarori)")""",
    """raise ValueError("prod'da AI rejimi 'api' bo'lishi shart (22-ai-qatlami.md §1, qaror #16)")""")

# T-125
rep("va **har bir yozilgan registr qatoriga teskari belgili nusxa** qo'shiladi (`doc_type`/`doc_id` — original hujjat, `reversal_of_id` — teskari qilinayotgan asl registr qatori; hech qachon `UPDATE`).",
    "va **har bir yozilgan registr qatoriga teskari qator** qo'shiladi: `ledger_entries` — Dt/Kt o'rni almashtiriladi, `amount` musbat; `stock_moves`/`debt_moves`/`cash_moves`/`vat_moves` — teskari ishora (`13-provodka-qoidalari.md` §5.2). `doc_type`/`doc_id` — original hujjat, `reversal_of_id` — teskari qilinayotgan asl registr qatori, sana — joriy ochiq davr; hech qachon `UPDATE`.")

# T-131
rep("job shu sanadan keyingi barcha chiqim postinglarini **FIFO/AVECO bo'yicha qayta hisoblaydi** va `ledger_entries`/`stock_moves`ga **tuzatish yozuvi** qo'shadi (asl yozuvni o'zgartirmaydi — append-only tamoyili shu yerda ham amal qiladi). `period_closings`ga tegadigan sana bo'lsa, job **rad etiladi** va `notifications` moduliga ogohlantirish yuboradi (`11-malumotlar-modeli.md`, 7-bo'lim). Job `queued → running → done/failed`; davr yopiq bo'lsa `rejected_period_closed`.",
    "job shu sanadan keyingi barcha chiqimlarni `ORDER BY moved_at, created_at, id` tartibida **FIFO/AVECO bo'yicha qayta hisoblaydi**; tegishli `ledger_entries` (9120/inv_acct) uchun eski qator storno (`reversal_of_id`) + yangi qator yoziladi (asl yozuv o'zgartirilmaydi — append-only): `doc_type`/`doc_id` = asl chiqim hujjati, `analytics.recost_job_id`, `entry_date` = asl sana (davr ochiq bo'lsa). Yopilgan davrga tegsa — yopilgan davr yozuvlari o'zgarmaydi, farq joriy ochiq davrda tuzatuvchi yozuv bilan (`analytics.correction_of_period`) (`13-provodka-qoidalari.md` §3.3, §3.4). Job `queued → running → done/failed`.")

# T-182
rep("butun qoralamani almashtiradi (13-0 §8) |", "butun qoralamani almashtiradi (`17-api-umumiy.md` §8) |")

# T-121
rep("`/billing/export-my-data` (SMS OTP bilan, D2)",
    "`/billing/export-my-data` (OTP bilan — Telegram birinchi, SMS zaxira, qaror #34; D2)")

# T-022, T-271
rep("""Agent ro'yxati, ulash, token va vazifa navbati — `onec_integration` modulidagi mavjud mexanizm (`33-1c-integratsiya.md` §9: `onec_agent_tasks`, lease, heartbeat, Ed25519 imzosi, Redis pub/sub uyg'otish).""",
    """Agent ro'yxati, ulash, token va vazifa navbati — Bosqich 5 da quriladigan umumiy mexanizm (qaror #66; jadvallar `onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations`, migratsiya `0028 store_agent`; protokol — `33-1c-integratsiya.md` §9: lease, heartbeat, Ed25519 imzosi, Redis pub/sub uyg'otish); `AgentTaskPort.enqueue` agent `capabilities` ni tekshiradi (`409 AGENT_CAPABILITY_DISABLED`).""")
rep("""| `kind` | Kim qo'yadi | Trigger | Natija qayerga |
|---|---|---|---|
| `fiscal.status` | `integrations/fiscal` | har 5 daqiqa (agent onlayn bo'lsa) | `cash_registers.fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at` |
| `fiscal.resend_unsent` | `integrations/fiscal` | `fiscal_unacked_monitor` 40 soat bosqichi; BO-14 "Qayta yuborish" | `ResendResult` → BO-14 |
| `fiscal.zreport` | `sales` (smena yopish) | smena POS'siz yopilganda | `fiscal_receipts(kind='z_report')` |
| `print.raw` | `notifications`/`reports` | back-office'dan LAN printerga chop etish | holat (yuborildi / printer xatosi) |
| `scale.plu_upload` | `catalog` | narx/tovar o'zgargach yoki qo'lda | yuklangan qatorlar soni / xato |""",
    """| `kind` | Kim qo'yadi | Trigger | Payload | Natija qayerga |
|---|---|---|---|---|
| `fiscal.status` | `integrations/fiscal` | har 5 daqiqa (agent onlayn bo'lsa) | `{cash_register_id}` | `cash_registers.*` (`fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at`; payload `cash_register_id` bo'yicha) va `acked[]` → `fiscal_receipts.ofd_acked_at` |
| `fiscal.resend_unsent` | `integrations/fiscal` | `fiscal_unacked_monitor` 40 soat bosqichi; BO-14 "Qayta yuborish" | `{cash_register_id}` | `ResendResult` → BO-14 |
| `fiscal.zreport` | `sales` (smena yopish) | smena POS'siz yopilganda | `{cash_register_id, shift_id}` | `ZReport` → `fiscal_receipts(kind='z_report')` yoziladi |
| `print.raw` | `notifications`/`reports` | back-office'dan LAN printerga chop etish | `{printer_local_id, data_base64, encoding: "cp866"\\|"raster"}` | holat (yuborildi / printer xatosi) |
| `scale.plu_upload` | `catalog` | narx/tovar o'zgargach yoki qo'lda — MVP'dan keyin | `{scale_local_id, items:[{plu, name, price, barcode_prefix}]}` | yuklangan qatorlar soni / xato |""")

# T-199
rep("postgres:   # postgres:17-alpine, host portga chiqarilgan", "postgres:   # postgres:16-alpine, host portga chiqarilgan")

# T-086
rep("- **Xarajat toifalari** (`expense_categories`): Ijara, Kommunal, Ish haqi, Transport, Soliq va yig'imlar, Ta'mirlash, Boshqa (M15, US-M15-01 — standart ro'yxat, tenant o'zgartira oladi).",
    "- **Xarajat toifalari** (`expense_categories`): standart ro'yxat — `13-provodka-qoidalari.md` §2.17 seed xaritasi (21 kod), tenant o'zgartira oladi (M15, US-M15-01).")

open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
