"""
基于参考库的验证码破解
加载预构建的模式参考图 → 差分定位缺口 → 加密提交
"""
import base64, json, time, random, pickle, numpy as np, cv2, requests, urllib3
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util import Counter
from datetime import datetime, timezone

urllib3.disable_warnings()

REF_FILE = "captcha_refs.npz"  # 或 captcha_refs.pkl
KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDXRMEk7baUetStHq6IPIxwKB9g
a9UyCepDEEFIZUS5cc1/FyS90Tbd1VA4j+AfqurclfBHUWgvuzAj4oW5b/sdS1SC
14259tLexFbT5EfPsyY0BPfMXkzUerSbzgL8ZIUtHfHV1z6/WA6iHVmB1SpWT2Bw
aE9Alednp9EO8dLQvQIDAQAB
-----END PUBLIC KEY-----"""
rsa_key = RSA.import_key(KEY)
CUSTOM = json.dumps({'session': {'username': '2025302114221', 'current_window_url': 'https://seat.lib.whu.edu.cn/seat/'}}, separators=(',',':'))

def encrypt(j):
    sk = get_random_bytes(16); iv = get_random_bytes(16)
    iv_int = int.from_bytes(iv, 'big')
    ctr_d = Counter.new(128, initial_value=iv_int)
    ctr_c = Counter.new(128, initial_value=iv_int)
    ed = AES.new(sk, AES.MODE_CTR, counter=ctr_d).encrypt(j.encode())
    ec = AES.new(sk, AES.MODE_CTR, counter=ctr_c).encrypt(CUSTOM.encode())
    ki = base64.b64encode(PKCS1_v1_5.new(rsa_key).encrypt(f'{sk.hex()}|{iv.hex()}'.encode())).decode()
    return base64.b64encode(ed).decode(), base64.b64encode(ec).decode(), ki

def make_tracks(d):
    tracks = [{'x': 0, 'y': 0, 'type': 'down', 't': 0}]
    cur, v, dt = 0.0, 0.0, 0.1
    mid = d * random.uniform(0.7, 0.85)
    rec_start = int(time.time()*1000)
    while cur < d:
        a = random.uniform(1.5, 3.5) if cur < mid else random.uniform(-5.0, -2.0)
        v = max(0.05, v + a*dt)
        cur += v*dt
        tracks.append({'x': int(min(cur,d)), 'y': random.choice([-1,0,0,0,1]), 'type': 'move', 't': int(time.time()*1000)-rec_start})
        time.sleep(random.uniform(0.01, 0.03))
    total = int(time.time()*1000) - rec_start
    if total < 800: total = 800 + random.randint(100, 600)
    tracks.append({'x': d, 'y': 0, 'type': 'up', 't': total})
    st_dt = datetime.fromtimestamp(rec_start/1000, timezone.utc)
    st_str = st_dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{st_dt.microsecond//1000:03d}Z'
    et_dt = datetime.fromtimestamp((rec_start+total)/1000, timezone.utc)
    et_str = et_dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{et_dt.microsecond//1000:03d}Z'
    return tracks, st_str, et_str

# 加载参考库（支持 npz 和 pkl 两种格式）
import os
if REF_FILE.endswith('.npz'):
    d = np.load(REF_FILE)
    refs = [
        {'group_id': 0, 'group_size': int(d['g0_size']), 'sample_img': d['g0_sample'], 'mode_bg': d['g0_mode']},
        {'group_id': 1, 'group_size': int(d['g1_size']), 'sample_img': d['g1_sample'], 'mode_bg': d['g1_mode']},
    ]
    print(f'Loaded {len(refs)} layout groups from {REF_FILE}')
elif REF_FILE.endswith('.pkl'):
    with open(REF_FILE, 'rb') as f:
        refs = pickle.load(f)
    print(f'Loaded {len(refs)} layout groups from {REF_FILE}')
else:
    raise ValueError(f'Unknown ref format: {REF_FILE}')

def find_gap(bg_b64):
    """用参考库差分定位缺口"""
    bg = cv2.imdecode(np.frombuffer(base64.b64decode(bg_b64), np.uint8), cv2.IMREAD_GRAYSCALE)
    bg_f = bg.astype(float)

    # 分类到最匹配的组
    best_g, best_sim = 0, 100
    for gi, ref in enumerate(refs):
        sim = np.mean(np.abs(bg_f - ref['sample_img'].astype(float)) > 30) * 100
        if sim < best_sim:
            best_sim, best_g = sim, gi

    # 与模式参考图差分
    mode_bg = refs[best_g]['mode_bg'].astype(float)
    diff = np.abs(bg_f - mode_bg)
    col_diff = np.sum(diff, axis=0)
    smooth = np.convolve(col_diff, np.ones(15)/15, mode='same')

    # 找 110px 窗口差值和最大的位置 = 缺口
    best_x, best_sum = 0, 0
    for x in range(40, 470):
        s = np.sum(smooth[x:x+110])
        if s > best_sum:
            best_sum, best_x = s, x
    return best_x, best_g, best_sim

# 测试
s = requests.Session(); s.verify = False
s.headers.update({'Content-Type': 'application/json;charset=UTF-8', 'User-Agent': 'Mozilla/5.0'})

results = []
for i in range(5):
    _, cb64, gen_ki = encrypt('{}')
    r = s.post('https://seat.lib.whu.edu.cn/jsq/static/cap/cg/gen/SLIDER', json={'custom': cb64, 'ki': gen_ki})
    g = r.json()
    if g['captcha']['type'] != 'SLIDER':
        results.append(('GEN_FAIL', ''))
        continue
    cap = g['captcha']
    bg_b64 = cap['backgroundImage'].split(',')[-1]

    gap_x, group_id, sim = find_gap(bg_b64)
    print(f'#{i}: group={group_id} gap={gap_x}px sim={sim:.1f}%')

    tracks, st_str, et_str = make_tracks(gap_x)

    pd = json.dumps({'bgImageWidth':600,'bgImageHeight':360,'sliderImageWidth':110,'sliderImageHeight':360,'startSlidingTime':st_str,'endSlidingTime':et_str,'trackList':tracks}, separators=(',',':'))
    db64, cb64_2, check_ki = encrypt(pd)
    r2 = s.post('https://seat.lib.whu.edu.cn/jsq/static/cap/cg/check', json={'id': g['id'], 'data': db64, 'custom': cb64_2, 'ki': check_ki})
    resp = r2.json()
    ok = resp.get('success', False)
    code = resp.get('code', '?')
    results.append(('OK' if ok else f'CK{code}', f'g{group_id} x={gap_x}'))

    # 控制频率
    time.sleep(2.0)

print(f'\nResults: {sum(1 for r in results if r[0]=="OK")}/{len(results)}')
for r in results:
    print(f'  {r[0]:8s} {r[1]}')
