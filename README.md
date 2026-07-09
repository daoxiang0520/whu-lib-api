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

基础 URL: `https://seat.lib.whu.edu.cn`  
所有 API 前缀: `/jsq/static`

---

### 1.0 认证体系

图书馆后端对两类端点有不同的认证要求:

| 端点类型 | 认证方式 |
|---|---|
| `cap/cg/*` (验证码) | 无需 HMAC。可选 `JSESSIONID` cookie |
| `frontApi/*` (业务) | **必须**: `token` + `loginType: PC` + **HMAC 签名** |

#### HMAC 签名算法

```
signStr = "seat::" + UUID + "::" + timestamp_ms + "::" + METHOD
signature = HMAC-SHA256(signStr, hmacKey)
```

其中 `hmacKey` 存储在 `sessionStorage.systemInfo.hmacKey`，Base64 编码的 16 字节密钥。

#### 必需的 HTTP Headers (frontApi)

| Header | 值 | 说明 |
|---|---|---|
| `token` | 40 位 hex | 登录后获取，存在 `sessionStorage.token` |
| `loginType` | `PC` | 固定值 |
| `X-request-id` | UUID | 随机 UUID |
| `X-request-date` | 毫秒时间戳 | `Date.now()` |
| `X-hmac-request-key` | 64 位 hex | HMAC-SHA256 签名 |

---

### 1.1 验证码：获取 `gen/SLIDER`

```
POST /jsq/static/cap/cg/gen/SLIDER
Content-Type: application/json;charset=UTF-8
```

**加密请求**（匹配前端 TAC SDK 行为）:

```json
{
    "custom": "<Base64(AES-CTR(custom_plaintext))>",
    "ki": "<Base64(RSA(hex(session_key)|hex(iv)))>"
}
```

> 仅 `custom` + `ki`，**无 `data` 字段**。

**`custom` 明文** (97 bytes):

```json
{"session":{"username":"<学号>","current_window_url":"https://seat.lib.whu.edu.cn/seat/"}}
```

**非加密请求**（简单调试用）:

```json
{}
```

**响应**:

```json
{
    "id": "captcha_uuid",
    "captcha": {
        "type": "SLIDER",
        "backgroundImage": "data:image/jpeg;base64,...",
        "templateImage": "data:image/png;base64,...",
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
| `id` | 验证码 UUID，check 时回传 |
| `captcha.type` | `"SLIDER"` 正常 / `"DISABLED"` 被拒 |
| `captcha.backgroundImage` | Base64 JPEG 背景图 (600×360) |
| `captcha.templateImage` | Base64 PNG 滑块模板 (110×360, 含 Alpha 通道) |

---

### 1.2 验证码：提交 `check`

```
POST /jsq/static/cap/cg/check
```

```json
{
    "id": "<captcha_id>",
    "data": "<Base64(AES-CTR(data_plaintext))>",
    "custom": "<Base64(AES-CTR(custom_plaintext))>",
    "ki": "<Base64(RSA(hex(session_key)|hex(iv)))>"
}
```

> `data` 和 `custom` 用**同一个** session_key + iv。纯 Base64，无 JSON.stringify 包裹。

**`data` 明文**:

```json
{
    "bgImageWidth": 600, "bgImageHeight": 360,
    "sliderImageWidth": 110, "sliderImageHeight": 360,
    "startSlidingTime": "2026-07-08T21:39:26.574Z",
    "endSlidingTime": "2026-07-08T21:39:34.070Z",
    "trackList": [
        {"x": 0, "y": 0, "type": "down", "t": 5301},
        {"x": 1, "y": 0, "type": "move", "t": 5329},
        ...
        {"x": 213, "y": 0, "type": "up",   "t": 7500}
    ]
}
```

| 关键约束 |
|---|
| `startSlidingTime`/`endSlidingTime` 是 ISO 8601 UTC 字符串**不是整数** |
| `x` 和 `y` 是 **int** 不是 float |
| 轨迹点必须包含 `type`: `"down"` → `"move"` → `"up"` |
| `t` 是相对 `startSlidingTime` 的毫秒偏移 |

**`custom` 明文**：与 gen 相同 (97 bytes)。

**响应**:

| code | msg | 说明 |
|---|---|---|
| 200 | — | 验证成功，`data.token` 为操作 token |
| 4000 | 已失效 | 验证码过期 |
| 4001 | 验证校验失败 | 滑块位置不正确 |
| 500 | 未知的内部错误 | 解密失败 |
| 50001 | basic check fail | 风控/请求频率限制 |

---

### 1.3 座位查询

#### 查分馆座位大盘

```
POST /jsq/static/frontApi/res/findRoomDuration/{venueId}/{date}
Headers: token, loginType: PC, X-hmac-request-key, X-request-date, X-request-id

