p = r'E:/Project/erp/spec/kod-uchun/32-kod-qoidalari.md'
s = open(p, encoding='utf-8').read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:90])
    s = s.replace(old, new)


# T-187 (206, 225, 473)
rep("08-dizayn-tizimi.md` §0.1", "08-dizayn-tizimi.md` §0 (1-band)", 3)
# T-277
rep("CI'da `ruff`, `mypy app`, `pytest`", "CI'da `ruff`, `mypy --strict app`, `pytest`")
# T-197
rep("| `spec/kod-uchun-atamalar` (joriy branch nomi shu uslubga mos) |", "| `spec/kod-uchun-atamalar` |")
# T-024
rep("""│   │   └── telemetry.py         # OpenTelemetry, prometheus-client, sentry-sdk
│   ├── modules/""",
    """│   │   └── telemetry.py         # OpenTelemetry, prometheus-client, sentry-sdk
│   ├── shared/
│   │   └── debt_allocation.py   # qarz to'lovi allokatsiyasi va debt_settlement chek qatorlari (TS juftligi — web shared/lib/debt-allocation)
│   ├── modules/""")
rep("""- Pul hisob-kitobi test-vektorlari (`shared/money-vectors.json`) — backend va frontend **bitta fayldan** o'qiydi (3.2–3.3-bo'lim), ikki tomonda alohida qo'lda yozilmaydi.
""",
    """- Pul hisob-kitobi test-vektorlari (`shared/money-vectors.json`) — backend va frontend **bitta fayldan** o'qiydi (3.2–3.3-bo'lim), ikki tomonda alohida qo'lda yozilmaydi.
- Qarz to'lovi allokatsiyasi va `debt_settlement` chek qatorlari (qaror #67; `18-api-kassa.md` §12.2) — TS `shared/lib/debt-allocation` (offline POS) va Python `app/shared/debt_allocation.py` (server posting) bitta formulani amalga oshiradi; test-vektorlar `shared/debt-allocation-vectors.json` — `shared/money-vectors.json` bilan bir xil qoida: ikki tomon bitta fayldan o'qiydi, CI'da ikkalasi bir xil natija beradi.
""")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
