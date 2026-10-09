# -*- coding: utf-8 -*-
"""Tabtoy v3 二進位設定表解析（configs.assetbundle 內的 TextAsset `Configs`）

格式：
  檔頭：string "TABTOY"（int32 長度前綴）、int32 版本、string md5
  之後都是 uint32 tag + 值；tag = (型別<<16) | 欄位索引
  型別：0=陣列數量標記(略過) 1=int32 8=enum(int32) 2=int64 5=float 7=bool(1 byte)
        6=string(int32 長度+UTF8) 9=struct / 10=表的列（int32 長度 + 內容，遞迴解析）
  最上層每筆 0xa00NN 是第 NN 張表的一列；表名 / 欄位名來自 schema.tsv（由 HotUpdate.dll 產生）
"""
import struct, re, collections, os

def parse_tabtoy(b):
    u32 = lambda p: struct.unpack_from('<I', b, p)[0]

    def parse(p, end):
        fields = []
        while p < end:
            t = u32(p); typ = t >> 16; idx = t & 0xffff; p += 4
            if typ == 0:
                continue
            if typ in (1, 8):   v = struct.unpack_from('<i', b, p)[0]; p += 4
            elif typ == 2:      v = struct.unpack_from('<q', b, p)[0]; p += 8
            elif typ == 5:      v = round(struct.unpack_from('<f', b, p)[0], 4); p += 4
            elif typ == 7:      v = b[p]; p += 1
            elif typ == 6:
                n = u32(p); v = b[p+4:p+4+n].decode('utf-8', 'replace'); p += 4 + n
            elif typ in (9, 10):
                n = u32(p); v = parse(p+4, p+4+n); p += 4 + n
            else:
                raise ValueError('未知欄位型別 %d @%x' % (typ, p-4))
            fields.append((idx, typ, v))
        return fields

    p = 0
    n = u32(p); assert b[p+4:p+4+n] == b'TABTOY'; p += 4 + n
    p += 4                      # 版本
    n = u32(p); p += 4 + n      # md5
    return parse(p, len(b))

def load_schema(path):
    """schema.tsv：類別 \t tag \t 欄位名|型別 \t 讀取方法"""
    sch = collections.defaultdict(dict)
    for line in open(path, encoding='utf-8-sig'):
        parts = line.rstrip('\r\n').split('\t')
        if len(parts) < 3: continue
        cls, tag, fld = parts[0], parts[1], parts[2]
        name, ftype = fld.split('|', 1)
        islist = ftype.startswith('System.Collections.Generic.List')
        inner = re.search(r'<(.+)>', ftype).group(1) if islist else ftype
        sch[cls][int(tag, 16)] = (name, islist, inner)
    return sch

def tables(raw, schema_path):
    sch = load_schema(schema_path)

    def conv(cls, fields):
        o = {}; s = sch.get(cls, {})
        for idx, typ, v in fields:
            name, islist, inner = s.get((typ << 16) | idx, ('f%d_%d' % (typ, idx), False, ''))
            if typ in (9, 10): v = conv(inner, v)
            if islist: o.setdefault(name, []).append(v)
            else: o[name] = v
        return o

    out = collections.OrderedDict()
    s = sch['Data.Configs']
    for idx, typ, v in parse_tabtoy(raw):
        key = (typ << 16) | idx
        if key not in s: continue
        name, _, inner = s[key]
        out.setdefault(name, []).append(conv(inner, v))
    return out
