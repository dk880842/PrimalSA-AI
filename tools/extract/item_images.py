# -*- coding: utf-8 -*-
"""
匯出道具圖示 Sprite（背包 / 倉庫格縮圖比對用，tools/gui/itemimg_match.py）。只讀 GameClient，輸出到 tools/.cache/item-images/（不進 git、不寫 knowledge/）。

來源：AssetBundles/itemalt*.assetbundle（itemalt_0 … itemalt_2700 + itemaltlist），Sprite 名 = Item.imageId。
  - 絕大多數是 80×80 固定畫布（中心固定），少數 64×64 / 128×128（字塊、屬性石等）。
  - 不屬於任何 Item 的 Sprite（皮膚、寵物用…）也照抽，但索引標 items 空白；比對端一律排除。
輸出：
  <imageId>.png
  index.tsv        欄位：imageId、bundle、w、h、道具數、道具 ID 清單（逗號）、繁中名清單（「、」分隔，去重）
  missing.tsv      Item.imageId 在 bundle 裡找不到的：imageId、道具 ID 清單、繁中名清單
  meta.json        匯出摘要（Sprite 數、覆蓋率、bundle 清單 mtime；比對端用 index.tsv 的 mtime 當快取戳記）

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project --with UnityPy python tools/extract/item_images.py              # 匯出（約 10 秒）
  uv run --no-project --with UnityPy python tools/extract/item_images.py --dry-run    # 只統計不寫檔
  uv run --no-project python tools/extract/item_images.py --find 龍王的守護           # 只查索引（標準函式庫）：名稱子字串 / imageId / 道具 ID
退出碼：0 成功；1 找不到 bundle / 索引；2 查無結果（--find）
"""
import sys, os, io, json, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'tools', '.cache', 'item-images')
AB = os.path.join(ROOT, 'GameClient', 'PrimalSA_Data', 'StreamingAssets', 'AssetBundles')


def items():
    """Item.jsonl → {imageId(str): [(道具 ID, 繁中名)]}（依道具 ID 排序）"""
    by = {}
    with open(os.path.join(ROOT, 'knowledge', 'data', 'tables', 'Item.jsonl'), encoding='utf-8') as f:
        for l in f:
            if not l.strip():
                continue
            r = json.loads(l)
            iid = str(r.get('imageId', '') or '')
            if not iid or iid == '0':
                continue
            name = r.get('nameTn') or r.get('nameCn') or r.get('nameKr') or str(r['ID'])
            by.setdefault(iid, []).append((r['ID'], name))
    for v in by.values():
        v.sort()
    return by


def _uniq(seq):
    return list(dict.fromkeys(seq))


def read_index(out=OUT):
    """讀 index.tsv → [{imageId, bundle, w, h, ids, names}]；沒有索引回 None"""
    p = os.path.join(out, 'index.tsv')
    if not os.path.exists(p):
        return None
    rows = []
    with open(p, encoding='utf-8') as f:
        next(f)
        for l in f:
            c = l.rstrip('\n').split('\t')
            rows.append({'imageId': c[0], 'bundle': c[1], 'w': int(c[2]), 'h': int(c[3]),
                         'ids': [x for x in c[5].split(',') if x], 'names': [x for x in c[6].split('、') if x]})
    return rows


def find(key, out=OUT):
    """查索引：繁中名子字串、imageId、道具 ID → (有圖 rows, 缺圖 rows)；沒索引回 None"""
    rows = read_index(out)
    if rows is None:
        return None
    hit = [r for r in rows if key == r['imageId'] or key in r['ids'] or any(key in n for n in r['names'])]
    miss = []
    p = os.path.join(out, 'missing.tsv')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            next(f)
            for l in f:
                c = l.rstrip('\n').split('\t')
                if key == c[0] or key in c[1].split(',') or key in c[2]:
                    miss.append(c)
    return hit, miss


