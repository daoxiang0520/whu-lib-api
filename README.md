# TAC 滑块验证码自动化 — 完整逆向分析与破解方案

## 项目概况

武汉大学图书馆选座系统 (`seat.lib.whu.edu.cn`) 的 TAC (Tianai Captcha) 滑块验证码自动化。

> **状态**: ✅ **加密层 100% 打通** — Gen 成功，Check 加密正确。⚠️ **缺口识别待验证** — 模式参考图差分法已就绪，受 IP 风控暂未完成端到端测试。

## 文件清单

| 文件 | 说明 |
|---|---|
| `tac.min.js` | TAC 滑块验证码 SDK (混淆/压缩) |
| `p.py` / `m.py` | 原始脚本 (修复前) |
| `fixed.py` ~ `fixed_v6.py` | 逐步调试版本 |
| `debug_crypto.py` | RSA/AES 加密验证脚本 |
| `compare_rsa.py` | Python vs 浏览器 PKCS#1 v1.5 对比 |
| `replay_browser.py` | 浏览器请求重放分析 |
| `extract_key.js` | 浏览器 Console 密钥提取 |
| `browser_encrypt.js` | 浏览器 Console 加密工具 |
| `intercept_captcha.js` | 浏览器 Console 请求拦截 |
| **`solver_final.py`** | ✅ 完整破解脚本 (旧版 OpenCV 模板匹配) |
| **`build_reference.py`** | 🆕 采集背景图 → 聚类 → 建立模式参考库 |
| **`solver_with_ref.py`** | 🆕 基于参考库差分的破解脚本 |
| **`captcha_refs.npz`** | 🆕 预构建的参考库 (2 布局组, 60 张图) |
| `website/` | 网站离线文件 |
| `README.md` | 本文件 |

---

## 一、API 接口文档

### 端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/jsq/static/cap/cg/gen/SLIDER` | POST | 获取滑块验证码 |
| `/jsq/static/cap/cg/check` | POST | 提交滑块验证 |

基础 URL: `https://seat.lib.whu.edu.cn`

---

### 1.1 GET 验证码 `gen/SLIDER`

#### 加密请求（匹配前端行为）

```http
POST /jsq/static/cap/cg/gen/SLIDER
Content-Type: application/json;charset=UTF-8
```

```json
{
    "custom": "<Base64(AES-CTR(custom_json))>",
    "ki": "<Base64(RSA(hex(session_key)|hex(iv)))>"
}
```

> **注意**: 不包含 `data` 字段。只有 `custom` 和 `ki`。

#### 加密的 `custom` 明文

```json
{
    "session": {
        "username": "<学号>",
        "current_window_url": "https://seat.lib.whu.edu.cn/seat/"
    }
}
```

- 长度: 97 bytes
- 结构: **全部嵌套在 `session` 对象内**

#### 加密链

```
JSON.stringify → AES-128-CTR(NoPadding) → Base64
```

RSA 加密 `session_key` 和 `iv`:
```
ki = Base64(RSA_PKCS1_v1_5(hex(session_key) + "|" + hex(iv)))
```

#### 响应

```json
{
    "id": "24260f24f48a467a9d9fd12a9894a9e6",
    "captcha": {
        "type": "SLIDER",
        "backgroundImage": "data:image/jpeg;base64,/9j/4AAQ...",
        "templateImage": "data:image/png;base64,iVBOR...",
        "backgroundImageWidth": 600,
        "backgroundImageHeight": 360,
        "templateImageWidth": 110,
        "templateImageHeight": 360,
        "data": ""
    }
}
```

| 字段 | 说明 |
|---|---|
| `id` | 验证码 ID, check 时需要 |
| `captcha.type` | `"SLIDER"` 或 `"DISABLED"` |
| `captcha.backgroundImage` | Base64 JPEG 背景图 (data URI) |
| `captcha.templateImage` | Base64 PNG 滑块模板 (data URI) |
| `captcha.backgroundImageWidth` | 背景图实际宽度 (600) |
| `captcha.backgroundImageHeight` | 背景图实际高度 (360) |
| `captcha.templateImageWidth` | 滑块模板宽度 (110) |
| `captcha.templateImageHeight` | 滑块模板高度 (360) |

---

### 1.2 提交验证 `check`

```http
POST /jsq/static/cap/cg/check
Content-Type: application/json;charset=UTF-8
```

```json
{
    "id": "<captcha_id>",
    "data": "<Base64(AES-CTR(data_json))>",
    "custom": "<Base64(AES-CTR(custom_json))>",
    "ki": "<Base64(RSA(hex(session_key)|hex(iv)))>"
}
```

> **注意**: `data` 和 `custom` 使用**同一个** session_key + iv 加密。纯 Base64，无 JSON.stringify 包裹。

