#!/usr/bin/env python3
"""紀錄檔路徑的測試轉向（只用標準函式庫）：設環境變數 PSA_LOG_DIR 後，actions.log / errlog.jsonl / quest-events.log /
quest-log.md / 各 *.json 進度檔都改寫到該資料夾（同檔名），真正的紀錄不會被離線測試污染。
各模組在定義紀錄路徑處包一層：LOG = logpaths.p(真正路徑)。測試檔第一行 import testenv 就會設好暫存資料夾。"""
import os
from pathlib import Path


def p(real: Path) -> Path:
    d = os.environ.get('PSA_LOG_DIR')
    return Path(d) / Path(real).name if d else Path(real)
