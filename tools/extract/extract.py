# -*- coding: utf-8 -*-
"""
精靈王石器 (PrimalSA) 遊戲資料匯出器 —— 只讀取 GameClient，不修改任何遊戲檔案。

用法（在專案根目錄）：
  uv run --no-project --with UnityPy python tools/extract/extract.py
  （選項 --game <GameClient 路徑>  --out <knowledge 路徑>）

步驟：
  1. 解出 hotupdate.dll.assetbundle → HotUpdate.dll（放 tools/.cache，供 schema / 列舉分析）
  2. 編譯並執行 tools/schemadump/SchemaDump.cs（ReflectionOnly，不執行遊戲程式）→ schema.tsv、enums.tsv
  3. configs.assetbundle → Tabtoy 設定表 → knowledge/data/tables/<表名>.jsonl（一列一筆）
  4. mapdata_*.assetbundle → knowledge/data/maps.bin（通行格）+ knowledge/data/mapinfo.json
  5. 呼叫 docs.py 產生分類 Markdown
"""
import sys, os, re, json, glob, struct, zlib, time, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import tabtoy

CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'

def bundle_bytes(path):
    """遊戲的 bundle 前面塞了假資料（含多個 UnityFS 簽章），真正的 bundle 是前 1024 bytes 內最後一個 UnityFS"""
    b = open(path, 'rb').read()
    p = b.rfind(b'UnityFS', 0, 1024)
    return b[p:] if p > 0 else b

def text_assets(path):
    import UnityPy
    env = UnityPy.load(bundle_bytes(path))
    out = {}
    for o in env.objects:
        if o.type.name == 'TextAsset':
            d = o.read()
            s = d.m_Script
            if isinstance(s, str):
                s = s.encode('utf-8', 'surrogateescape')
            out[d.m_Name] = bytes(s)
    return out

def log(*a):
    print(*a, flush=True)

# ---------------- 1+2. HotUpdate.dll → schema / enums ----------------
def build_schema(ab, cache, data_dir):
    os.makedirs(cache, exist_ok=True)
    dll = os.path.join(cache, 'HotUpdate.dll')
    ta = text_assets(os.path.join(ab, 'hotupdate.dll.assetbundle'))
    open(dll, 'wb').write(ta['HotUpdate.dll'])
    for name, b in text_assets(os.path.join(ab, 'hofix_dll.assetbundle')).items():   # 依賴組件（ReflectionOnly 解析型別用）
        open(os.path.join(cache, name), 'wb').write(b)
    exe = os.path.join(cache, 'SchemaDump.exe')
    src = os.path.join(ROOT, 'tools', 'schemadump', 'SchemaDump.cs')
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        subprocess.check_call([CSC, '/nologo', '/out:' + exe, src])
    for mode, fn in (('schema', 'schema.tsv'), ('enums', 'enums.tsv')):
        out = subprocess.check_output([exe, mode, dll, cache])
        open(os.path.join(data_dir, fn), 'wb').write(out)
    return os.path.join(data_dir, 'schema.tsv')

# ---------------- 3. 設定表 ----------------
def export_tables(ab, schema, data_dir):
    raw = text_assets(os.path.join(ab, 'configs.assetbundle'))['Configs']
    T = tabtoy.tables(raw, schema)
    tdir = os.path.join(data_dir, 'tables')
    os.makedirs(tdir, exist_ok=True)
    for f in glob.glob(os.path.join(tdir, '*.jsonl')): os.remove(f)
    for name, rows in T.items():
        with open(os.path.join(tdir, name + '.jsonl'), 'w', encoding='utf-8', newline='\n') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    return T

# ---------------- 4. 地圖 ----------------
def parse_ls2map(t):
    """LS2MAP（大端序）："LS2MAP" + uint16 範本ID + 32 bytes 名稱(GBK,'|'分隔) + uint16 寬 + uint16 高 + 地面層 uint16[w*h] + 物件層 uint16[w*h]"""
    name = t[8:40].split(b'\0')[0].decode('gbk', 'replace').split('|')[0]
    w, h = struct.unpack_from('>HH', t, 40); n = w * h
    if len(t) < 44 + 4 * n: raise ValueError('長度不足')
    return name, w, h, struct.unpack_from('>%dH' % n, t, 44), struct.unpack_from('>%dH' % n, t, 44 + 2 * n)