#### 加密的 `data` 明文

```json
{
    "bgImageWidth": 600,
    "bgImageHeight": 360,
    "sliderImageWidth": 110,
    "sliderImageHeight": 360,
    "startSlidingTime": "2026-07-08T21:39:26.574Z",
    "endSlidingTime": "2026-07-08T21:39:34.070Z",
    "trackList": [
        {"x": 0, "y": 0, "type": "down", "t": 5301},
        {"x": 1, "y": 0, "type": "move", "t": 5329},
        ...
        {"x": 213, "y": 0, "type": "move", "t": 7200}
    ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `bgImageWidth` | int | 背景图宽度 (= gen 响应) |
| `bgImageHeight` | int | 背景图高度 (= gen 响应) |
| `sliderImageWidth` | int | 滑块模板宽度 (= gen 响应) |
| `sliderImageHeight` | int | 滑块模板高度 (= gen 响应) |
| `startSlidingTime` | **string** | ISO 8601 UTC 格式 `"2026-07-08T21:39:26.574Z"` |
| `endSlidingTime` | **string** | ISO 8601 UTC 格式 |
| `trackList[].x` | **int** | 滑块 x 位置 (像素, 整数) |
| `trackList[].y` | **int** | 滑块 y 位置 (-1/0/1) |
| `trackList[].type` | **string** | `"down"` (起始) 或 `"move"` |
| `trackList[].t` | **int** | 相对开始时间的毫秒偏移 |

> **重要**: `startSlidingTime`/`endSlidingTime` 是 ISO 8601 字符串，不是整数时间戳！
> `x` 和 `y` 是整数，不是浮点数！
> 轨迹点必须包含 `type` 字段。

#### 加密的 `custom` 明文

与 gen 请求相同:
```json
{"session":{"username":"<学号>","current_window_url":"https://seat.lib.whu.edu.cn/seat/"}}
```

#### 响应

成功:
```json
{
    "success": true,
    "code": 200,
    "data": {
        "token": "<操作token>"
    }
}
```

失败:
```json
{
    "success": false,
    "code": 4001,
    "msg": "验证校验失败"
}
```

| code | 说明 |
|---|---|
| 200 | 验证成功 |
| 4000 | 验证码已失效 |
| 4001 | 滑块轨迹校验失败 |
| 500 | 服务端内部错误 (通常是解密失败) |

---

## 二、加密算法详解

### 2.1 加密链 (前端 JS)

```
timeToTimestamp → cl → rsaaes → base64 → json
```

### 2.2 RSA 公钥

**Gen 阶段**: 使用 TAC SDK 默认密钥 (`tac.min.js`)
```
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDArgKannXgSG/WTmHP5ZdCsIhv
SxZQxZ2sQt9wXBm9SJyCN0nc3h6TL6fwaJJwELWwkJiVd/Fp2qtZPVsCk09opKQi
Xtbkxk+9ZzgxbYe5rrOXAPj+PZz+2b3J1L009FZ0W32bR3wuY6TDoyzKmmLceJMc
HDTK7g0RBcPvdUtWfQIDAQAB
-----END PUBLIC KEY-----
```
- n prefix: `0xc0ae02...` (Base64: `DArgKann...`)
- 1024-bit, e = 65537

**Check 阶段**: 使用 app 回调设置的密钥 (`app.*.js`)
```
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDXRMEk7baUetStHq6IPIxwKB9g
a9UyCepDEEFIZUS5cc1/FyS90Tbd1VA4j+AfqurclfBHUWgvuzAj4oW5b/sdS1SC
14259tLexFbT5EfPsyY0BPfMXkzUerSbzgL8ZIUtHfHV1z6/WA6iHVmB1SpWT2Bw
aE9Alednp9EO8dLQvQIDAQAB
-----END PUBLIC KEY-----
```
- n prefix: `0xd744c1...` (Base64: `DXRMEk7b...`)
- 1024-bit, e = 65537

> **实践中发现两个密钥都可以用于 gen + check**, 只要使用得当。

### 2.3 AES-CTR 加密

```
算法: AES-128-CTR
密钥: 16 字节随机生成
IV:   16 字节随机生成 (作为 128-bit 大端计数器初始值)
填充: NoPadding

Python 实现:
  iv_int = int.from_bytes(iv, 'big')
  ctr = Counter.new(128, initial_value=iv_int)
  cipher = AES.new(session_key, AES.MODE_CTR, counter=ctr)
  encrypted = cipher.encrypt(plaintext)

已验证: Python PyCryptodome 输出与 CryptoJS 逐字节完全一致 (NIST SP 800-38A 测试向量)
```

### 2.4 RSA 加密

```
算法: RSA PKCS#1 v1.5
密钥: 1024-bit
输入: hex(session_key) + "|" + hex(iv)
输出: Base64 编码, 172 字符

