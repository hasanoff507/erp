# Sohalar bo'yicha ehtiyojlar — tafsiliy tadkik

## Chakana (Retail: kiyim, elektronika)
- **Soha**: 164,481 trade businesses (2026), largest sector by count
- **Asosiy dasturlar**: BILLZ (4000+), REGOS (5000+), OX System, HIPPO, RAOS, JetPos
- **Asosiy jarayonlar**:
  - Barcode scanning / QR code scanning for marked goods
  - Real-time inventory update after each sale
  - Multiple payment methods (cash, card, QR, credit)
  - Variant tracking (size, color, IMEI for electronics)
  - Loyalty programs
- **Majburiy talablar**:
  - OFD (Online Fiscal Device) — cheklar real vaqtda Soliq qo'mitasiga
  - Asl belgisi markirovka (2026-03-01 dan muddati o'tgan tovar bloklanadi)
  - Marked product code scanning at sale (code goes into fiscal receipt)
  - IMEI registration for mobile devices (must be in inventory)
  - Elektronik hisob-faktura (EDO)
- **Hozir nima ishlatadi**: Simple POS'lar (BILLZ, REGOS, desktop JetPos), smartphone apps (MobiSklad), Telegram bots for reporting
- **AI halqilashi og'riq**:
  - Auto-detecting marked goods by code + expiry alert
  - Demand forecasting by variant/size/color
  - Inventory alerts (low stock by location)
  - Real-time shelf visibility (camera + marked code)
- **Tipik o'lcham**: 500–5000 store network; BILLZ 4000+, REGOS 5000+ (faqat POS)
- **Ombor harakat**: High inventory turnover (daily), variant-heavy

---

## Oziq-ovqat (Food stores, minimarkets)
- **Soha**: ~164,481 trade businesses; Jan–Apr 2026 retail growth 22.9% (165.8 trl. som), SME's 113.8 trl. (121.3% growth)
- **Asosiy dasturlar**: EasyTrade, RAOS, iDo'kon, MDokon (299k tariff + credit), Optimo, Paloma365
- **Asosiy jarayonlar**:
  - Batch and expiry tracking (FEFO — First Expired First Out)
  - Real-time inventory by batch/expiry date
  - Multiple payment types (cash, card, QR, credit/"nasiya")
  - Electronic scales integration (weight-based pricing)
  - Daily stock reconciliation
- **Majburiy talablar**:
  - OFD + virtual cash register (online ChEK)
  - Asl belgisi marking (marked goods scanning)
  - Batch/expiry date tracking (separate stock lines)
  - Expiry date alert (30–60 days before expiration)
  - Destruction certificate for expired goods
  - Elektronik hisob-faktura (EDO)
- **Hozir nima ishlatadi**: EasyTrade (widespread, no AI), MDokon (pushes credit as paid add-on), simple POS'lar, handwritten batch registers
- **AI halqilashi og'riq**:
  - Expiry prediction + auto-alert (prevent waste)
  - Demand forecasting by product/season
  - Auto-mark expired items as non-sellable
  - Supplier reorder optimization
  - Credit/nasiya risk scoring (who defaults most)
- **Tipik o'lcham**: 1–20 cashiers; SME's dominate (22.9% growth Q1 2026)

---

## HoReCa (Restaurants, cafes, fast food)
- **Soha**: ~1,942 new food service businesses (Q1 2026), ~69.8 bn. som revenue (Apr 2026)
- **Asosiy dasturlar**: iiko (~1000 restoran), Horyco, Soft24 (iiko partner), r_keeper, Poster, Paloma365
- **Asosiy jarayonlar**:
  - Kitchen order tracking (tickets, prep time, station workflow)
  - Recipe/portion control (menu item costs)
  - Staff scheduling and shift management
  - Inventory for FMCG input (ingredient batches, expiry)
  - Order delivery integration (Uzum Tezkor, TBC)
- **Majburiy talablar**:
  - OFD + virtual cash register
  - Asl belgisi marking (for alcohol, tobacco, some ingredients)
  - Elektronik hisob-faktura
  - Labor licensing (may vary by region)
  - Marked goods batch tracking (if purchasing FMCG with marks)
- **Hozir nima ishlatadi**: iiko (premium, complex, ~1000 users), Horyco (new 2026), simple POS + Excel
- **AI halqilashi og'riq**:
  - Kitchen load prediction + staff scheduling
  - Ingredient demand forecasting (reduce waste)
  - Labor cost optimization
  - Delivery time prediction
  - Recipe yield variance detection
- **Tipik o'lcham**: 5–100 seats; chains with 2–50+ outlets; labor-intensive

---

## Ulgurji va distribyutsiya (Wholesale, FMCG, savdo agentlari)
- **Soha**: 50+ large FMCG distributors (2023), distributor teams with 360+ field personnel, 1.2M SME's at 2026 Q1
- **Asosiy dasturlar**: Smartup (19,500 users, 600+ companies, FMCG-specific), BILLZ, MoySklad (integrates 1C), iiko (delivery orders)
- **Asosiy jarayonlar**:
  - **Savdo agenti marshruti** (sales agent route optimization, visit tracking, real-time geotagging)
  - **Nasiya/qarz daftar** (credit register — who owes how much, payment schedule, aging)
  - Trade marketing (promotional materials, shelf tracking)
  - Multi-warehouse inventory (regional hubs, transit)
  - Commission/incentive tracking
  - Contragent (supplier) credit limits
- **Majburiy talablar**:
  - Elektronik hisob-faktura (EDO) — Didox, Faktura.uz
  - Asl belgisi marking (marked goods receipt/sale)
  - OFD for B2B point-of-sale if any
  - 1C integration (back-office accounting)
  - Bank/payment gateway integration (Click, Payme)
  - Fake invoice detection (AI risk-scoring)
- **Hozir nima ishlatadi**: Smartup (with AI javon photo check), BILLZ API (P&L data), MoySklad (1C modules), manual Excel + WhatsApp updates, standalone CRM's (amoCRM)
- **AI halqilashi og'riq**:
  - Route optimization (minimize drive time, maximize stops)
  - Debtor prediction (who will default, when)
  - Invoice risk detection (fake/risky supplier invoices)
  - Demand forecasting by region/product
  - Automated credit limit & term decisions
- **Tipik o'lcham**: 600+ distributors; 5–500 field agents each
- **Kontragent xavfi**: +Didox, Faktura.uz integration for B2B invoice risk

---

## Ishlab chiqarish (Manufacturing: non, mebel, tekstil)
- **Soha**: ~63,861 industrial enterprises (2026)
- **Asosiy dasturlar**: None noted for Uzbekistan (Textile ERP exists globally but not localized)
- **Asosiy jarayonlar**:
  - Retseptura/texkarta (recipe/tech card) management + costing
  - Batch production tracking (BOM, work-in-progress by location)
  - Raw material lot/batch expiry (for perishables like yeast)
  - Multi-location inventory (warehouse, production floor, finished goods)
  - Yield/waste tracking (prevent spoilage)
- **Majburiy talablar**:
  - Asl belgisi marking (if product is marked category — non might be, tekstil unlikely)
  - Elektronik hisob-faktura (EDO)
  - OFD (if on-site retail)
  - Labor safety compliance (may vary)
- **Hozir nima ishlatadi**: 1C (but expensive localization), Excel + WhatsApp, handwritten records
- **AI halqilashi og'riq**:
  - Recipe optimization (ingredient costs, yield variance)
  - Quality control (defect pattern detection)
  - Demand planning (reduce over-production)
  - Batch traceability (if product recall needed)
- **Tipik o'lcham**: 10–500 employees; SME's dominate

---

## Qurilish mollari dilerlari (Construction materials dealers)
- **Soha**: Fragmented; B2B platforms emerging (b2b-savdo.uz, brix.uz)
- **Asosiy dasturlar**: Direct sales + Telegram, b2b marketplace, simple websites
- **Asosiy jarayonlar**:
  - Product catalog (specs, pricing by size/grade/color)
  - Variant inventory (size, finish, batch/lot number)
  - Multi-location stock (warehouse, showroom, branch)
  - Supplier PO's and lead time
  - Dealer network pricing/margin rules
- **Majburiy talablar**:
  - Product info label (name, regulatory doc, specs, price, mfg date, warranty, usage, service life)
  - Elektronik hisob-faktura (EDO)
  - OFD (if any retail point)
  - Asl belgisi marking (unlikely unless product is marked category)
- **Hozir nima ishlatadi**: b2b marketplaces (free signup), direct sales + WhatsApp, simple POS
- **AI halqilashi og'riq**:
  - Demand forecasting by region/season
  - Supplier coordination (lead time, price alerts)
  - Pricing optimization (margin by dealer/volume)
- **Tipik o'lcham**: 10–100+ dealers; small teams

---

## Apteka (Pharmacy)
- **Soha**: Licensed, heavily regulated; Ministry of Health oversees
- **Asosiy dasturlar**: Niche pharmacy POS (mostly Russian imports, 1C-based)
- **Asosiy jarayonlar**:
  - Drug registry compliance (product registration in State Register)
  - Batch/expiry tracking (mandatory, crucial)
  - Prescription management (if applicable)
  - License + GMP/GDP/GSP compliance
  - Supplier PO's (must register distributor in system)
  - Withdrawal/destruction report (expired goods)
- **Majburiy talablar**:
  - **Asl belgisi marking** (mandatory for all medicines, Data Matrix code + GTIN, serial, expiry, batch)
  - **Drug registry** (product registration, valid 5 years)
  - **EDS (Electronic Digital Signature)** for system access
  - Batch/expiry tracking (alert 30–60 days before expiration)
  - OFD + Elektronik hisob-faktura
  - License report to Ministry of Health
  - GDP/GSP compliance (good distribution practice, good storage practice)
- **Hozir nima ishlatadi**: Russian pharmacy POS (iiko derivatives), manual + 1C, Asl belgisi system (separate)
- **AI halqilashi og'riq**:
  - Expiry prediction + auto-quarantine before expiration
  - Regulatory compliance monitoring (license renewal, drug registry status)
  - Demand forecasting (prevent stockouts of critical drugs)
  - Supplier quality scoring (defect/expiry patterns)
- **Tipik o'lcham**: 100–1000+ outlets (small chains, independent)

---

## Xizmatlar (Services: go'zallik saloni, klinika, avtoservis)
- **Soha**: Fragmented; may require business licensing (Law #ZRU-701, 60 regulated activities)
- **Asosiy dasturlar**: None standardized; Fresha (booking), amoCRM (CRM), generic POS
- **Asosiy jarayonlar**:
  - Appointment/booking system + online calendar
  - Client management (contact, history, loyalty)
  - Staff scheduling + shifts
  - Service/supply inventory (tools, materials, consumables)
  - Payment processing (cash, card, QR, credit)
- **Majburiy talablar**:
  - OFD + virtual cash register
  - Elektronik hisob-faktura (if B2B services)
  - Business license (may apply to clinics, auto repair)
  - Data privacy (health data if clinic)
  - Labor licensing (may apply to certain services)
- **Hozir nima ishlatadi**: Fresha (global), simple POS + WhatsApp, paper appointment book
- **AI halqilashi og'riq**:
  - Appointment demand forecasting (scheduling optimization)
  - No-show prediction (send reminder, adjust overbooking)
  - Churn prediction (client retention)
  - Supply demand (consumable reorder)
- **Tipik o'lcham**: 1–50+ staff; SME-dominated

---

## Avto ehtiyot qismlar (Auto parts)
- **Soha**: 1.44K import shipments (Mar 2025–Feb 2026); JSC UZAUTO MOTORS largest buyer (1,883 shipments)
- **Asosiy dasturlar**: BILLZ, REGOS, simple POS
- **Asosiy jarayonlar**:
  - Inventory by part type, OEM spec, fitment (which car model/year)
  - Supplier PO management + lead time
  - Serial/lot tracking (warranty claims)
  - Warranty register (return/exchange)
  - Multi-location stock (warehouse, retail counter)
- **Majburiy talablar**:
  - OFD + Elektronik hisob-faktura
  - Asl belgisi marking (unlikely unless part is marked category)
  - IMEI (if selling electronics like sensors, modules)
  - Customs declaration (import compliance)
- **Hozir nima ishlatadi**: BILLZ, REGOS, simple POS, manual Excel
- **AI halqilashi og'riq**:
  - Demand forecasting by car model/season
  - Part compatibility checking (auto-suggest part bundles)
  - Supplier performance (delivery time, defect rate)
  - Pricing optimization (margin by supplier/volume)
- **Tipik o'lcham**: 5–500+ SKU's; small dealers to large chains

---

## Qo'shimcha ma'lumotlar

### Mavjud qarz/nasiya dasturlari
- **Nasiya Daftar** (play.google.com app) — simple credit register for mahalla shops
- **Qarz Daftari** (Telegram bot) — credit tracking for small businesses
- **MDokon 299k tariff** — includes debt tracking as paid module
- **Smartup** — advanced debtor analytics, payment schedule, commission tracking

### OFD va markirovka integrasiyasi
- **Didox** (largest EDO operator, ~250k companies) — auto-sends 1C
- **Faktura.uz** — REGOS, Smartup bilan ishlaydi
- **Asl belgisi (CRPT Turon)** — mandatory marking 2026-03-01
- **Multikassa** — virtual cash register + MoySklad/Poster

### Davlat talablari 2026
- **UzQR** (united QR system) — mandatory Jul 1, 2026
- **Fake invoice detection AI** — pilot Dec 22, 2025; full Jan 1, 2026 (QQS credit delay for risky invoices)
- **Cashless mandates** — Apr 1, 2026 for real estate, vehicles, utilities, etc.

---

## Tavsiya (Qaysi sohadan boshlash?)

**1. Oziq-ovqat do'konlari / minimarketlar (Food retail)** 
- 164,481 trade businesses, 22.9% growth Q1 2026
- Current software weak (EasyTrade, MDokon simple)
- Critical pain: expiry tracking, credit management (MDokon sells as paid add-on)
- High willingness to pay (e.g., MDokon 299k + credit fee)
- Less competitive AI space; Smartup focused on FMCG, not retail

**2. HoReCa (Restaurants, cafes, fast food)**
- ~1,942 new businesses Q1 2026; ~69.8bn som revenue
- iiko expensive/complex; Horyco just entering; gap in kitchen AI + labor optimization
- Premium segment, high willingness to pay
- ~1,000 restaurants currently on iiko (market size exists)
- AI for kitchen load, ingredient demand, labor scheduling is huge gap

**3. FMCG / Distribyutsiya (Wholesale + field sales)**
- 50+ large distributors, 360+ field force
- Smartup has gap: nasiya/qarz AI (debtor prediction), route optimization, fake invoice detection
- High complexity, high margins, high willingness to pay
- Nascent sector (Smartup growing but features incomplete)

---

## Mos yechimlar taqqoslash

| Soha | Asosiy jarayonlar | Majburiy talablar | Hozir nima ishlatadi | AI hal qiladigan og'riq |
|------|------|------|------|------|
| **Chakana (kiyim, elektronika)** | Barcode + variant, payment methods, loyalty | OFD, Asl belgisi, IMEI, marked goods scan, EDO | BILLZ (4k+), REGOS (5k+), POS, JetPos, MobiSklad | Marked code + expiry alert, demand by variant, shelf visibility |
| **Oziq-ovqat (do'kon, minimarket)** | Batch/expiry, inventory, scales, nasiya, payment | OFD, Asl belgisi, batch tracking, expiry alert, EDO | EasyTrade, RAOS, iDo'kon, MDokon (+ nasiya fee) | Expiry predict, demand forecast, auto-quarantine, nasiya risk |
| **HoReCa (restoran, kafe)** | Kitchen order, recipe, staff, ingredient batch, delivery | OFD, Asl belgisi marking, EDO | iiko (~1k), Horyco, r_keeper, Poster | Kitchen load forecast, ingredient demand, labor scheduling |
| **Ulgurji / distribyutsiya (FMCG, savdo agenti)** | Savdo agenti marshruti, nasiya/qarz, trade marketing, multi-warehouse | EDO, Asl belgisi, OFD, 1C link, fake invoice risk | Smartup (19.5k users), BILLZ, MoySklad, manual | Route optimize, debtor predict, invoice risk, demand forecast |
| **Ishlab chiqarish (non, mebel, tekstil)** | Retseptura/texkarta, batch prod, WIP, yield/waste | Asl belgisi (selektiv), EDO, OFD | 1C (expensive), Excel, handwritten | Recipe optimize, quality control, demand plan, batch trace |
| **Qurilish mollari dilerlari** | Catalog (specs/size/grade), variant inv, supplier PO | Product info label, EDO, OFD | b2b marketplaces, Telegram, simple POS | Demand forecast, supplier coord, pricing optimize |
| **Apteka (pharmacy)** | Drug registry, batch/expiry, prescription, license, supplier | Asl belgisi (mandatory), drug registry, EDS, batch track, destruction report, OFD, EDO | Russian POS (1C), manual + separate Asl belgisi | Expiry quarantine, license monitor, demand forecast, supplier score |
| **Xizmatlar (salon, klinika, avtoservis)** | Appointment, client mgmt, staff schedule, supply inv | OFD, EDO (if B2B), license (may apply), data privacy | Fresha, amoCRM, POS, paper book | Appt demand forecast, no-show predict, churn predict, supply order |
| **Avto ehtiyot qismlar** | Inventory (part type, OEM, fitment), supplier PO, warranty | OFD, EDO, IMEI (if electronics) | BILLZ, REGOS, Excel | Demand forecast, part compatibility, supplier performance |
