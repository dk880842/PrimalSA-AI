#!/usr/bin/env python3
"""離線測試共用：import 這個模組就把所有紀錄檔（actions.log / errlog / quest-events.log / quest-log.md / 進度檔）
轉向暫存資料夾（logpaths.p）。必須在 import 其他 tools/gui 模組之前（各測試檔的第一個專案 import）。"""
import os
import tempfile

os.environ['PSA_LOG_DIR'] = tempfile.mkdtemp(prefix='psatest-')
# 樣板模組（petmatch / titlematch / questdetail…）依 layout.tpl_key() 選樣板檔；離線測試一律當 2880×1659、不問遊戲（測試要別的版面自己改 layout 函式）
os.environ.setdefault('PSA_LAYOUT', '2880x1659')
