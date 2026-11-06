#!/usr/bin/env python3
"""手册自检：链接 / 置信一致性 / 卡数 / 占位符 / Mermaid 图。
用法：python3 -I scripts/verify_handbook.py
退出码：0 全过，1 有问题。
"""
import re, os, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

errors, warns = [], []

# 1. 内部链接（先剔除行内代码与围栏代码块，避免把示例当成真链接）
def strip_code(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    return re.sub(r'`[^`]*`', '', text)

for f in glob.glob('books/*.md') + glob.glob('cards/*.md'):
    base = os.path.dirname(f)
    for m in re.finditer(r'\]\(([^)#]+\.md)(?:#[^)]*)?\)', strip_code(open(f, encoding='utf-8').read())):
        t = m.group(1)
        if t.startswith('http'):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(base, t))):
            errors.append(f'断链: {f} -> {t}')

# 2. 置信级一致性：卡内 vs 速查单页
idx = open('books/速查单页.md', encoding='utf-8').read()
groups = {}
for lvl in ['高', '中高', '中']:
    m = re.search(r'\|\s*\*\*' + lvl + r'\*\*\s*\|([^|]+)\|', idx)
    if m:
        groups[lvl] = re.findall(r'(\d{2})\s', m.group(1) + ' ')
for f in sorted(glob.glob('cards/*.md')):
    num = os.path.basename(f)[:2]
    m = re.search(r'\*\*置信级\*\*[：:]\s*\*{0,2}(高|中高|中|低)',
                  open(f, encoding='utf-8').read())
    actual = m.group(1) if m else '?'
    listed = next((k for k, v in groups.items() if num in v), None)
    if actual != listed:
        errors.append(f'置信不一致: 卡 {num} 卡内={actual} 索引={listed}')

# 3. 卡数声明
declared = re.search(r'cards/\s*(\d+)\s*张', idx)
actual_n = len(glob.glob('cards/*.md'))
if declared and int(declared.group(1)) != actual_n:
    errors.append(f'卡数不符: 声明 {declared.group(1)}，实际 {actual_n}')

# 4. 真占位符（排除代码、引号引用、以及"描述要找占位符"的说明行）
PLACEHOLDER = re.compile(r'\b(TBD|FIXME|XXX)\b|待补充|待填写')
DESCRIBING = re.compile(r'找占位符|占位符与遗漏|清理.{0,6}占位|占位符扫描')
for f in glob.glob('books/*.md') + glob.glob('cards/*.md'):
    for i, line in enumerate(open(f, encoding='utf-8'), 1):
        stripped = re.sub(r'`[^`]*`', '', line)
        stripped = re.sub(r'[""][^""]*[""]', '', stripped)
        if DESCRIBING.search(stripped):
            continue
        if PLACEHOLDER.search(stripped):
            errors.append(f'占位符: {f}:{i}')

# 5. Mermaid 图结构
for f in glob.glob('books/*.md'):
    text = open(f, encoding='utf-8').read()
    for bi, b in enumerate(re.findall(r'```mermaid\n(.*?)```', text, re.S), 1):
        defs = set(re.findall(r'^\s*([A-Za-z][\w]*)\s*[\[\(\{]', b, re.M))
        edges = re.findall(r'([A-Za-z][\w]*)\s*-->(?:\|[^|]*\|)?\s*([A-Za-z][\w]*)', b)
        used = {x for e in edges for x in e}
        cls_def = set(re.findall(r'^\s*classDef\s+(\w+)', b, re.M))
        cls_use = set(re.findall(r':::\s*(\w+)', b))
        tag = f'{f} 图{bi}'
        if used - defs: errors.append(f'{tag}: 未定义节点 {sorted(used-defs)}')
        if defs - used: errors.append(f'{tag}: 未使用节点 {sorted(defs-used)}')
        if cls_use - cls_def: errors.append(f'{tag}: 未定义样式 {sorted(cls_use-cls_def)}')
        if len(defs) > 20: errors.append(f'{tag}: 节点 {len(defs)} > 20')

# 6. 不予发布的卡不应出现在 cards/
for banned in ['09', '11']:
    if glob.glob(f'cards/{banned}-*.md'):
        errors.append(f'不予发布的卡 {banned} 仍在 cards/')

# 报告
print(f'检查完成：{actual_n} 张卡，{len(glob.glob("books/*.md"))} 个 book 文件\n')
if warns:
    print('警告:')
    for w in warns: print(f'  ⚠️  {w}')
if errors:
    print('错误:')
    for e in errors: print(f'  ❌ {e}')
    print(f'\n共 {len(errors)} 个问题')
    sys.exit(1)
print('全部通过 ✅')
sys.exit(0)
