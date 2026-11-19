import sys, re, openpyxl, collections
from openpyxl.formula import Tokenizer
from openpyxl.utils import range_boundaries, get_column_letter
sys.setrecursionlimit(1000000)
path = sys.argv[1]
only = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
wb = openpyxl.load_workbook(path)
sheets = {ws.title.upper(): ws for ws in wb}
def parse_ref(tok, cur):
    t = tok
    if '!' in t:
        sh, ref = t.rsplit('!', 1); sh = sh.strip("'").upper()
        if '[' in sh: sh = sh.split(']')[-1]
    else:
        sh, ref = cur, t
    ref = ref.replace('$', '')
    return sh, ref
graph = collections.defaultdict(set)   # node -> deps
RANGE_CACHE = {}
def range_node(sh, ref):
    key = (sh, ref)
    if key in RANGE_CACHE: return RANGE_CACHE[key]
    try:
        c0, r0, c1, r1 = range_boundaries(ref)
    except Exception:
        RANGE_CACHE[key] = None; return None
    if c0 is None or r0 is None:   # whole column/row: skip
        RANGE_CACHE[key] = None; return None
    if c0 == c1 and r0 == r1:
        node = (sh, ref); RANGE_CACHE[key] = node; return node
    node = ('RNG', sh, ref)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            graph[node].add((sh, f"{get_column_letter(c)}{r}"))
    RANGE_CACHE[key] = node
    return node
n = 0
for ws in wb:
    sh = ws.title.upper()
    if only and sh not in only: continue
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if isinstance(v, str) and v.startswith('='):
                node = (sh, cell.coordinate)
                try:
                    toks = Tokenizer(v).items
                except Exception:
                    continue
                for t in toks:
                    if t.type == 'OPERAND' and t.subtype == 'RANGE':
                        # may be "A1:B2" or "Sheet!A1:B2"
                        s2, ref = parse_ref(t.value, sh)
                        d = range_node(s2, ref)
                        if d is not None: graph[node].add(d)
                n += 1
print('formulas', n, 'nodes', len(graph))
# iterative Tarjan
index = {}; low = {}; onstack = set(); stack = []; sccs = []
counter = [0]
def strongconnect(v0):
    work = [(v0, iter(graph.get(v0, ())))]
    index[v0] = low[v0] = counter[0]; counter[0] += 1; stack.append(v0); onstack.add(v0)
    while work:
        v, it = work[-1]
        advanced = False
        for w in it:
            if w not in index:
                index[w] = low[w] = counter[0]; counter[0] += 1; stack.append(w); onstack.add(w)
                work.append((w, iter(graph.get(w, ())))); advanced = True; break
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if advanced: continue
        work.pop()
        if work: low[work[-1][0]] = min(low[work[-1][0]], low[v])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); onstack.discard(w); comp.append(w)
                if w == v: break
            if len(comp) > 1 or v in graph.get(v, ()):
                sccs.append(comp)
for v in list(graph.keys()):
    if v not in index: strongconnect(v)
print('cyclic components', len(sccs))
for comp in sccs[:5]:
    cells = [c for c in comp if c[0] != 'RNG']
    print(len(comp), sorted(cells)[:15])
