import re, glob, os, sys, json
from collections import defaultdict
os.chdir('E:/Project/erp/spec/kod-uchun')
ROOT = 'E:/Project/erp'
files = sorted(glob.glob('*.md'))
num2file = {f[:2]: f for f in files}
text = {f: open(f, encoding='utf-8').read().split('\n') for f in files}

def norm(s):
    return s.strip().rstrip('.')

# headings
heads = {}
for f in files:
    hs = []
    for l in text[f]:
        m = re.match(r'^(#{1,6})\s+(.*)$', l)
        if m:
            hs.append(m.group(2).strip())
    heads[f] = hs

def sec_exists(f, x):
    x = x.rstrip('.').rstrip(',')
    if not x:
        return True
    pat = re.compile(r'^(?:\d+\.\s+)?[`*«"]?' + re.escape(x) + r'(?![\w])', re.I)
    for h in heads[f]:
        h2 = h.lstrip('#').strip()
        if pat.match(h2):
            return True
        # "2-bo'lim" style or "§X" mention
        if re.match(r'^' + re.escape(x) + r'[\.\s:)—-]', h2):
            return True
    # also accept e.g. "0.9-band" defined as list/paragraph item "**0.9**" or line starting "x." in text
    for l in text[f]:
        if re.match(r'^\s*(?:[-*]\s*)?\**' + re.escape(x) + r'[\.\)]?\**\s', l):
            return True
    return False

out = []
def rep(kind, f, ln, msg):
    out.append((kind, f, ln, msg))

FILEREF = re.compile(r'`?((?:spec/|research_notes/|spec/kod-uchun/)?[\w./-]*?)(\b\d\d-[a-z0-9-]+\.md)`?')
# 1. file existence: any NN-xxx.md
for f in files:
    for i, l in enumerate(text[f], 1):
        for m in re.finditer(r'(?<![\w/])((?:[\w.-]+/)*)(\d\d-[A-Za-z0-9_-]+\.md)', l):
            pre, name = m.group(1), m.group(2)
            if pre and not pre.startswith('spec/kod-uchun'):
                p = os.path.join(ROOT, pre, name)
                if not os.path.exists(p):
                    # try relative to research_notes/ochiq-savollar
                    rep('FILE-EXT', f, i, f'{pre}{name} topilmadi')
            else:
                if name not in files:
                    # maybe a research note without prefix
                    cands = glob.glob(ROOT + '/**/' + name, recursive=True)
                    rep('FILE', f, i, f'{name} — spec/kod-uchun da yo\'q' + (f' (mavjud: {cands[0][len(ROOT)+1:]})' if cands else ' (hech qayerda yo\'q)'))
        for m in re.finditer(r'`((?:spec|research_notes)/[^`\s]+)`', l):
            p = m.group(1).rstrip('/')
            p2 = re.sub(r'[#§].*$', '', p)
            if '*' in p2 or '<' in p2 or '…' in p2: continue
            if not os.path.exists(os.path.join(ROOT, p2)):
                rep('PATH', f, i, f'{p} topilmadi')

# 2. § refs
SEC = re.compile(r'§\s*([0-9]+(?:\.[0-9]+)*(?:[a-z](?![a-z]))?(?:\.[0-9]+[a-z]?)*|[A-Za-z][\w-]*)')
FREF = re.compile(r'(?:`(\d\d)(?:-[A-Za-z0-9_-]+\.md)?`|(?<![\w#.§-])(\d\d)(?=\s*(?:\([^)]{0,80}\)\s*)?§))')
for f in files:
    for i, l in enumerate(text[f], 1):
        prev_end = 0
        prev_ctx = f; prev_expl = False
        for m in SEC.finditer(l):
            span = l[prev_end:m.start()]
            frs = list(FREF.finditer(span))
            expl = False
            if frs:
                expl = True
                last = frs[-1]
                nn = last.group(1) or last.group(2)
                ctx = num2file.get(nn)
                # if the file ref is far (>60 chars) and something else in between, still use
                if ctx is None:
                    rep('SEC-FILE', f, i, f'{nn} fayl yo\'q (§{m.group(1)})')
                    prev_end = m.end(); continue
            elif prev_end and re.fullmatch(r'[\s,;/–\-]*(?:va|yoki|and)?[\s,;/–\-]*', span):
                ctx = prev_ctx; expl = prev_expl
            elif prev_end and len(span) < 4:
                ctx = prev_ctx; expl = prev_expl
            else:
                ctx = f
            x = m.group(1)
            # range: §1–5 handled by first token
            if not sec_exists(ctx, x):
                where = [ff[:2] for ff in files if sec_exists(ff, x)]
                rep('SEC-EXPL' if expl else 'SEC-IMPL', f, i, f'[{",".join(where)}] ' + f'{ctx[:2]} §{x} — sarlavha topilmadi :: ' + l.strip()[max(0, m.start()-60):m.start()+20])
            prev_ctx = ctx; prev_expl = expl; prev_end = m.end()

# 3. decisions
dec = set()
for l in text['01-qarorlar.md']:
    m = re.match(r'^\|\s*(\d+)\s*\|', l)
    if m: dec.add(int(m.group(1)))
