import csv
import json
from pathlib import Path

with open('/tmp/loto7.json', encoding='utf-8') as f:
    data = json.load(f)

rows = []
for d in data:
    nums = d.get('numbers', [])
    if len(nums) != 7 or len(set(nums)) != 7 or not all(1 <= int(n) <= 37 for n in nums):
        continue
    rows.append([int(d['round']), d['date'], *map(int, nums)])

rows.sort(key=lambda r: r[0])
if len(rows) < 600:
    raise SystemExit(f'Incomplete Loto7 history: {len(rows)} rows')

out = Path('app/src/main/assets/loto7.csv')
with out.open('w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['round', 'date', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7'])
    writer.writerows(rows)

print(f'Bundled {len(rows)} Loto7 draws')
