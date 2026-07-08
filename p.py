import os
import base64
import json
import time
import random
import requests
import numpy as np
import cv2

# 密码学库，需要通过 `pip install pycryptodome` 安装
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.Util.Padding import pad
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util import Counter  # 引入用于 CTR 模式的标准计数器

# ==================== 测试配置区 ====================
# 替换为您的本地测试环境或私有 TAC 验证码服务地址
BASE_URL = "https://seat.lib.whu.edu.cn" 

# 测试用的 RSA 公钥 PEM 格式（请确保与您的测试服务端公钥一致）
MOCK_RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDXRMEk7baUetStHq6IPIxwKB9g
a9UyCepDEEFIZUS5cc1/FyS90Tbd1VA4j+AfqurclfBHUWgvuzAj4oW5b/sdS1SC
14259tLexFbT5EfPsyY0BPfMXkzUerSbzgL8ZIUtHfHV1z6/WA6iHVmB1SpWT2Bw
aE9Alednp9EO8dLQvQIDAQAB
-----END PUBLIC KEY-----"""
# ====================================================

class TianaiCaptchaAutomator:
    def __init__(self, base_url, rsa_public_key_pem):
        self.base_url = base_url
        self.session = requests.Session()
        # 导入服务端公钥，用于非对称加密
        self.rsa_key = RSA.import_key(rsa_public_key_pem)
        
        # 配置通用的标准浏览器标头
        self.session.headers.update({
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"
        })

    def solve_gap_offset(self, bg_base64, template_base64):
        """
        利用 OpenCV 模板匹配计算滑块缺口 X 轴物理位移
        """
        bg_bytes = base64.b64decode(bg_base64)
        template_bytes = base64.b64decode(template_base64)
        
        bg_img = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        template_img = cv2.imdecode(np.frombuffer(template_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        
        bg_edge = cv2.Canny(bg_img, 100, 200)
        template_edge = cv2.Canny(template_img, 100, 200)
        
        result = cv2.matchTemplate(bg_edge, template_edge, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)
        
        return max_loc[0]

    def generate_human_tracks(self, distance):
        """
        严格匹配后端实体类，输出校准的 x, y, t 轨迹
        """
        tracks = []
        current = 0
        mid = distance * 4 / 5  
        t = 0.1                 
        v = 0                   
        
        start_time = int(time.time() * 1000)
        
        tracks.append({
            'x': 0.0,
            'y': 0.0,
            't': 0
        })
        
        while current < distance:
            if current < mid:
                a = 2.5         
            else:
                a = -3.5        
            
            v0 = v
            v = v0 + a * t
            move = v0 * t + 0.5 * a * (t ** 2)
            current += move
            
            elapsed_time = int(time.time() * 1000) - start_time
            y_jitter = random.choice([-1, 0, 1])  
            
            tracks.append({
                'x': round(float(current), 2),
                'y': float(y_jitter),
                't': elapsed_time
            })
            time.sleep(random.uniform(0.01, 0.02))  
            
        total_time = int(time.time() * 1000) - start_time
        tracks.append({
            'x': float(distance),
            'y': 0.0,
            't': total_time + random.randint(10, 30)
        })
        
        return tracks, start_time

    def encrypt_payload(self, plain_data, plain_custom):
        """
        更新后的加密方法：引入标准的 128位 AES-CTR 计数器
        与前端 CryptoJS.enc.Utf8 序列化、CryptoJS.AES.encrypt 完全对齐
        """
        session_key = get_random_bytes(16)
        iv = get_random_bytes(16)
        
        # 1. 无空格序列化，确保字节流指纹一致
        data_json = json.dumps(plain_data, separators=(',', ':')).encode('utf-8')
        custom_json = json.dumps(plain_custom, separators=(',', ':')).encode('utf-8')
        
        # 2. 将 16 字节 IV 转换为 128 位大端整数作为计数器初始值
        iv_int = int.from_bytes(iv, byteorder='big')
        
        # 3. 加密 data
        ctr_data = Counter.new(128, initial_value=iv_int)
        cipher_data = AES.new(session_key, AES.MODE_CTR, counter=ctr_data)
        encrypted_data = cipher_data.encrypt(data_json)
        
        # 4. 加密 custom (由于是独立的加密调用，计数器状态需要重置为初始状态)
        ctr_custom = Counter.new(128, initial_value=iv_int)
        cipher_custom = AES.new(session_key, AES.MODE_CTR, counter=ctr_custom)
        encrypted_custom = cipher_custom.encrypt(custom_json)
        
        # 5. 编码转换。根据后端配置，可能需要 Hex 编码或 Base64 编码。
        # ------------------ 方案 A: 十六进制小写 (常用于新版 Java 后端) ------------------
        data_out = encrypted_data.hex().lower()
        custom_out = encrypted_custom.hex().lower()
        
        # ------------------ 方案 B: Base64 编码 (如果方案 A 报错，请取消下两行注释) ------------------
        # data_out = base64.b64encode(encrypted_data).decode('utf-8')
        # custom_out = base64.b64encode(encrypted_custom).decode('utf-8')
        
        # 6. 构造密钥交换数据 (明文格式: hex(key)|hex(iv))
        key_iv_plain = f"{session_key.hex().lower()}|{iv.hex().lower()}"
        
        # 7. 使用 RSA 公钥加密对称密钥信息 (注意：ki 的外层编码固定为 Base64)
        rsa_cipher = PKCS1_v1_5.new(self.rsa_key)
        encrypted_key_iv = rsa_cipher.encrypt(key_iv_plain.encode('utf-8'))
        ki_b64 = base64.b64encode(encrypted_key_iv).decode('utf-8')
        
        return data_out, custom_out, ki_b64

    def run(self):
        # 1. 申请验证码 (POST /gen/SLIDER)
        gen_url = f"{self.base_url}/jsq/static/cap/cg/gen/SLIDER"
        
        # 注意：部分安全级别高的后端会校验初始化指纹，此处可以使用空 JSON 
        # 如果服务端强制校验，则需要将 init_payload 的生成逻辑也套用上面的加密算法
        init_payload = {}
        
        print("[*] 正在向服务器请求滑块资源...")
        gen_response = self.session.post(gen_url, json=init_payload)
        if gen_response.status_code != 200:
            print(f"[-] 获取验证码资源失败: {gen_response.status_code}")
            return
        
        captcha_res = gen_response.json()
        captcha_id = captcha_res["id"]
        bg_b64 = captcha_res["captcha"]["backgroundImage"]
        temp_b64 = captcha_res["captcha"]["templateImage"]
        bg_raw = bg_b64.split(",")[-1]
        temp_raw = temp_b64.split(",")[-1]

        # 写入本地文件进行调试检查
        with open("debug_bg.jpg", "wb") as f:
            f.write(base64.b64decode(bg_raw))
            
        with open("debug_template.png", "wb") as f:
            f.write(base64.b64decode(temp_raw))
            
        # 2. 图像识别定位
        print("[*] 正在执行 OpenCV 图像缺口定位算法...")
        offset_x = self.solve_gap_offset(bg_raw, temp_raw)
        print(f"[+] 识别到滑块缺口偏移量: {offset_x} 像素")
        
        # 3. 模拟人类滑动轨迹
        print("[*] 正在规划并生成非线性运动轨迹...")
        track_list, start_time = self.generate_human_tracks(offset_x)
        end_time = start_time + track_list[-1]['t']
        
        # 4. 构造明文数据载荷
        # 注意：根据实际前端渲染比例，如果渲染宽度非原始图宽，可能需要等比例缩放 offset_x
        plain_data = {
            "bgImageWidth": 600,       
            "bgImageHeight": 360,
            "sliderImageWidth": 110,   
            "sliderImageHeight": 360,
            "startSlidingTime": start_time,
            "endSlidingTime": end_time,
            "trackList": track_list
        }
        
        plain_custom = {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "current_window_url": f"{self.base_url}/testing/"
        }
        
        # 5. 执行混合加密
        print("[*] 正在使用双层密码学机制加密特征载荷...")
        enc_data, enc_custom, enc_ki = self.encrypt_payload(plain_data, plain_custom)
        
        # 6. 提交服务器校验 (POST /check)
        check_url = f"{self.base_url}/jsq/static/cap/cg/check"
        check_payload = {
            "id": captcha_id,
            "data": enc_data,
            "custom": enc_custom,
            "ki": enc_ki
        }
        
        print("[*] 正在向服务器提交校验...")
        check_response = self.session.post(check_url, json=check_payload)
        print(f"[+] 响应状态码: {check_response.status_code}")
        print(f"[+] 校验接口返回: {check_response.text}")


if __name__ == "__main__":
    automator = TianaiCaptchaAutomator(BASE_URL, MOCK_RSA_PUBLIC_KEY)
    automator.run()