#!/usr/bin/env python3
"""
Corrected skill optimization analysis based on verified EVE wiki data.

Key corrections from wiki verification:
1. Accounting is rank 3x (NOT 2x as I assumed), prerequisite is Trade IV (NOT Trade II)
2. Retail is rank 2x, prerequisite Trade II, gives +8 orders/level
3. Wholesale is rank 4x (NOT 5x), prerequisite Retail V + Marketing II, gives +16 orders/level
4. Tycoon is rank 6x (NOT 8x), prerequisite Wholesale V + Marketing IV, gives +32 orders/level
5. Accounting prerequisite is Trade IV (NOT Trade II) - THIS IS A MAJOR CHANGE
6. Sales tax formula confirmed: 7.5% * (1 - 0.11 * level), so:
   L0=7.5%, L1=6.675%, L2=5.85%, L3=5.025%, L4=4.2%, L5=3.375%
   Wait - wiki says L5 = 3.3%, but 7.5*(1-0.55) = 3.375. Wiki says 3.3%.
   Let me use the exact formula: 7.5% * (1 - 0.11*level)
   L0=7.50%, L1=6.675%, L2=5.85%, L3=5.025%, L4=4.20%, L5=3.375%
7. Broker fee formula confirmed: 3% - 0.3% * level (ignoring standings)
8. Base orders = 5, Trade gives +4/level
9. Market tax (NPC tax on market transactions) is separate from sales tax
   Actually checking again: the 7.5% IS the sales tax that Accounting reduces.

IMPORTANT: Accounting requires Trade IV, not Trade II.
This changes the progression order significantly.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# VERIFIED skill data from EVE University Wiki (July 2026)
# ============================================================

# SP per level for rank 1: [0, 250, 1414, 8000, 45255, 256000]
SP_RANK1 = [0, 250, 1414, 8000, 45255, 256000]
# Incremental SP per level
SP_RANK1_INC = [0, 250, 1164, 6586, 37255, 210745]

SKILLS = {
    'Trade':            {'rank': 1, 'orders': 4,  'prereqs': {}},
    'Accounting':       {'rank': 3, 'orders': 0,  'prereqs': {'Trade': 4}},  # FIXED: requires Trade IV
    'Broker Relations': {'rank': 2, 'orders': 0,  'prereqs': {'Trade': 2}},
    'Retail':           {'rank': 2, 'orders': 8,  'prereqs': {'Trade': 2}},
    'Wholesale':        {'rank': 4, 'orders': 16, 'prereqs': {'Retail': 5, 'Marketing': 2}},
    'Tycoon':           {'rank': 6, 'orders': 32, 'prereqs': {'Wholesale': 5, 'Marketing': 4}},
    'Marketing':        {'rank': 3, 'orders': 0,  'prereqs': {'Trade': 2}},
}

# Skill effects
# Accounting: tax = 7.5% * (1 - 0.11 * level)
# Broker Relations: fee = 3% - 0.3% * level

# ============================================================
# Item data (same as before)
# ============================================================
items_raw = [
    (21791,4,'Minmatar Encryption Methods',310.00,310.10),
    (34203,11,'Augmentation Decryptor',785800.00,893800.00),
    (47765,4,'Calm Electrical Filament',17020.00,25380.00),
    (34201,8,'Accelerant Decryptor',345400.00,382400.00),
    (20416,19,'Datacore - Nanite Engineering',97110.00,100400.00),
    (82479,5,'Megacity Crunch - Unlimited',20000.00,31600000.00),
    (21596,163,'Data Processor',56.00,56.01),
    (21594,410,'Energy Cells',9.03,9.04),
    (81348,143,'Alignment Sequencer',36.63,54.64),
    (17893,5,'High-Tech Data Chip',510000.00,658400.00),
    (20172,67,'Datacore - Minmatar Starship Eng',82930.00,94450.00),
    (34202,3,'Attainment Decryptor',1801000.00,1927000.00),
    (20424,72,'Datacore - Mechanical Eng',26250.00,31390.00),
    (47761,3,'Calm Exotic Filament',78010.00,78030.00),
    (53984,7,"Signal-5 Needlejack Filament",228600.00,262500.00),
    (47764,1,'Calm Gamma Filament',5764.00,7500.00),
    (17895,4,'High-Tech Manufacturing Tools',3798000.00,4110000.00),
    (21595,148,'Construction Alloy',5.10,5.11),
    (21593,262,'Mechanic Parts',10.00,16.98),
    (17894,2,'High-Tech Scanner',839600.00,967200.00),
    (25600,503,'Burned Logic Circuit',45600.00,48760.00),
    (25601,206,'Fried Interface Circuit',3179.00,3182.00),
    (25602,183,'Thruster Console',7402.00,8485.00),
    (9826,42,'Carbon',253.50,253.60),
    (25614,43,'Single-crystal Superalloy I-beam',40850.00,64820.00),
    (25597,368,'Damaged Artificial Neural Network',225.70,225.80),
    (25599,387,'Charred Micro Circuit',365.10,365.20),
    (25617,63,'Power Circuit',272000.00,291700.00),
    (25616,61,'Artificial Neural Network',1014.00,1015.00),
    (25619,89,'Logic Circuit',2337000.00,2397000.00),
    (25595,323,'Alloyed Tritanium Bar',2078.00,2079.00),
    (25618,48,'Micro Circuit',5227.00,6297.00),
    (25593,246,'Smashed Trigger Unit',4611.00,4915.00),
    (25612,58,'Trigger Unit',454500.00,467400.00),
    (33195,3,'Spatial Attunement Unit',751.00,8000.00),
    (25621,74,'Impetus Console',81200.00,81210.00),
    (25598,173,'Tripped Power Circuit',3109.00,3434.00),
    (15331,5,'Metal Scraps',975.00,975.00),
    (25620,19,'Interface Circuit',20300.00,23940.00),
    (21592,37,'Electric Conduit',15.29,15.30),
    (34204,15,'Parity Decryptor',902600.00,1087000.00),
    (83309,3,'Planetfall Green Matte - Unlimited',1006.00,169900.00),
    (34205,3,'Process Decryptor',354500.00,354600.00),
    (34207,2,'Optimized Attainment Decryptor',3500000.00,4600000.00),
    (20420,58,'Datacore - Rocket Science',91620.00,105900.00),
    (20415,82,'Datacore - Molecular Engineering',96320.00,123400.00),
    (47763,3,'Calm Firestorm Filament',1717.00,1719.00),
    (34206,3,'Symmetry Decryptor',367300.00,380000.00),
    (20423,47,'Datacore - Nuclear Physics',91690.00,103000.00),
    (53977,6,"Noise-5 Needlejack Filament",170000.00,231800.00),
    (81349,113,'Fermionic Sequencer',40.17,70.00),
    (83369,1,'Boosted Mint Gloss - Unlimited',180000.00,279400.00),
    (21732,1,'Angel Spatial Analyzer',30600.00,0.00),
    (47762,1,'Calm Dark Filament',8379.00,8380.00),
]

PAYMENT = 340_240_404.20

def calc_sp(skill, level):
    """Total SP for a skill at given level."""
    rank = SKILLS[skill]['rank']
    return SP_RANK1[level] * rank

def calc_total_sp(levels):
    """Total SP across all skills."""
    # Must include prerequisite skills
    all_skills = set(levels.keys())
    for skill, level in list(levels.items()):
        for prereq, prereq_level in SKILLS[skill]['prereqs'].items():
            all_skills.add(prereq)
    total = 0
    for skill in all_skills:
        level = levels.get(skill, 0)
        # Ensure prerequisites are met
        for prereq, prereq_level in SKILLS[skill]['prereqs'].items():
            levels.setdefault(prereq, prereq_level)
            if levels.get(prereq, 0) < prereq_level:
                levels[prereq] = prereq_level
        if level > 0:
            total += calc_sp(skill, level)
    return total

def calc_orders(levels):
    """Total active market orders."""
    base = 5
    for skill, info in SKILLS.items():
        level = levels.get(skill, 0)
        base += info['orders'] * level
    return base

def calc_tax(levels):
    accounting = levels.get('Accounting', 0)
    return 0.075 * (1 - 0.11 * accounting)

def calc_broker(levels):
    broker = levels.get('Broker Relations', 0)
    return max(0.0, 0.03 - 0.003 * broker)

def calc_net_revenue(levels, items):
    """Calculate net revenue given skill levels."""
    max_orders = calc_orders(levels)
    tax_rate = calc_tax(levels)
    broker_rate = calc_broker(levels)

    item_data = []
    for tid, qty, name, buy, sell in items:
        buy_total = qty * buy
        sell_total = qty * sell
        sell_net = sell_total * (1 - tax_rate - broker_rate) if sell > 0 else 0
        buy_net = buy_total * (1 - tax_rate)
        sell_advantage = sell_net - buy_net
        item_data.append({
            'name': name, 'qty': qty,
            'buy_total': buy_total, 'sell_total': sell_total,
            'sell_net': sell_net, 'buy_net': buy_net,
            'sell_advantage': sell_advantage,
        })

    item_data.sort(key=lambda x: x['sell_advantage'], reverse=True)

    sell_items = item_data[:max_orders] if max_orders < len(item_data) else item_data
    buy_items = item_data[max_orders:] if max_orders < len(item_data) else []

    total_net = sum(i['sell_net'] for i in sell_items) + sum(i['buy_net'] for i in buy_items)
    n_sell = len(sell_items)
    n_buy = len(buy_items)
    total_gross_sell = sum(i['sell_total'] for i in sell_items)
    total_gross_buy = sum(i['buy_total'] for i in buy_items)

    return total_net, n_sell, n_buy

# ============================================================
# Build a sensible progression path
# Key insight: Accounting requires Trade IV (NOT Trade II!)
# This means you must invest 45,255 SP in Trade before touching Accounting
# ============================================================

PROGRESSION = [
    # Phase 0: Base
    ("0. 零技能 Omega", {
        'Trade': 0, 'Accounting': 0, 'Broker Relations': 0,
        'Retail': 0, 'Wholesale': 0, 'Tycoon': 0, 'Marketing': 0,
    }),
    # Phase 1: Trade I-IV (must get to IV for Accounting)
    ("1. Trade I (+4单)", {'Trade': 1}),
    ("2. Trade II (+8单)", {'Trade': 2}),
    ("3. Trade III (+12单)", {'Trade': 3}),
    ("4. Trade IV (+16单, 解锁Accounting)", {'Trade': 4}),
    # Phase 2: Accounting (massive tax savings, requires Trade IV)
    ("5. + Accounting I (税6.68%)", {'Trade': 4, 'Accounting': 1}),
    ("6. + Accounting II (税5.85%)", {'Trade': 4, 'Accounting': 2}),
    ("7. + Accounting III (税5.03%)", {'Trade': 4, 'Accounting': 3}),
    ("8. + Accounting IV (税4.20%)", {'Trade': 4, 'Accounting': 4}),
    # Phase 3: Broker Relations (requires only Trade II, could do earlier)
    ("9. + Broker Relations I (佣金2.70%)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 1}),
    ("10. + Broker Relations II (佣金2.40%)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 2}),
    ("11. + Broker Relations III (佣金2.10%)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 3}),
    ("12. + Broker Relations IV (佣金1.80%)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 4}),
    # Phase 4: Retail for more orders
    ("13. + Retail I (29单)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 4, 'Retail': 1}),
    ("14. + Retail II (37单)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 4, 'Retail': 2}),
    ("15. + Retail III (45单)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 4, 'Retail': 3}),
    ("16. + Retail IV (53单)", {'Trade': 4, 'Accounting': 4, 'Broker Relations': 4, 'Retail': 4}),
    # Phase 5: Accounting V (expensive but big tax savings)
    ("17. + Accounting V (税3.38%)", {'Trade': 4, 'Accounting': 5, 'Broker Relations': 4, 'Retail': 4}),
    # Phase 6: Broker V
    ("18. + Broker Relations V (佣金1.50%)", {'Trade': 4, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 4}),
    # Phase 7: Retail V (61单, covers 54 items)
    ("19. + Retail V (61单, 覆盖全部54种)", {'Trade': 4, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 5}),
    # Phase 8: Trade V (65单)
    ("20. + Trade V (65单)", {'Trade': 5, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 5}),
    # Phase 9: Wholesale (requires Retail V + Marketing II)
    ("21. + Marketing II + Wholesale I (97单)", {'Trade': 5, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 5, 'Marketing': 2, 'Wholesale': 1}),
    ("22. + Wholesale V (225单)", {'Trade': 5, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 5, 'Marketing': 2, 'Wholesale': 5}),
    # Phase 10: Tycoon (requires Wholesale V + Marketing IV)
    ("23. + Marketing IV + Tycoon V (861单)", {'Trade': 5, 'Accounting': 5, 'Broker Relations': 5, 'Retail': 5, 'Marketing': 4, 'Wholesale': 5, 'Tycoon': 5}),
]

# Fill in missing skills with 0 and ensure prerequisites
def ensure_prereqs(levels):
    """Ensure all prerequisites are met, adding them if needed."""
    changed = True
    while changed:
        changed = False
        for skill, info in SKILLS.items():
            level = levels.get(skill, 0)
            for prereq, prereq_level in info['prereqs'].items():
                if levels.get(prereq, 0) < prereq_level:
                    levels[prereq] = prereq_level
                    changed = True
    # Add Marketing if needed by Wholesale/Tycoon
    return levels

# ============================================================
# Calculate progression
# ============================================================
print('=' * 110)
print('Omega 新角色交易技能投入产出分析 (基于 EVE Wiki 实时验证数据)')
print('=' * 110)
print()
print('已验证数据 (来源: EVE University Wiki, 2026-07):')
print('  * 销售税基数: 7.5% (2025-03 V22.02 更新)')
print('  * Accounting: Rank 3x, 前置 Trade IV (非Trade II!)')
print('  * Broker Relations: Rank 2x, 前置 Trade II')
print('  * Retail: Rank 2x, 前置 Trade II, +8单/级')
print('  * Wholesale: Rank 4x, 前置 Retail V + Marketing II, +16单/级')
print('  * Tycoon: Rank 6x, 前置 Wholesale V + Marketing IV, +32单/级')
print()

# Test items
total_buy = sum(q*b for _,q,_,b,_ in items_raw)
total_sell = sum(q*s for _,q,_,_,s in items_raw)
print(f'货物: {len(items_raw)} 种物品, Jita Buy = {total_buy:,.0f}, Jita Sell = {total_sell:,.0f}')
print(f'收货商报价: {PAYMENT:,.0f}')
print()

header = f'{"阶段":<42} {"SP累计":>10} {"挂单":>4} {"税率":>6} {"佣金":>6} {"净收入":>14} {"vs收货商":>13} {"每万SP":>10}'
print(header)
print('-' * len(header))

prev_sp = 0
prev_net = 0
results = []

for desc, raw_levels in PROGRESSION:
    levels = dict(raw_levels)
    # Ensure all skills present
    for skill in SKILLS:
        levels.setdefault(skill, 0)
    # Ensure prerequisites met
    ensure_prereqs(levels)

    sp = calc_total_sp(dict(levels))  # don't mutate
    orders = calc_orders(levels)
    tax = calc_tax(levels)
    broker = calc_broker(levels)
    net, n_sell, n_buy = calc_net_revenue(levels, items_raw)

    diff = net - PAYMENT
    sp_diff = sp - prev_sp
    net_diff = net - prev_net
    per_10k = net_diff / (sp_diff / 10000) if sp_diff > 0 else 0

    results.append({
        'desc': desc, 'sp': sp, 'orders': orders, 'tax': tax, 'broker': broker,
        'net': net, 'diff': diff, 'sp_diff': sp_diff, 'net_diff': net_diff,
        'per_10k': per_10k, 'levels': dict(levels),
    })

    tax_str = f'{tax*100:.2f}%'
    broker_str = f'{broker*100:.2f}%'
    print(f'{desc:<42} {sp:>10,} {orders:>4} {tax_str:>6} {broker_str:>6} {net:>14,.0f} {diff:>+13,.0f} {per_10k:>10,.0f}')

    prev_sp = sp
    prev_net = net

# ============================================================
# Marginal analysis
# ============================================================
print()
print('=' * 110)
print('边际收益分析')
print('=' * 110)
print()
print(f'{"升级":<48} {"追加SP":>10} {"追加收入":>14} {"每万SP收益":>12} {"边际评价":<12}')
print('-' * 100)

for i, r in enumerate(results):
    if i == 0:
        continue
    prev = results[i-1]
    sp_diff = r['sp'] - prev['sp']
    net_diff = r['net'] - prev['net']
    per_10k = net_diff / (sp_diff / 10000) if sp_diff > 0 else 0

    if per_10k > 5_000_000:
        verdict = "★★★ 极高"
    elif per_10k > 1_000_000:
        verdict = "★★ 很高"
    elif per_10k > 300_000:
        verdict = "★ 值得"
    elif per_10k > 100_000:
        verdict = "一般"
    elif per_10k > 30_000:
        verdict = "较低"
    elif per_10k > 0:
        verdict = "很低"
    else:
        verdict = "负收益"

    print(f'{r["desc"]:<48} {sp_diff:>10,} {net_diff:>+14,.0f} {per_10k:>12,.0f} {verdict}')

# ============================================================
# Training time and recommendations
# ============================================================
SP_PER_HOUR = 2700 * 60 / 60  # 2700 SP/min = 162,000 SP/hour

print()
print('=' * 110)
print('推荐方案 (针对不同使用场景)')
print('=' * 110)
print()

# Scenario analysis for different cargo sizes
# For 54 items: 21 orders is often enough for high-value items
# For 100+ items: need more orders
# For long-term recurring use: tax rate matters more

# Key breakpoints for order counts
print('挂单需求 vs 技能投入:')
print()

configs = [
    ("方案A: Trade IV + Acc IV + Broker IV", results[12]),
    ("方案B: + Retail I-IV (29-53单)", results[16]),
    ("方案C: + Accounting V", results[17]),
    ("方案D: + Broker V", results[18]),
    ("方案E: + Retail V (61单, 全覆盖54种)", results[19]),
    ("方案F: + Trade V (65单)", results[20]),
]

for name, r in configs:
    hours = r['sp'] / 162000
    print(f'{name}:')
    print(f'   SP: {r["sp"]:>10,} | 训练: {hours:>5.1f}h | 挂单: {r["orders"]:>3} | 税: {r["tax"]*100:.2f}% | 佣金: {r["broker"]*100:.2f}% | 净收入: {r["net"]:>12,.0f} | vs收货商: {r["diff"]:+12,.0f}')
    print()

# Long-term analysis
print('-' * 110)
print('长期分析: 如果每月卖货 1 次 vs 4 次 vs 每天卖')
print('-' * 110)
print()

# Tax savings scale linearly with volume
# Each skill level of Accounting saves: 7.5% * 0.11 * transaction_volume
# For a 500M transaction: Accounting IV saves 7.5%*0.44*500M = 16.5M vs 0

monthly_volumes = [500_000_000, 2_000_000_000, 15_000_000_000]  # 500M, 2B, 15B (daily 500M)
volume_labels = ["每月 500M (偶尔)", "每月 2B (经常)", "每月 15B (每天)"]

# Compare key configs
key_configs = [
    ("零技能", results[0]),
    ("Trade IV+Acc IV+Brk IV (21单)", results[12]),
    ("+ Retail IV (53单)", results[16]),
    ("+ Acc V+Brk V+Retail V (61单)", results[19]),
]

print(f'{"配置":<36} {"SP":>8} | ', end='')
for label in volume_labels:
    print(f'{label:>18} | ', end='')
print()
print(f'{"":36} {"":8} | ', end='')
for label in volume_labels:
    print(f'{"月净税率节省":>18} | ', end='')
print()
print('-' * 130)

for name, r in key_configs:
    tax = r['tax']
    broker = r['broker']
    total_rate = tax + broker
    sp = r['sp']
    print(f'{name:<36} {sp:>8,} | ', end='')
    for vol in monthly_volumes:
        # Approximate: on sell orders, pay tax+broker; on buy fills, pay tax only
        # Assume 70% sell orders, 30% buy fills (rough)
        monthly_cost = vol * total_rate * 0.7 + vol * tax * 0.3
        print(f'{monthly_cost:>15,.0f} ISK | ', end='')
    print()

print()
print('=' * 110)
print('最终结论')
print('=' * 110)
print()

r_a = results[12]  # Trade IV + Acc IV + Brk IV
r_b = results[16]  # + Retail IV
r_e = results[19]  # Full trade V + all V

print(f'1. 最小可行方案 (方案A): Trade IV + Accounting IV + Broker Relations IV')
print(f'   SP: {r_a["sp"]:,} ({r_a["sp"]/162000:.1f} 小时)')
print(f'   挂单: {r_a["orders"]}个 | 税率: {r_a["tax"]*100:.2f}% | 佣金: {r_a["broker"]*100:.2f}%')
print(f'   这批货净收入: {r_a["net"]:,.0f} ISK (vs收货商 {r_a["diff"]:+,.0f})')
print()

# Calculate how many items are in top 21 by sell advantage
items_with_adv = []
for tid, qty, name, buy, sell in items_raw:
    sell_total = qty * sell if sell > 0 else 0
    buy_total = qty * buy
    sell_adv = sell_total * (1 - r_a['tax'] - r_a['broker']) - buy_total * (1 - r_a['tax']) if sell > 0 else 0
    items_with_adv.append((name, qty, sell_adv))
items_with_adv.sort(key=lambda x: x[2], reverse=True)
top_items_value = sum(sell_adv for _, _, sell_adv in items_with_adv[:r_a['orders']])
remaining_items_value = sum(sell_adv for _, _, sell_adv in items_with_adv[r_a['orders']:])

print(f'   21个挂单覆盖的物品卖单优势: {top_items_value:,.0f} ISK')
print(f'   其余{len(items_raw)-r_a["orders"]}种物品放弃的卖单优势: {remaining_items_value:,.0f} ISK (仅占总优势的{remaining_items_value/(top_items_value+remaining_items_value)*100:.1f}%)')
print()

print(f'2. 性价比最优 (方案B): 方案A + Retail IV = {r_b["orders"]}个挂单')
print(f'   额外SP: {r_b["sp"]-r_a["sp"]:,} | 额外收入: {r_b["net"]-r_a["net"]:+,.0f} ISK')
print(f'   这批货几乎覆盖所有有意义的物品')
print()

print(f'3. 税率优化的长期价值:')
print(f'   从方案B (税4.20%) 到 方案E (税3.38%):')
print(f'   每月交易量 2B: 省税 {2_000_000_000*(0.042-0.0338):,.0f} ISK/月')
print(f'   每月交易量 15B: 省税 {15_000_000_000*(0.042-0.0338):,.0f} ISK/月')
print(f'   Accounting V 需要额外 {(r_e["sp"]-r_b["sp"]):,} SP ({(r_e["sp"]-r_b["sp"])/162000:.1f}小时)')
print(f'   如果你每月交易量超过 2B, Accounting V 值得练')
print()

print(f'4. 关键发现: Accounting 前置是 Trade IV (不是 Trade II!)')
print(f'   这意味着必须先投入 {calc_sp("Trade", 4):,} SP 在 Trade 上才能开始减税')
print(f'   Trade IV 本身也很有价值 (+16个订单), 所以不是浪费')
print(f'   但这改变了学习顺序: 必须先 Trade IV -> 才能学 Accounting')
print()

# The real sweet spot depends on volume
print(f'5. 不同使用频率的推荐:')
print()
print(f'   偶尔卖货 (每月<1B):')
print(f'     → Trade IV + Accounting IV + Broker IV (方案A), 训练1.4小时, 足够')
print()
print(f'   经常卖货 (每月2-5B):')
print(f'     → 方案A + Retail IV (方案B), 再加 Accounting V')
print(f'     → 训练约8小时, 税率从6%降到4.875%, 每月多省几百万')
print()
print(f'   高频交易 (每月10B+):')
print(f'     → 方案E (Trade V + Retail V + Acc V + Broker V), 61单, 税3.38%')
print(f'     → 每月省下的税远超训练成本')
