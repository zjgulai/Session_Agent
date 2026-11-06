#!/usr/bin/env python3
"""发布前敏感数据扫描（卡 17 默认拒绝的自动化）。
用法：python3 -I scripts/prepublish_scan.py [目标目录，默认整个项目]
退出码：0 干净，1 有阻断项。
默认排除 _raw/ 与 _archive/（原始语料永不发布）。
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = sys.argv[1] if len(sys.argv) > 1 else ROOT
EXCLUDE_DIRS = {'_raw', '_archive', '.git', '__pycache__', 'node_modules'}

# 说明（2026-11-06 实测校准）：
# - sk- 前缀极易误报（sk-1-import / sk-2-fi-package 等路径），要求长度 ≥40 且高熵
# - 私钥块常出现在"禁止导出"的规则文本里 → 降为 warn
# - JWT 可能是公开资源的临时签名 URL（已过期）→ 降为 warn
_PATHS = ('import', 'export', 'package', 'exec', 'agent', 'report', 'brief',
          'round', 'review', 'implement', 'migration', 'celery')

def _real_sk(m):
    v = m.group(0)
    if len(v) < 40:
        return False
    if any(p in v for p in _PATHS):
        return False
    return len(set(v[3:])) > 15

PATTERNS = [
    ('GitHub PAT',         re.compile(r'ghp_[A-Za-z0-9]{36}'),                     'block'),
    ('GitHub fine-grained', re.compile(r'github_pat_[A-Za-z0-9_]{82}'),            'block'),
    ('API key (sk-)',      re.compile(r'sk-[A-Za-z0-9_-]{20,}'),                   'block'),
    ('AWS key',            re.compile(r'AKIA[0-9A-Z]{16}'),                        'block'),
    ('Stripe key',         re.compile(r'sk_(?:live|test)_[A-Za-z0-9]{20,}'),       'block'),
    ('私钥块',             re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'), 'warn'),
    ('JWT',                re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}'), 'warn'),
    ('邮箱',               re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), 'warn'),
    ('本地绝对路径',        re.compile(r'/Users/[A-Za-z0-9_.-]+/'),                 'warn'),
    ('内网 IP',            re.compile(r'\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+\b'), 'warn'),
]

def mask(m):
    s = m.group(0)
    return s[:6] + '…[脱敏]' if len(s) > 10 else s

def iter_files():
    if os.path.isfile(TARGET):
        yield TARGET
        return
    for dirpath, dirnames, filenames in os.walk(TARGET):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            yield os.path.join(dirpath, fn)

def scan():
    hits = {'block': [], 'warn': []}
    for p in iter_files():
        base = TARGET
        try:
            # 流式逐行读取，不因文件大而跳过（大文件恰恰最可能含凭据）
            with open(p, encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    for name, rx, level in PATTERNS:
                        for m in rx.finditer(line):
                            if name == 'API key (sk-)' and not _real_sk(m):
                                continue
                            hits[level].append((name, os.path.relpath(p, base), mask(m)))
        except Exception:
            continue
    return hits

hits = scan()
print(f'扫描目标：{TARGET}\n排除目录：{sorted(EXCLUDE_DIRS)}\n')

if hits['warn']:
    # 按类型聚合，避免刷屏
    from collections import Counter
    c = Counter((n, f) for n, f, _ in hits['warn'])
    print(f'警告（{len(hits["warn"])} 处）：')
    for (name, f), n in c.most_common(20):
        print(f'  ⚠️  {name:<12} {f}  ×{n}')
    print()

if hits['block']:
    print(f'阻断（{len(hits["block"])} 处）：')
    from collections import Counter
    c = Counter((n, f) for n, f, _ in hits['block'])
    for (name, f), n in c.most_common(20):
        print(f'  🔴 {name:<12} {f}  ×{n}')
    print('\n结论：❌ 阻断发布。任一阻断项命中即整体拒绝（卡 17 fail-closed）。')
    sys.exit(1)

print('结论：✅ 无阻断项' + ('（有警告，需人工确认）' if hits['warn'] else '，可发布'))
sys.exit(0)
