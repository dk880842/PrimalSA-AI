#!/usr/bin/env python3
"""離線測試共用：import 這個模組就把所有紀錄檔（actions.log / errlog / quest-events.log / quest-log.md / 進度檔）
轉向暫存資料夾（logpaths.p）。必須在 import 其他 tools/gui 模組之前（各測試檔的第一個專案 import）。"""
import os
import tempfile

os.environ['PSA_LOG_DIR'] = tempfile.mkdtemp(prefix='psatest-')
