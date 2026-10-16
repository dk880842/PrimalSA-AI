#!/usr/bin/env python3
"""答題介面（UInpcanswerScreen，npcanswer）的合成模擬圖：從 GameClient UI assetbundle **唯讀**抽 prefab 版面與 sprite，
依 RectTransform 規則算出 1440×830 截圖上的位置，畫成 PNG（tools/.cache/npcanswer-extract/）給 screen_sigs.quiz_screen 選點 / 離線測試。

為什麼要合成：答題 / 防腳本驗證視窗沒有任何實機截圖（猜謎三兄弟不會再跑到答題），只能照遊戲自己的 prefab 推。
  - prefab：uiuinpcanswer_yhkrn.assetbundle（自帶 sprite 圖集；uinpcanswer_yhkrn 版面相同、sprite 在相依圖集）
  - 版面：ImgBg 741.1×431.6（錨點右下 (-668.8, 366)）、CommonPopupBg（bg_2 九宮格 + bg_title_2 標題板 + btn_close）、
    img_beijing 底板、Content（HorizontalLayoutGroup，間距 0、強制展開 → 每格 680.1/4 寬）放 4 張 bg_qh_stone 選項卡（163×231.7）、
    btn_1 藍「確認」鈕；UINPCAnswerCtrl enableMask=1、maskCol 黑 α0.6 → 背景整片壓暗成 ×0.4
  - 畫布比例 k：用 2026-10-09 爬塔實測的點擊座標（選項 463 / 643 / 822 / 1002, 430、確認 735, 610，notes/quest-log.md）
    反推 k ≈ 1.0546（選項中心 = 1440 − 926.35k、間距 170.03k；確認鈕 y = 830 − 209.6k，三者一致）；
    同 k 套到 UIConfirmMsgBox（461.5 寬）≈ 487 px，實機「提示」框量到約 483 px，誤差在邊緣陰影內
  - 選項圖：Answer 6～10 那組（洛克斯系 100916～100919）的全身靜態圖（tools/.cache/pet-images/static，沒有就畫灰塊）

用法（需要 UnityPy，它會帶 Pillow；只讀 GameClient，輸出寫 tools/.cache/）：
  uv run --no-project --with UnityPy python tools/extract/uimock.py [--out tools/.cache/npcanswer-extract]
輸出：mock_<背景>_k<比例>_<位移>.png（多種背景 / 比例 / 位移，給特徵容差測試）與 layout.json（各元件的截圖座標）。
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from extract import bundle_bytes  # noqa: E402

if not (ROOT / 'GameClient').exists():           # git worktree（.claude/worktrees/…）裡沒有 GameClient / tools/.cache：用主工作樹的
    for up in ROOT.parents:
        if (up / 'GameClient').exists():
            ROOT = up
            break
AB = ROOT / 'GameClient' / 'PrimalSA_Data' / 'StreamingAssets' / 'AssetBundles'
BUNDLE = 'uiuinpcanswer_yhkrn.assetbundle'
CACHE = ROOT / 'tools' / '.cache'
SW, SH = 1440, 830
K_FIT = 1.0546                      # 由 10-09 實測點擊座標反推的畫布比例（見檔頭）
MASK_A = 0.6                        # UINPCAnswerCtrl.maskCol 黑 α
PETS = ('100916', '100917', '100918', '100919')   # Answer 6～10 的四張選項圖
# 背景：tools/.cache 既有實機截圖（主畫面 / 戰鬥 / 洞窟 / 村莊）；不存在的略過
BACKS = {'field': 'net1.png', 'village': 'kr322.png', 'battle': 'battle-samples/vs_9.png', 'idle': 'watch-m0/s1.png'}


def load_prefab():
    """→ (rect 樹 {pathid: dict}, sprites {name: (PIL.Image, border)})"""
    import UnityPy
    env = UnityPy.load(bundle_bytes(AB / BUNDLE))
    objs = {o.path_id: o for o in env.objects}
    sprites = {}
    for o in env.objects:
        if o.type.name == 'Sprite':
            d = o.read()
            b = o.read_typetree().get('m_Border') or {}
            sprites.setdefault(d.m_Name, (d.image.convert('RGBA'), (b.get('x', 0), b.get('y', 0), b.get('z', 0), b.get('w', 0))))
    nodes = {}
    for o in env.objects:
        if o.type.name != 'RectTransform':
            continue
        t = o.read_typetree()
        go = objs[t['m_GameObject']['m_PathID']].read_typetree()
        info = {'name': go['m_Name'], 'active': bool(go['m_IsActive']), 'father': t['m_Father']['m_PathID'],
                'children': [c['m_PathID'] for c in t['m_Children']],
                'amin': (t['m_AnchorMin']['x'], t['m_AnchorMin']['y']), 'amax': (t['m_AnchorMax']['x'], t['m_AnchorMax']['y']),
                'pos': (t['m_AnchoredPosition']['x'], t['m_AnchoredPosition']['y']), 'size': (t['m_SizeDelta']['x'], t['m_SizeDelta']['y']),
                'pivot': (t['m_Pivot']['x'], t['m_Pivot']['y']), 'sprite': None, 'text': None}
        for c in go['m_Component']:
            co = objs.get(c['component']['m_PathID'])
            if co is None or co.type.name != 'MonoBehaviour':
                continue
            ct = co.read_typetree()
            if 'm_Sprite' in ct:
                sp = objs.get(ct['m_Sprite']['m_PathID'])
                info['sprite'] = sp.read().m_Name if sp else None
            if 'm_fontColor' in ct:
                fc = ct['m_fontColor']
                info['text'] = {'size': ct.get('m_fontSize', 20), 'color': tuple(round(fc[k] * 255) for k in 'rgb')}
        nodes[o.path_id] = info
    return nodes, sprites


def resolve(nodes, W, H):
    """RectTransform → 畫布座標 (x0, y0, x1, y1)，y 往上（Unity 慣例）。根 = 全畫布"""
    rects = {}

    def go(pid, parent):
        n = nodes[pid]
        px0, py0, px1, py1 = parent
        pw, ph = px1 - px0, py1 - py0
        ax0, ay0 = px0 + n['amin'][0] * pw, py0 + n['amin'][1] * ph
        ax1, ay1 = px0 + n['amax'][0] * pw, py0 + n['amax'][1] * ph
        w, h = ax1 - ax0 + n['size'][0], ay1 - ay0 + n['size'][1]
        cx = ax0 + (ax1 - ax0) * n['pivot'][0] + n['pos'][0]
        cy = ay0 + (ay1 - ay0) * n['pivot'][1] + n['pos'][1]
        r = (cx - n['pivot'][0] * w, cy - n['pivot'][1] * h, cx - n['pivot'][0] * w + w, cy - n['pivot'][1] * h + h)
        rects[pid] = r
        for c in n['children']:
            go(c, r)

    for pid, n in nodes.items():
        if n['father'] == 0:
            go(pid, (0, 0, W, H))
    return rects


def to_screen(r, k):
    """畫布 rect（y 往上）→ 截圖 rect（x0, y0, x1, y1，y 往下）"""
    x0, y0, x1, y1 = r
    return (x0 * k, SH - y1 * k, x1 * k, SH - y0 * k)


def sliced(img, border, w, h, k):
    """Unity 九宮格（border = L, B, R, T sprite px；邊框按 k 縮放、中段拉伸）"""
    from PIL import Image
    L, B, R, T = (round(v) for v in border)
    sw, sh = img.size
    if not any((L, B, R, T)):
        return img.resize((max(1, round(w)), max(1, round(h))), Image.BILINEAR)
    w, h = max(1, round(w)), max(1, round(h))
    kl, kr, kt, kb = round(L * k), round(R * k), round(T * k), round(B * k)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    xs_src, xs_dst = [0, L, sw - R, sw], [0, kl, w - kr, w]
    ys_src, ys_dst = [0, T, sh - B, sh], [0, kt, h - kb, h]
    for i in range(3):
        for j in range(3):
            sx0, sx1, dx0, dx1 = xs_src[i], xs_src[i + 1], xs_dst[i], xs_dst[i + 1]
            sy0, sy1, dy0, dy1 = ys_src[j], ys_src[j + 1], ys_dst[j], ys_dst[j + 1]
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            out.alpha_composite(img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR), (dx0, dy0))
    return out


def font(px):
    from PIL import ImageFont
    for p in ('/mnt/c/Windows/Fonts/msjh.ttc', 'C:/Windows/Fonts/msjh.ttc', '/mnt/c/Windows/Fonts/mingliu.ttc'):
        try:
            return ImageFont.truetype(p, max(8, round(px)))
        except OSError:
            continue
    return None


def pet_image(pid):
    from PIL import Image
    d = CACHE / 'pet-images' / 'static'
    for f in sorted(d.glob(f'*_{pid}.png')) if d.exists() else []:
        return Image.open(f).convert('RGBA')
    return Image.new('RGBA', (120, 160), (120, 120, 120, 255))


def render(nodes, sprites, k, back, shift=(0, 0)):
    """畫一張答題介面（背景 back 壓暗 ×0.4 + 彈窗）。回 (PIL.Image RGB, layout dict 截圖座標)"""
    from PIL import Image, ImageDraw
    W, H = SW / k, SH / k
    rects = resolve(nodes, W, H)
    canvas = back.convert('RGBA').resize((SW, SH))
    canvas = Image.blend(canvas, Image.new('RGBA', (SW, SH), (0, 0, 0, 255)), MASK_A)
    byname = {}
    for pid, n in nodes.items():
        byname.setdefault(n['name'], []).append(pid)
    layout = {}
    dx, dy = shift

    def scr(pid):
        x0, y0, x1, y1 = to_screen(rects[pid], k)
        return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    def draw_node(pid, rect=None):
        n = nodes[pid]
        if not n['active']:
            return
        r = rect or scr(pid)
        if n['sprite'] and n['sprite'] in sprites and n['name'] != 'icon':
            img, border = sprites[n['sprite']]
            im = sliced(img, border, r[2] - r[0], r[3] - r[1], k)
            canvas.alpha_composite(im, (round(r[0]), round(r[1])))
        layout.setdefault(n['name'], []).append([round(v, 1) for v in r])

    root = next(p for p, n in nodes.items() if n['father'] == 0)
    item = next(p for p, n in nodes.items() if n['name'] == '6')
    content = next(p for p, n in nodes.items() if n['name'] == 'Content')

    def walk(pid):
        n = nodes[pid]
        if pid == item:                      # 範本卡不畫（執行時複製到 Content）
            return
        draw_node(pid)
        for c in n['children']:
            walk(c)

    walk(root)
    # 4 張選項卡：HorizontalLayoutGroup（間距 0、強制展開寬、不控制子物件大小、左上對齊）→ 每格寬 = Content 寬 / 4，卡片貼格左上
    cx0, cy0, cx1, cy1 = scr(content)
    slot = (cx1 - cx0) / 4
    iw, ih = nodes[item]['size'][0] * k, nodes[item]['size'][1] * k
    d = ImageDraw.Draw(canvas)
    f20 = font(20 * k)
    for i in range(4):
        r = (cx0 + i * slot, cy0, cx0 + i * slot + iw, cy0 + ih)
        img, border = sprites[nodes[item]['sprite']]
        canvas.alpha_composite(sliced(img, border, iw, ih, k), (round(r[0]), round(r[1])))
        layout.setdefault('card', []).append([round(v, 1) for v in r])
        pet = pet_image(PETS[i])
        bw, bh = 148.5 * k, 192.1 * k * 0.9          # 選項圖放在內容區（txtContent 148.5×192.1）內、等比縮放置中
        s = min(bw / pet.width, bh / pet.height)
        pm = pet.resize((max(1, round(pet.width * s)), max(1, round(pet.height * s))))
        ccx, ccy = (r[0] + r[2]) / 2 - 0.5 * k, (r[1] + r[3]) / 2 + 11.4 * k
        canvas.alpha_composite(pm, (round(ccx - pm.width / 2), round(ccy - pm.height / 2)))
        if f20:
            d.text((r[0] + (iw / 2 - 67.8 * k), (r[1] + r[3]) / 2 - 104 * k), 'ABCD'[i], font=f20, fill=(255, 255, 255))
    if f20:
        t = scr(byname['name'][0])
        d.text(((t[0] + t[2]) / 2, (t[1] + t[3]) / 2), '以下哪只寵物的名字叫做“諾克斯”', font=f20, fill=(255, 255, 255), anchor='mm')
        for pid in byname.get('Tmp', []):
            fa = nodes[nodes[pid]['father']]['name'] if nodes[pid]['father'] in nodes else ''
            if fa == '5':
                t = scr(nodes[pid]['father'])
                d.text(((t[0] + t[2]) / 2, (t[1] + t[3]) / 2), '確認', font=font(26 * k), fill=(216, 248, 255), anchor='mm')
            elif fa == 'CommonPopupBg':
                t = scr(pid)
                d.text(((t[0] + t[2]) / 2, (t[1] + t[3]) / 2), '知識答題', font=font(32 * k), fill=(226, 182, 130), anchor='mm')
    return canvas.convert('RGB'), layout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='答題介面合成模擬圖（唯讀 GameClient，輸出到 tools/.cache）')
    ap.add_argument('--out', default=str(CACHE / 'npcanswer-extract'))
    a = ap.parse_args(argv)
    from PIL import Image
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    nodes, sprites = load_prefab()
    made = []
    for bname, rel in BACKS.items():
        p = CACHE / rel
        if not p.exists():
            continue
        back = Image.open(p)
        for k in (1.0466, K_FIT, 1.062):
            for shift in ((0, 0), (6, -5), (-6, 5)):
                if k != K_FIT and shift != (0, 0):
                    continue
                img, lay = render(nodes, sprites, k, back, shift)
                name = f'mock_{bname}_k{round(k * 10000)}_{shift[0]:+d}{shift[1]:+d}.png'
                img.save(out / name)
                made.append(name)
                if bname == 'field' and k == K_FIT and shift == (0, 0):
                    (out / 'layout.json').write_text(json.dumps(lay, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'寫入 {len(made)} 張到 {out}')
    for n in made:
        print(' ', n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
