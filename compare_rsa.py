"""
生成 RSA 密钥对，公钥用于浏览器加密，Python 解密对比结构
"""
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
import base64, json

# 生成 1024-bit RSA 密钥对
key = RSA.generate(1024)
private_pem = key.export_key().decode()
public_pem = key.public_key().export_key().decode()

with open('test_key_private.pem', 'w') as f:
    f.write(private_pem)
with open('test_key_public.pem', 'w') as f:
    f.write(public_pem)

test_plain = 'a1b2c3d4e5f60718293a4b5c6d7e8f90|1a2b3c4d5e6f70819203a4b5c6d7e8f90'

# Python 加密
cipher = PKCS1_v1_5.new(key.public_key())
py_encrypted = cipher.encrypt(test_plain.encode())
py_ki = base64.b64encode(py_encrypted).decode()

print(f'Python ki: {py_ki}')

# 保存测试数据
with open('test_plain.txt', 'w') as f:
    f.write(test_plain)

# 输出浏览器 Console 命令
browser_cmd = f'''
// 复制到浏览器 Console 运行:
var testKey = `{public_pem}`;
var jsEnc = new JSEncrypt();
jsEnc.setPublicKey(testKey);
var plain = "{test_plain}";
var result = jsEnc.encrypt(plain);
console.log("BROWSER_KI:" + result);
'''

with open('browser_test_cmd.js', 'w') as f:
    f.write(browser_cmd)

print("浏览器 Console 命令已保存到 browser_test_cmd.js")
print("请在浏览器 Console 粘贴运行，把 BROWSER_KI: 后面的值复制给我")
print()
print(f"测试明文: {test_plain}")
print(f"Python ki: {py_ki}")
print()
print("拿到浏览器 ki 后，我就能解密对比两个密文的 PKCS#1 v1.5 内部结构")
