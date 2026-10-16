p = r'E:/Project/erp/spec/kod-uchun/21-integratsiyalar.md'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep("""1. **Lokal API (POS ↔ agent)** — `http://127.0.0.1:<port>/v1/*`, faqat loopback interfeysida tinglaydi (port agent sozlamasida, POS-16 «Uskunalar sozlamasi»da ko'rsatiladi). Kim ishlatadi: veb-kassa — sotuv paytidagi fiskal chek va xom printerga chop etish; internetsiz ham ishlaydi (offline savdoning asosiy sharti). Yo'llar:""",
    """1. **Lokal API (POS ↔ agent)** — `http://127.0.0.1:47110/v1/*` (standart port `47110`, agent sozlamasida o'zgaradi, POS-16 «Uskunalar sozlamasi»da ko'rsatiladi), faqat loopback interfeysida tinglaydi. Kim ishlatadi: veb-kassa — sotuv paytidagi fiskal chek va xom printerga chop etish; internetsiz ham ishlaydi (offline savdoning asosiy sharti). Yo'llar (so'rov/javob sxemalari, xato shakli va HTTP kodlari — §16.1):""")

rep("""2. **Bulut kanali (agent ↔ server)** — `33-1c-integratsiya.md` §9 dagi **bir xil** identifikatsiya va protokol: OAuth mijozi `onec-agent` (RFC 8628 device grant bilan ulash, keyin `client_credentials` + `private_key_jwt`, access token 10 daqiqa), yo'llar `/api/v1/onec-agent/*` (long-poll pull, Ed25519 imzoli vazifalar, lease/heartbeat). Bitta do'kon PK'si — bitta agent yozuvi (`devices.kind='onec_agent'`), imkoniyatlar sozlamada yoqiladi.

**Bulut vazifa turlari — Bosqich 5 kengaytmasi** (`33` §9.5 oq ro'yxatiga qo'shiladi; `base_id = null`, 1C bazasi talab qilinmaydi):

| `kind` | Vazifa | Natija |
|---|---|---|
| `fiscal.status` | FM holati: `fm_state`, yuborilmagan cheklar soni, eng eski yuborilmagan chek vaqti | `cash_registers.fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at` yangilanadi |
| `fiscal.resend_unsent` | Yuborilmagan cheklarni qayta yuborish (40 soatdan keyin server avtomatik qo'yadi, BO-14'da qo'lda ham) | `ResendResult` |
| `fiscal.zreport` | Smena yopilishida Z-hisobotni FM'dan olish (POS yopiq bo'lsa) | `ZReport` |
| `print.raw` | Back-office'dan LAN printerga chop etish (masalan qayta chek nusxasi, kassa hisoboti) | yuborildi / printer xatosi |
| `scale.plu_upload` | PLU ro'yxatini yorliqli taroziga yuklash | yuklangan qatorlar soni / xato |

Bu ro'yxat""",
    """2. **Bulut kanali (agent ↔ server)** — `33-1c-integratsiya.md` §9 dagi **bir xil** identifikatsiya va protokol: OAuth mijozi `onec-agent` (RFC 8628 device grant bilan ulash, keyin `client_credentials` + `private_key_jwt`, access token 10 daqiqa), yo'llar `/api/v1/onec-agent/*` (long-poll pull, Ed25519 imzoli vazifalar, lease/heartbeat). Bitta do'kon PK'si — bitta agent yozuvi (`devices.kind='onec_agent'`), imkoniyatlar sozlamada yoqiladi. **Agent infratuzilmasi — Bosqich 5** (qaror #66): agent ro'yxati, ulash, token, vazifa navbati va imzo — umumiy registr jadvallari `onec_agents` (`capabilities JSONB`), `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations`, migratsiya `0028 store_agent`; 1C ga xos qism — Bosqich 7 (`0029 onec_integration`). A-01 `hello` so'rovi `capabilities` ni yuboradi (`34-1c-agent.md` §14.2 sxemasi, `X-Agent-Protocol: 2`), server uni `onec_agents.capabilities` ga yozadi.
   - **Kassa bog'lanishi**: lokal ko'prik kassasi `cash_registers.fiscal_agent_id` (xizmat qiluvchi agent) + `fiscal_local_device_id` (agent `capabilities.fiscal.devices[].local_id`) orqali bog'lanadi; `fiscal_agent_id` berilsa `fiscal_local_device_id` majburiy. Sozlash — BO-12 kassa qatorida "Fiskal agent" (`PATCH /cash-registers/{id}`, ruxsat `settings.branches`).
   - **Imkoniyat tekshiruvi**: vazifa faqat agent `capabilities` da yoqilgan (`capabilities.<oila>.enabled = true`) oilaga qo'yiladi, aks holda `AgentTaskPort.enqueue` → `409 AGENT_CAPABILITY_DISABLED`.

**Bulut vazifa turlari — Bosqich 5** (`33` §9.5 oq ro'yxatida; `purpose='device_service'`, `base_id = null`, 1C bazasi talab qilinmaydi):

| `kind` | Vazifa | Payload | Natija | Bosqich |
|---|---|---|---|---|
| `fiscal.status` | FM holati va OFD tasdiqlari (har 5 daqiqada) | `{cash_register_id}` | `{cash_register_id, fm_state, pending_count, oldest_unacked_at, acked:[{fm_terminal_id, fm_receipt_seq, acked_at}]}` → `cash_registers.fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at`; `acked[]` → `fiscal_receipts.ofd_acked_at` (`tenant_id, fm_terminal_id, fm_receipt_seq` bo'yicha) | Bosqich 5 |
| `fiscal.resend_unsent` | Yuborilmagan cheklarni qayta yuborish (40 soatdan keyin server avtomatik qo'yadi, BO-14'da qo'lda ham) | `{cash_register_id}` | `ResendResult {sent, failed, acked[]}` (`acked[]` — `fiscal.status` dagidek) | Bosqich 5 |
| `fiscal.zreport` | Smena yopilishida Z-hisobotni FM'dan olish (POS yopiq bo'lsa) | `{cash_register_id, shift_id}` | `ZReport` → `fiscal_receipts(kind='z_report')` | Bosqich 5 |
| `print.raw` | Back-office'dan LAN printerga chop etish (masalan qayta chek nusxasi, kassa hisoboti) | `{printer_local_id, data_base64, encoding: "cp866"\\|"raster"}` | yuborildi / printer xatosi | Bosqich 5 |
| `scale.plu_upload` | PLU ro'yxatini yorliqli taroziga yuklash | `{scale_local_id, items:[{plu, name, price, barcode_prefix}]}` | yuklangan qatorlar soni / xato | MVP'dan keyin |

Bu ro'yxat""")

