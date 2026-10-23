# DB nomlari va enum'lar (11/12/13 egasidan, 2026-10-16) — 17–20, 07, 31, 33 shu bilan mos bo'lishi shart

- sale_payments + debt_payments: card_type ('personal','corporate','social','unknown'; method='card' bo'lsa majburiy), card_mask (^[0-9]{4}\*+[0-9]{4}$), rrn (card_type='social' bo'lsa card_mask bilan majburiy); debt_payments ga qr_type. UzQR: provider_tx_id faqat qr_type='dynamic' da majburiy; method='uzqr' qr_type talab qiladi; click/payme/uzum provider_tx_id talab qiladi.
- fiscal_receipts: kind ga 'credit_sale' (FiscalPolicy.credit_sale_receipt='none'|'credit_type', standart none); yangi ustunlar fm_terminal_id, fm_receipt_seq BIGINT, fiscal_at, ofd_acked_at (48 soat blok ofd_acked_at IS NULL bo'lgan eng eski fiskal chekdan hisoblanadi), payment_form ('cash','card','qr','mixed'), delivery ('printed','electronic', standart printed) + delivery_reason.
- cash_registers: fm_state ('ok','locked','ack_overdue','memory_full','unknown'), last_unacked_receipt_at, fm_receipts_pending, tax_registered_at, outlet_address_snapshot, txkm_contract_ref.
- tenants: legal_form ('llc','jsc','private_enterprise','sole_proprietor'), go_live_date, accepted_terms_version/at/ip; settings kalitlari supplier_overpay_policy ('warn'|'block'), vat_diff_tolerance_amount "1000.00", discount_posting ('gross_9050'|'net'), owner_withdrawal_account, payment_org_commission_account ('9430'|'9410'), turnover_tax_account ('9430'|'9820'), fiscal_policy {debt_receipt_split 'single'|'per_sale', credit_sale_receipt}, weight_barcode_templates[], ai_cross_border_enabled.
- warehouses.inventory_account ('2910','2920'; do'kon→2920, ombor→2910).
- write_off_lines.reason ga 'expired_return'; write_off_lines.gift_kind ('promo_justified','other', reason='gift' bo'lsa majburiy); write_offs.promo_order_ref, write_offs.source_return_id; return_lines.restock BOOLEAN.
- stock_counts.started_at, responsible_user_id; count_lines.snapshot_qty, counted_at (qaror #53).
- debt_writeoffs.tax_writeoff_basis ('court','bankruptcy','liquidation','death','limitation','none'); debt_payment_allocations.target_doc_type ('sales','debt_openings','debt_writeoffs') — hisobdan chiqarilgan qarzga to'lov Kt 9390.
- goods_receipts.kind ('purchase','gratuitous'); counterparties.is_founder; cash_movements.counterparty_id (ta'sischi); bank_settlements.variance_amount (faqat inkassa); ledger_adjustments.analytics JSONB.
- expense_categories: code, default_account ('9410','9420','9430','6410'), source_ref; expenses.tax_type ('vat','turnover','pit','social','property','land','other') soliq to'lovi kategoriyasi uchun (Dt 6410/Kt 5110).
- YANGI hujjat tax_settlements (kod 'ST'): tax_kind ('vat_offset','turnover_tax'), period, base_amount, rate, amount, expense_account → 13 §2.26 Dt 6410/Kt 4410 va §4.3 Dt 9430/Kt 6410. API (20): POST /tax-settlements (server hisoblagan qoralama), POST /tax-settlements/{id}/post, /cancel.
- YANGI sync_exceptions jadvali (reviewed_at/by/review_note, qaror #56) va platform.fx_rates (qaror #55); billing_payments.kind ('payment','manual_extension','refund') + reason; einvoices.risk_flag ga 'unknown' (standart), factura_type, related_einvoice_id; ettn_documents.transfer_id/transport_type/direction; transfers.ettn_ref, transport_mode ('vehicle','on_foot_or_public'); tenant_secrets.cash_register_id (har kassa uchun UzQR kaliti).
- onec_settings.credit_revenue_timing ustuni olib tashlandi (faqat sotuv kuni).
- 48 soat blok xato kodi: FISCAL_OFFLINE_48H_BLOCKED.

## 26 raqamlari (yakuniy) — havola: "26 #N (OQ-0xx)"
Tashqi javob kerak (B): #9 OQ-002 kredit chek turi · #40 OQ-025 CRPT · #42 OQ-011 reyestr narxi · #45 OQ-102 Eskiz · #47 OQ-019 Faktura.uz risk · #49 OQ-032 dinamik UzQR API · #51 OQ-043 UzCloud SLA/PITR · #63 OQ-063 PAX SDK · #71 OQ-047 · #89 OQ-008 fm_state/ofd_status · #94–#99, #101 OQ-057 (1C OQ-02..07, 09) · #100 OQ-052 · #102 OQ-053 · #103/#104 1C OQ-11/12 · #105 OV sertifikat · #109 OQ-012 fiskal hamkor (BLOK Bosqich 5) · #112 OQ-018 faqat-elektron chek · #118 OQ-028 E-IMZO API-KEY · #127 OQ-042 oferta/rozilik · #130 OQ-046 yuridik shaxs · #132 OQ-049 · #133 OQ-050 · #135 OQ-054 · #136 OQ-055 · #137 OQ-056 · #139 OQ-060 printer testi · #167 Didox (asoschi) · #168 hamkor kassa narxi vs +39 000 · #169 VMQ-393 ikkilamchi tizim · #170 karta/UzQR integratsiyasi reyestr sharti · #19 OQ-078 · #20 OQ-079 · #24 OQ-098.
Yopilgan (A) misollar: #107 OQ-004 48 soat blok · #113 OQ-021 E-TTN · #4 OQ-024 e-ishonchnoma · #10 MARKING_PRECHECK=warn · #34 5710+9430 · #35 9390 · #36 0000 · #93 1C OQ-01. Yangi A raqamlari #106–#166 OQ tartibida (OQ-003→106 … OQ-101→166); to'liq indeks 26 oxirida. Qarorlar #43–#65 — 01 da yozilgan.

## Qo'shimcha (11/12 egasi, 2-bosqich)
- platform.terms_versions (version PK, kind 'terms'|'privacy'|'ai_cross_border', text_url, text_sha256, effective_from, is_current); app.consents (subject 'tenant'|'user', user_id, purpose 'terms'|'ai_cross_border'|'ai_training', terms_version, accepted, ip, at) — append-only.
- app.bank_statement_imports (attachment_id, file_sha256 UNIQUE per tenant, format '1c_client_bank_exchange', account, period_from/to, status 'parsed'|'failed', rows_total, drafts_created, duplicates, ignored_outgoing, unmatched_lines JSONB, error_code, parsed_at); bank_settlements.statement_import_id (source='statement_import' bo'lsa majburiy). net_amount = gross − commission + variance (variance < 0 — kamomad).
- tenants.settings: marking_precheck ('off'|'warn'|'block', standart 'warn'), bank_account, bank_mfo; supplier_payment_strict yo'q.
- transfers.vehicle_plate, driver_name; ettn_documents.status CHECK ('pending_signature','sending','registered','received','accepted','rejected','cancelled'); einvoice_id NULL ruxsat.
- outbox_jobs.kind: + 'ettn_accept','marking_accept','marking_return' ('label_pdf','report_export' bor). Bank importi sinxron — outbox turi yo'q.
- payment_checkouts: provider='uzqr' faqat qr_type='dynamic' (statik UzQR seanssiz).
- billing_payments.actor_user_id (manual_extension'da majburiy, provider NULL, amount 0, reason majburiy).
- count_lines.counted_at — qurilma vaqti (offline sanashda ham, server_time ofseti bilan).
- onec_settings.same_day_returns ('orp_returns_section','separate_document'), standart 'orp_returns_section'.
- devices.kind ('web','android','onec_agent') — 'onec_agent' = yagona Do'kon agenti (qaror #60).
- oauth_clients.status ('active','pending_secret','disabled'); CHECK client_type='public' OR secret IS NOT NULL OR status='pending_secret'.
- ledger_entries/ledger_adjustments account_dt/kt CHECK ~ '^[0-9]{4}$'; stock_lots.source_doc_type + 'stock_counts'.
