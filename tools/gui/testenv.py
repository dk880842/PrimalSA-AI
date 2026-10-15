#!/usr/bin/env python3
"""離線測試共用：import 這個模組就把所有紀錄檔（actions.log / errlog / quest-events.log / quest-log.md / 進度檔 / verify-halt.json）
轉向暫存資料夾（logpaths.p）。必須在 import 其他 tools/gui 模組之前（各測試檔的第一個專案 import）。
另外把「正在執行的遊戲程序」固定成單一主視窗（clients.running 讀 PSA_TEST_PROCS，不呼叫 powershell）、帳號對照設定檔固定成「沒有」（PSA_ACCOUNTS_FILE）；
要測多視窗的測試自己改 os.environ['PSA_TEST_PROCS']。"""
import os
import tempfile

os.environ['PSA_LOG_DIR'] = tempfile.mkdtemp(prefix='psatest-')
os.environ.setdefault('PSA_TEST_PROCS', 'PrimalSA')
# 帳號對照設定檔（accounts.py）一律指到不存在的檔 = 沒設定檔：本機真的 accounts.local.json 不影響離線測試；要測的測試自己改 PSA_ACCOUNTS_FILE
os.environ['PSA_ACCOUNTS_FILE'] = os.path.join(os.environ['PSA_LOG_DIR'], 'accounts-none.json')