rep("lokal ko'prik tanlansa sertifikat Bosqich 5 dan oldin kerak.",
    "lokal ko'prik tanlansa — Bosqich 5/6 pilot tarqatishidan oldin (qaror #38).")

sec = """
### 16.1 Lokal API sxemalari

Standart port `47110` (agent sozlamasida o'zgaradi). Barcha so'rov/javob JSON, pul — butun son tiyin (`int64`), vaqt — ISO 8601 UTC.

| Yo'l | So'rov | Javob |
|---|---|---|
| `GET /v1/status` | — | `{agent_version, capabilities:{fiscal:{enabled, provider}, print:{enabled}}, fiscal_devices:[{local_id, fm_state, pending_count, oldest_unacked_at}]}` |
| `POST /v1/pair` | `{code, device_id}` | `{local_token, expires_at:null}` |
| `POST /v1/fiscal/open-shift` | `{cash_register: CashRegisterRef, shift_no, cashier_name}` | `FiscalShiftResult {fm_terminal_id, opened_at}` |
| `POST /v1/fiscal/close-shift` | `{cash_register, shift_no}` | `ZReport {fm_terminal_id, z_number, totals:{sale, return, by_payment_form}, closed_at}` |
| `POST /v1/fiscal/sale`, `/refund` | `FiscalReceiptPayload {cash_register, receipt_seq, kind, items:[{name, mxik, package_code, unit_code, qty_milli, price_tiyin, amount_tiyin, vat_rate, vat_tiyin, marking_codes[]}], payments:{payment_form, cash_tiyin, card_tiyin, qr_tiyin, card_type, card_mask, rrn}, refund_info?:{fm_terminal_id, fm_receipt_seq, fiscal_sign}}` | `FiscalResult {fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}` |
| `GET /v1/fiscal/device-status` | `?local_id=` | `FiscalDeviceStatus {fm_state, pending_count, oldest_unacked_at}` |
| `GET /v1/fiscal/unsent` | `?local_id=` | `{items: [UnsentReceipt {fm_receipt_seq, fiscal_at, amount_tiyin}]}` |
| `POST /v1/fiscal/resend` | `{local_id}` | `ResendResult {sent, failed, acked:[{fm_terminal_id, fm_receipt_seq, acked_at}]}` |
| `POST /v1/print/raw` | `{printer_local_id, data_base64, encoding}` | `{status:"sent"}` |

`CashRegisterRef = {cash_register_id, local_id}`. Xato shakli `{code, message_key, params?}`; HTTP: `401` (lokal token yo'q/noto'g'ri), `403` (`Origin` ro'yxatda yo'q), `409` (`FISCAL_SHIFT_STATE`, `FISCAL_DEVICE_LOCKED`), `423` (`FISCAL_OFFLINE_48H_BLOCKED`), `502` (`FISCAL_PROVIDER_ERROR`); hamkorga xos maydonlar adapter ichida qoladi. `FakeLocalBridge` shu sxemalarga tayanadi.
"""

anchor = """**Platforma oqibati**: lokal ko'prik rejimida veb-kassa — **Windows PK (Chrome/Edge) + Do'kon agenti**; Android Chrome va iOS'da fiskal kassa faqat hamkor bulut rejimida (1-bo'lim).
"""
rep(anchor, anchor + sec)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