def print_find(key):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    res = find(key)
    if res is None:
        print('找不到索引，先執行：uv run --no-project --with UnityPy python tools/extract/item_images.py')
        return 1
    hit, miss = res
    if not hit and not miss:
        print('查無道具圖：' + key)
        return 2
    for r in hit:
        print('imageId=%s  %dx%d  %s  同圖 %d 個名字：%s' % (r['imageId'], r['w'], r['h'], r['bundle'],
                                                       len(r['names']), '、'.join(r['names'][:20]) + ('…' if len(r['names']) > 20 else '')))
        print('  ' + os.path.join(OUT, r['imageId'] + '.png'))
    for c in miss:
        print('imageId=%s  缺圖（bundle 裡沒有）：%s' % (c[0], c[2]))
    return 0


def export(dry=False):
    import UnityPy
    sys.path.insert(0, HERE)
    from extract import bundle_bytes
    paths = sorted(glob.glob(os.path.join(AB, 'itemalt*.assetbundle')))
    if not paths:
        print('找不到 itemalt*.assetbundle：' + AB)
        return 1
    by = items()
    sprites, mt = {}, {}
    for p in paths:
        bn = os.path.basename(p)[:-len('.assetbundle')]
        mt[bn] = os.stat(p).st_mtime_ns
        env = UnityPy.load(bundle_bytes(p))
        for o in env.objects:
            if o.type.name == 'Sprite':
                s = o.read()
                sprites.setdefault(s.m_Name, (bn, s))      # 同名只取第一個（bundle 名排序）
    if not dry:
        os.makedirs(OUT, exist_ok=True)
    rows, sizes = [], {}
    for iid, (bn, s) in sorted(sprites.items(), key=lambda kv: (len(kv[0]), kv[0])):
        img = s.image
        w, h = img.size
        sizes[(w, h)] = sizes.get((w, h), 0) + 1
        if not dry:
            b = io.BytesIO()
            img.save(b, 'PNG')
            with open(os.path.join(OUT, iid + '.png'), 'wb') as f:
                f.write(b.getvalue())
        its = by.get(iid, [])
        rows.append([iid, bn, str(w), str(h), str(len(its)), ','.join(str(i) for i, _ in its),
                     '、'.join(_uniq(n for _, n in its))])
    missing = [[iid, ','.join(str(i) for i, _ in v), '、'.join(_uniq(n for _, n in v))]
               for iid, v in sorted(by.items(), key=lambda kv: (len(kv[0]), kv[0])) if iid not in sprites]
    covered = sum(1 for iid in by if iid in sprites)
    orphan = sum(1 for r in rows if r[4] == '0')
    meta = {'sprites': len(sprites), 'item_imageIds': len(by), 'covered': covered, 'missing_imageIds': len(missing),
            'missing_items': sum(len(by[m[0]]) for m in missing), 'orphan_sprites': orphan,
            'sizes': {'%dx%d' % k: v for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])}, 'bundles': mt}
    if not dry:
        with open(os.path.join(OUT, 'index.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('imageId\tbundle\tw\th\tn_items\titem_ids\tnames\n')
            for r in rows:
                f.write('\t'.join(r) + '\n')
        with open(os.path.join(OUT, 'missing.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('imageId\titem_ids\tnames\n')
            for r in missing:
                f.write('\t'.join(r) + '\n')
        with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    print('Sprite %d 張（%s）；Item imageId %d 種，有圖 %d、缺 %d（影響 %d 個道具）；不屬於道具的 Sprite %d 張；%s%s'
          % (len(sprites), '、'.join('%s×%d' % kv for kv in list(meta['sizes'].items())[:4]), len(by), covered,
             len(missing), meta['missing_items'], orphan, '（dry-run 未寫檔）' if dry else '輸出 ', '' if dry else OUT))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='匯出道具圖示 Sprite → tools/.cache/item-images/')
    ap.add_argument('--find', help='只查索引：名稱子字串 / imageId / 道具 ID')
    ap.add_argument('--dry-run', action='store_true', help='只統計不寫檔')
    a = ap.parse_args()
    sys.exit(print_find(a.find) if a.find else export(a.dry_run))