Body:
{
    "beginMinute": 492,     // 开始时间(分钟) eg. 08:12 = 492
    "currentPage": 1,
    "endMinute": 0,
    "floorId": 0,
    "minMinute": 0,
    "pageSize": 12,
    "power": false,
    "roomType": false,
    "sortField": "",
    "sortType": "",
    "windows": false
}
```

| 参数 | 说明 |
|---|---|
| `venueId` | 场馆 19 位雪花 ID (见下方映射) |
| `date` | 日期 `YYYY-MM-DD` |

#### 场馆 ID 映射

| 场馆 | venueId |
|---|---|
| 总馆 | `1812737769937670144` |
| 信息分馆 | `1812738485913751552` |
| 工学分馆 | `1812738878798401536` |
| 医学分馆 | `1812739190351302656` |

#### 查区域内具体座位

```
POST /jsq/static/frontApi/res/freeSeatIdsDuration/{areaId}/{date}
Body: { "beginMinute": 492, "endMinute": 0 }
```

返回每个座位的 19 位 UUID、label（桌贴号）、status（FREE/USED）。

#### 查时间线

```
POST /jsq/static/frontApi/res/getTimeLine/{areaId}/{date}
Body: {}
```

#### 查可用时段

```
POST /jsq/static/frontApi/res/getMakeSlices/{id}/{date}
Body: {}
POST /jsq/static/frontApi/res/findRoomSlice/{id}/{date}
Body: {}
POST /jsq/static/frontApi/res/getStartTimes/{id}/{date}
Body: {}
POST /jsq/static/frontApi/res/getEndTimes/{id}/{date}/{startMinute}
Body: {}
```

---

### 1.4 座位预约

#### 预约座位

```
POST /jsq/static/frontApi/make/freeBook/{seatId}/{date}/{startMinute}/{endMinute}?capToken={captchaToken}
Headers: token, loginType: PC, X-hmac-*, X-request-*
Body: {}
```

| 参数 | 说明 |
|---|---|
| `seatId` | 19 位座位 UUID (从 `freeSeatIdsDuration` 获取) |
| `date` | `YYYY-MM-DD` |
| `startMinute` | 开始分钟 (8:00 = 480) |
| `endMinute` | 结束分钟 |
| `capToken` | 验证码 token (从 `check` 成功响应中获取) |

#### 取消预约

```
POST /jsq/static/frontApi/reserve/cancel/{reservationId}
Body: {}
```

#### 预约记录

```
POST /jsq/static/frontApi/reserve/index
Body: { "currentPage": 1, "pageSize": 15 }
```

返回预约历史列表，含 `id`、`date`、`seatLabel`、`statusName` 等。

---

### 1.5 使用管理

#### 查询当前使用中座位

```
POST /jsq/static/frontApi/user/currentUseMake
Body: {}
```

返回当前正在使用的座位信息（`roomName`、`seatLabel`、`beginTime`、`endTime`）。

#### 结束使用（签退）

```
POST /jsq/static/frontApi/make/stop
Body: {}
```

---

### 1.6 用户

```
POST /jsq/static/frontApi/user/getUserInfo   # 获取用户信息
Body: {}

POST /jsq/static/frontApi/user/logout        # 登出
Body: {}
```

---

### 1.7 接口总览

| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| `cap/cg/gen/SLIDER` | POST | 无 | 获取滑块验证码 |
| `cap/cg/check` | POST | 无 | 提交滑块验证 |
| `frontApi/res/findRoomDuration/{venueId}/{date}` | POST | HMAC | 查分馆座位大盘 |
| `frontApi/res/freeSeatIdsDuration/{areaId}/{date}` | POST | HMAC | 查区域内具体座位 |
| `frontApi/res/getTimeLine/{id}/{date}` | POST | HMAC | 查时间线 |
| `frontApi/res/findRoomSlice/{id}/{date}` | POST | HMAC | 查房间时段 |
| `frontApi/res/getMakeSlices/{id}/{date}` | POST | HMAC | 查预约时段 |
| `frontApi/res/getStartTimes/{id}/{date}` | POST | HMAC | 查可用开始时间 |
| `frontApi/res/getEndTimes/{id}/{date}/{startMinute}` | POST | HMAC | 查可用结束时间 |
| `frontApi/make/freeBook/{...}?capToken=` | POST | HMAC | **预约座位** |
| `frontApi/make/stop` | POST | HMAC | **结束使用** |
| `frontApi/reserve/cancel/{id}` | POST | HMAC | **取消预约** |
| `frontApi/reserve/index` | POST | HMAC | 预约记录 |
| `frontApi/user/currentUseMake` | POST | HMAC | 当前使用中座位 |
| `frontApi/user/getUserInfo` | POST | HMAC | 用户信息 |
| `frontApi/user/logout` | POST | HMAC | 登出 |

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

## 三、完整 Python 实现（旧版 OpenCV 模板匹配，已废弃）

> 以下代码已被参考库差分法替代。保留供学习加密流程。

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
