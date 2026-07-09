"""
构建验证码背景图参考库
采集 → 聚类 → 建立模式参考图 → 保存本地
"""
import base64, json, time, hashlib, numpy as np, cv2, requests, urllib3, pickle, os
from collections import defaultdict

urllib3.disable_warnings()
REF_FILE = "captcha_refs.pkl"

s = requests.Session()
s.verify = False
s.headers.update({
    'Content-Type': 'application/json;charset=UTF-8',
    'User-Agent': 'Mozilla/5.0'
})

# ====== Step 1: 采集 ======
print("[1/3] 采集背景图 (间隔 1s，避免风控)...")
images = []
for i in range(60):
    try:
        r = s.post('https://seat.lib.whu.edu.cn/jsq/static/cap/cg/gen/SLIDER', json={})
        g = r.json()
        if g['captcha']['type'] == 'SLIDER':
            bg_b64 = g['captcha']['backgroundImage'].split(',')[-1]
            bg = cv2.imdecode(np.frombuffer(base64.b64decode(bg_b64), np.uint8), cv2.IMREAD_GRAYSCALE)
            images.append({'b64': bg_b64, 'img': bg})
            print(f"  {i+1}/60 OK", end='\r')
        time.sleep(1.0)  # 控制频率
    except Exception as e:
        print(f"  {i+1}/60 ERR: {e}")
        time.sleep(2.0)

print(f"\n  采集完成: {len(images)} 张")

# ====== Step 2: 聚类 ======
print("[2/3] 聚类分组...")
groups = [[0]]
for i in range(1, len(images)):
    found = False
    for group in groups:
        diff_pct = np.mean(np.abs(images[group[0]]['img'].astype(float) - images[i]['img'].astype(float)) > 30) * 100
        if diff_pct < 10:
            group.append(i)
            found = True
            break
    if not found:
        groups.append([i])

print(f"  共 {len(groups)} 组:")
for gi, group in enumerate(groups):
    print(f"    Group {gi}: {len(group)} 张")

# ====== Step 3: 建立模式参考图 & 保存 ======
print("[3/3] 建立模式参考图...")
refs = []
for gi, group in enumerate(groups):
    # Mode reference
    stack = np.array([images[i]['img'] for i in group])
    stack_rounded = (stack // 8) * 8
    mode_bg = np.zeros((360, 600), dtype=np.uint8)
    for y in range(360):
        for x in range(600):
            vals = stack_rounded[:, y, x]
            unique, counts = np.unique(vals, return_counts=True)
            mode_bg[y, x] = unique[np.argmax(counts)]

    # Save one sample image for classification
    refs.append({
        'group_id': gi,
        'group_size': len(group),
        'sample_img': images[group[0]]['img'],  # for classification
        'mode_bg': mode_bg,
    })

    cv2.imwrite(f'ref_group{gi}_mode.png', mode_bg)
    print(f"    Group {gi}: mode_bg saved (ref_group{gi}_mode.png)")

# 序列化保存
with open(REF_FILE, 'wb') as f:
    pickle.dump(refs, f)
print(f"\n  参考库已保存: {REF_FILE} ({os.path.getsize(REF_FILE)} bytes)")
print(f"  共 {len(refs)} 组, 可用于缺口识别")