DEC = re.compile(r'(?:qaror(?:lar|i|ga|da|dagi|ni)?|01)\s*(#\d+(?:\s*(?:[–\-…,/]|va|yoki)\s*#\d+)*)', re.I)
for f in files:
    for i, l in enumerate(text[f], 1):
        for m in DEC.finditer(l):
            for n in re.findall(r'#(\d+)', m.group(1)):
                if int(n) not in dec:
                    rep('DEC', f, i, f'qaror #{n} 01 da yo\'q')

# 4. 26 rows
A, B = {}, {}
cur = None
for l in text['26-ochiq-savollar-reestri.md']:
    if l.startswith('## Jadval A'): cur = A
    elif l.startswith('## Jadval B'): cur = B
    elif l.startswith('## '): cur = None
    elif cur is not None:
        m = re.match(r'^\|\s*(\d+)\s*\|\s*([^|]*)\|', l)
        if m: cur[int(m.group(1))] = m.group(2).strip()
json.dump({'A': A, 'B': B}, open('E:/Project/erp/research_notes/mustaqil-tekshiruv/_scripts/26rows.json', 'w'))
R26 = re.compile(r'(?<![\w.])26\s*(?:Jadval\s*[AB]\s*)?(#\d+(?:\s*(?:\([^)]*\))?\s*(?:[–\-…,/]|va|yoki)\s*#\d+)*)')
for f in files:
    for i, l in enumerate(text[f], 1):
        for m in R26.finditer(l):
            for n in re.findall(r'#(\d+)', m.group(1)):
                n = int(n)
                if n not in A and n not in B:
                    rep('R26', f, i, f'26 #{n} hech bir jadvalda yo\'q')
        # pair consistency: 26 #N (OQ-0xx)
        for m in re.finditer(r'26\s*#(\d+)\s*\((OQ-\d{3})', l):
            n = int(m.group(1)); oq = m.group(2)
            row = A.get(n) or B.get(n)
            if row is not None and oq not in row:
                rep('R26-OQ', f, i, f'26 #{n} OQ ustuni "{row}", matnda {oq}')

# 5. ids
def defined(pattern, fl):
    s = set()
    for ff in fl:
        for l in text[ff]:
            for mm in re.finditer(pattern, l):
                s.add(mm.group(0))
    return s
US_def = set(re.findall(r'\*\*(US-M\d\d-\d\d)\*\*', '\n'.join(text['03-modullar-talablari.md'])))
BP_def = set(re.findall(r'^## (BP-\d\d)', '\n'.join(text['04-biznes-jarayonlar.md']), re.M))
SCR_def = set(re.findall(r'^## ((?:POS|BO|ADM)-\d\d)', '\n'.join(text['07-ekran-tafsilotlari.md']), re.M))
QT_def = set(re.findall(r'^\|\s*(QT-[A-Z0-9-]+?)\s*\|', '\n'.join(text['31-qabul-testlari.md']), re.M))
print('US', len(US_def), 'BP', len(BP_def), 'SCR', len(SCR_def), 'QT', len(QT_def), 'DEC', len(dec), 'A', len(A), 'B', len(B))

def expand(a, b, prefix, width=2):
    return [f'{prefix}{k:0{width}d}' for k in range(int(a), int(b) + 1)]

for f in files:
    for i, l in enumerate(text[f], 1):
        for mm in re.finditer(r'\bUS-M(\d\d)-(\d\d)(?:\s*[…–-]\s*(?:US-M\d\d-)?(\d\d)\b)?', l):
            ids = [f'US-M{mm.group(1)}-{mm.group(2)}']
            if mm.group(3): ids = expand(mm.group(2), mm.group(3), f'US-M{mm.group(1)}-')
            for u in ids:
                if u not in US_def: rep('US', f, i, f'{u} 03 da aniqlanmagan')
        for mm in re.finditer(r'\bBP-(\d\d)\b', l):
            if f'BP-{mm.group(1)}' not in BP_def: rep('BP', f, i, f'BP-{mm.group(1)} 04 da yo\'q')
        for mm in re.finditer(r'\b(POS|BO|ADM)-(\d\d)\b', l):
            sid = f'{mm.group(1)}-{mm.group(2)}'
            if sid not in SCR_def: rep('SCR', f, i, f'{sid} 07 da yo\'q')
        for mm in re.finditer(r'\b(QT-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d\d)\b', l):
            q = mm.group(1)
            if q not in QT_def and f != '31-qabul-testlari.md' or (f == '31-qabul-testlari.md' and q not in QT_def):
                rep('QT', f, i, f'{q} 31 da yo\'q')
        # ranges like QT-M19-10…12
        for mm in re.finditer(r'\b(QT-[A-Z0-9]+(?:-[A-Z0-9]+)*-)(\d\d)\s*[…–]\s*(\d\d)\b', l):
            for q in expand(mm.group(2), mm.group(3), mm.group(1)):
                if q not in QT_def: rep('QT', f, i, f'{q} (oraliqdan) 31 da yo\'q')
        for mm in re.finditer(r'\b(QT-[A-Z0-9]+(?:-[A-Z0-9]+)*-)(\d\d)/(\d\d)\b', l):
            q = mm.group(1) + mm.group(3)
            if q not in QT_def: rep('QT', f, i, f'{q} 31 da yo\'q')

for k in out:
    print('\t'.join(map(str, k)))