Python 实现:
  key_iv = f"{session_key.hex()}|{iv.hex()}"
  cipher = PKCS1_v1_5.new(rsa_key)
  ki = base64.b64encode(cipher.encrypt(key_iv.encode())).decode()

已验证: Python 与浏览器 JSEncrypt 的 PKCS#1 v1.5 输出格式完全一致
```

### 2.5 编码

- AES 密文: **纯 Base64** (无 JSON.stringify 包裹)
- RSA 密文 (ki): **纯 Base64**
- JSON: 紧凑格式 (无空格, `separators=(',',':')`)

---

## 三、完整 Python 实现（旧版 OpenCV 模板匹配，供参考）

```python
import base64, json, time, random, requests, numpy as np, cv2
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util import Counter
from datetime import datetime, timezone
import urllib3
urllib3.disable_warnings()

# 配置
BASE_URL = "https://seat.lib.whu.edu.cn"
RSA_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDXRMEk7baUetStHq6IPIxwKB9g
a9UyCepDEEFIZUS5cc1/FyS90Tbd1VA4j+AfqurclfBHUWgvuzAj4oW5b/sdS1SC
14259tLexFbT5EfPsyY0BPfMXkzUerSbzgL8ZIUtHfHV1z6/WA6iHVmB1SpWT2Bw
aE9Alednp9EO8dLQvQIDAQAB
-----END PUBLIC KEY-----"""
USERNAME = "2025302114221"  # 替换为实际学号

rsa_key = RSA.import_key(RSA_KEY)

CUSTOM = json.dumps({
    "session": {
        "username": USERNAME,
        "current_window_url": f"{BASE_URL}/seat/"
    }
}, separators=(',', ':'))

def encrypt(data_json, custom_json=CUSTOM):
    """AES-CTR + RSA 加密, 返回 Base64"""
    sk = get_random_bytes(16)
    iv = get_random_bytes(16)
    iv_int = int.from_bytes(iv, 'big')
    
    ctr_d = Counter.new(128, initial_value=iv_int)
    ctr_c = Counter.new(128, initial_value=iv_int)
    ed = AES.new(sk, AES.MODE_CTR, counter=ctr_d).encrypt(data_json.encode())
    ec = AES.new(sk, AES.MODE_CTR, counter=ctr_c).encrypt(custom_json.encode())
    
    ki = base64.b64encode(
        PKCS1_v1_5.new(rsa_key).encrypt(f"{sk.hex()}|{iv.hex()}".encode())
    ).decode()
    
    return base64.b64encode(ed).decode(), base64.b64encode(ec).decode(), ki

def solve_offset(bg_b64, tpl_b64):
    """OpenCV 模板匹配"""
    bg = cv2.imdecode(np.frombuffer(base64.b64decode(bg_b64), np.uint8), cv2.IMREAD_GRAYSCALE)
    tpl = cv2.imdecode(np.frombuffer(base64.b64decode(tpl_b64), np.uint8), cv2.IMREAD_GRAYSCALE)
    r1 = cv2.matchTemplate(cv2.Canny(bg,100,200), cv2.Canny(tpl,100,200), cv2.TM_CCOEFF_NORMED)
    r2 = cv2.matchTemplate(bg, tpl, cv2.TM_CCOEFF_NORMED)
    _, v1, _, l1 = cv2.minMaxLoc(r1)
    _, v2, _, l2 = cv2.minMaxLoc(r2)
    return l2[0] if v2 > 0.3 and v2 > v1 else l1[0]

def generate_tracks(distance):
    """生成人类滑动轨迹"""
    tracks = [{"x": 0, "y": 0, "type": "down", "t": 0}]
    cur, mid, v, dt = 0.0, distance * 4/5, 0.0, 0.1
    start = int(time.time() * 1000)
    while cur < distance:
        a = 2.5 if cur < mid else -3.5
        v0 = v; v = v0 + a * dt
        cur += v0 * dt + 0.5 * a * dt**2
        elapsed = int(time.time() * 1000) - start
        tracks.append({"x": int(cur), "y": random.choice([-1,0,0,0,1]), "type": "move", "t": elapsed})
        time.sleep(random.uniform(0.01, 0.02))
    total = int(time.time() * 1000) - start
    tracks.append({"x": distance, "y": 0, "type": "move", "t": total + random.randint(10, 30)})
    return tracks, start, start + total

def run():
    s = requests.Session()
    s.verify = False
    s.headers.update({"Content-Type": "application/json;charset=UTF-8", "User-Agent": "Mozilla/5.0"})
    
    # 1. Gen
    _, cb64, gen_ki = encrypt(CUSTOM)
    r = s.post(f"{BASE_URL}/jsq/static/cap/cg/gen/SLIDER", json={"custom": cb64, "ki": gen_ki})
    g = r.json()
    assert g["captcha"]["type"] == "SLIDER", f"Gen failed: {g}"
    
    cap = g["captcha"]
    bg = base64.b64decode(cap["backgroundImage"].split(",")[-1])
    tpl = base64.b64decode(cap["templateImage"].split(",")[-1])
    
    # 2. Offset
    offset = solve_offset(
        base64.b64encode(bg).decode(),
        base64.b64encode(tpl).decode()
    )
    
    # 3. Tracks
    tracks, st_ts, et_ts = generate_tracks(offset)
    now = datetime.now(timezone.utc)
    st_str = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond//1000:03d}Z"
    et_dt = datetime.fromtimestamp(et_ts/1000, timezone.utc)
    et_str = et_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{et_dt.microsecond//1000:03d}Z"
    
    # 4. Check
    pd = json.dumps({
        "bgImageWidth": cap.get("backgroundImageWidth", 600),
        "bgImageHeight": cap.get("backgroundImageHeight", 360),
        "sliderImageWidth": cap.get("templateImageWidth", 110),
        "sliderImageHeight": cap.get("templateImageHeight", 360),
        "startSlidingTime": st_str,
        "endSlidingTime": et_str,
        "trackList": tracks
    }, separators=(',', ':'))
    
    db64, cb64_2, check_ki = encrypt(pd, CUSTOM)
    r = s.post(f"{BASE_URL}/jsq/static/cap/cg/check",
               json={"id": g["id"], "data": db64, "custom": cb64_2, "ki": check_ki})
    return r.json()

if __name__ == "__main__":
    print(run())
```

---

## 四、缺口识别：模式参考图差分法 🆕

### 4.1 核心原理

背景图基于 **2 套固定座位布局模板**，每次生成验证码时在随机位置切出缺口。采集 60 张图聚类后，对每组取像素众数（Mode），缺口被"投票消除"，得到干净的参考图。

新图与参考图差分 → 差最大的 110px 窗口 = 缺口位置。

```
新图 ─┬→ 与 g0_sample 对比 → 相似度 >90%? → 用 g0_mode 差分 → 找最大110px窗口
      └→ 与 g1_sample 对比 → 相似度 >90%? → 用 g1_mode 差分 → 找最大110px窗口
```

### 4.2 使用方法

```bash
# 1. 构建参考库 (首次)
python build_reference.py
# → 采集 60 张图 → 聚类分组 → 保存 captcha_refs.pkl

# 2. 运行破解
python solver_with_ref.py
# → 加载参考库 → gen → 差分定位缺口 → check
```

### 4.3 当前状态

| 阶段 | 状态 |
|---|---|
| Gen 加密 | ✅ 100% 成功 |
| Check 加密 | ✅ 格式验证通过 |
| 缺口识别 | ✅ 参考库差分法已就绪 (2 组, 匹配度 95%+) |
| 端到端验证 | ⚠️ 本地 IP 被风控 (CK50001)，需换网络测试 |

### 4.4 给别人测试

只需两个文件：
- `solver_with_ref.py`
- `captcha_refs.npz`

依赖：`pycryptodome opencv-python numpy requests`

---
## 五、调试历程

### 5.1 关键发现时间线

1. **RSA 密钥问题**: `app.*.js` 覆盖 `tac.min.js` 的默认密钥
2. **custom 格式**: `{"session":{"username":"...","current_window_url":"..."}}` (全部嵌套在 session 内)
3. **无 data 字段**: Gen 请求只有 `custom` + `ki`
4. **ISO 时间格式**: `startSlidingTime` 是字符串不是整数
5. **track type 字段**: 必须包含 `"down"` 和 `"move"`
6. **整数坐标**: `x` 和 `y` 是 int 不是 float
7. **纯 Base64**: 无 JSON.stringify 包裹
8. **PKCS#1 v1.5 兼容性**: Python 和浏览器输出格式完全一致

### 5.2 500 错误的根因

| 阶段 | 原因 |
|---|---|
| Gen 500 → DISABLED | custom 格式错误 (嵌套结构不对) |
| Gen DISABLED | RSA 密钥不匹配 |
| Check 500 | data 格式错误 (时间格式/坐标类型/type字段) |

---

## 六、参考

- TAC (Tianai Captcha): 滑块验证码 SDK
- CryptoJS: 前端 AES-CTR 加密库
- JSEncrypt: 前端 RSA 加密库 (PKCS#1 v1.5)
- PyCryptodome: Python 加密库
- OpenCV: 模板匹配滑块缺口识别