def build_grid(w, h, ground, objs, off):
    """格子值 0=無地面 1=可通行 2=不可通行地面(水/懸崖) 3=物件阻擋；物件佔地 xland×yland 從錨點往 (x+i, y-j) 延伸"""
    walk = [0] * 65536
    for k, r in off.items():
        if 0 < k < 65536: walk[k] = 1 if r[2] else 2
    g = bytearray(map(walk.__getitem__, ground))
    for k, o in enumerate(objs):
        if not o: continue
        r = off.get(o)
        if r is None or r[2]: continue
        x, y = k % w, k // w
        for j in range(max(1, r[1])):
            yy = y - j
            if yy < 0: break
            for i in range(max(1, r[0])):
                if x + i < w: g[yy * w + x + i] = 3
    return g

def export_maps(ab, T, data_dir):
    import UnityPy
    off = {}
    for r in T.get('MapOffset', []):
        oid = r.get('ID', r.get('f2_0'))
        if oid is not None: off[oid] = (r.get('xland', 1), r.get('yland', 1), r.get('walkable', 0))
    entries = []; info = {}; bad = 0
    files = sorted(glob.glob(os.path.join(ab, 'mapdata_*.assetbundle')))
    for n, f in enumerate(files):
        mid = int(re.search(r'mapdata_(\d+)', os.path.basename(f)).group(1))   # 地圖 ID 以檔名為準（檔頭 ID 是範本）
        try:
            ta = text_assets(f)
            t = next(v for v in ta.values() if v.startswith(b'LS2MAP'))
            name, w, h, ground, objs = parse_ls2map(t)
            g = build_grid(w, h, ground, objs, off)
            c = zlib.compressobj(9, zlib.DEFLATED, -15); z = c.compress(bytes(g)) + c.flush()
            entries.append((mid, w, h, z))
            info[mid] = {'w': w, 'h': h, 'headerName': name, 'walkable': g.count(1)}
        except Exception as e:
            bad += 1; log('  略過 %s：%s' % (os.path.basename(f), e))
        if n % 300 == 299: log('  地圖 %d / %d' % (n + 1, len(files)))
    entries.sort()
    # maps.bin：'PSAMAP1' + int32 數量 + [int32 id, uint16 寬, uint16 高, int32 長度, raw deflate(每格 1 byte，索引 = y*寬+x)]
    with open(os.path.join(data_dir, 'maps.bin'), 'wb') as fo:
        fo.write(b'PSAMAP1'); fo.write(struct.pack('<i', len(entries)))
        for mid, w, h, z in entries:
            fo.write(struct.pack('<iHHi', mid, w, h, len(z))); fo.write(z)
    json.dump({str(k): v for k, v in sorted(info.items())}, open(os.path.join(data_dir, 'mapinfo.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    log('  maps.bin：%d 張地圖%s' % (len(entries), '（%d 張失敗）' % bad if bad else ''))

# ---------------- 其他小型資料 ----------------
def export_misc(ab, data_dir):
    ver = os.path.join(ab, 'app.ver')   # 遊戲啟動後才會有（客戶端版本）
    open(os.path.join(data_dir, 'app.ver'), 'wb').write(open(ver, 'rb').read() if os.path.exists(ver) else b'')
    alt = text_assets(os.path.join(ab, 'itemaltlist.assetbundle')).get('ItemAltList', b'')
    open(os.path.join(data_dir, 'ItemAltList.csv'), 'wb').write(alt)
    # bundle 清單（分類用）
    rows = []
    for f in sorted(os.listdir(ab)):
        p = os.path.join(ab, f)
        if os.path.isfile(p): rows.append('%s\t%d' % (f, os.path.getsize(p)))
    open(os.path.join(data_dir, 'bundles.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default=os.path.join(ROOT, 'GameClient'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'knowledge'))
    ap.add_argument('--skip-maps', action='store_true')
    a = ap.parse_args()
    ab = os.path.join(a.game, 'PrimalSA_Data', 'StreamingAssets', 'AssetBundles')
    data_dir = os.path.join(a.out, 'data'); os.makedirs(data_dir, exist_ok=True)
    cache = os.path.join(ROOT, 'tools', '.cache')
    t0 = time.time()
    log('1/5 解出 HotUpdate.dll，產生 schema / 列舉 ...')
    schema = build_schema(ab, cache, data_dir)
    log('2/5 解析設定表 configs.assetbundle ...')
    T = export_tables(ab, schema, data_dir)
    log('  %d 張表' % len(T))
    log('3/5 其他資料 ...')
    export_misc(ab, data_dir)
    if not a.skip_maps:
        log('4/5 地圖 ...')
        export_maps(ab, T, data_dir)
    log('5/5 產生分類文件 ...')
    import docs
    docs.build(a.out)
    log('完成，用時 %.1f 秒' % (time.time() - t0))

if __name__ == '__main__':
    main()
