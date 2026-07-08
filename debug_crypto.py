"""Debug script to verify encryption matches JS behavior"""
import base64
import json
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util import Counter

# The real RSA public key from tac.min.js
REAL_RSA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDArgKannXgSG/WTmHP5ZdCsIhv
SxZQxZ2sQt9wXBm9SJyCN0nc3h6TL6fwaJJwELWwkJiVd/Fp2qtZPVsCk09opKQi
Xtbkxk+9ZzgxbYe5rrOXAPj+PZz+2b3J1L009FZ0W32bR3wuY6TDoyzKmmLceJMc
HDTK7g0RBcPvdUtWfQIDAQAB
-----END PUBLIC KEY-----"""

# Parse and check the key
rsa_key = RSA.import_key(REAL_RSA_PUBLIC_KEY_PEM)
print(f"RSA Key size: {rsa_key.size_in_bits()} bits")
print(f"RSA Key n (hex): {hex(rsa_key.n)[:80]}...")
print(f"RSA Key e: {rsa_key.e}")
print()

# Test data
test_data = b'{"test":"hello"}'
test_custom = b'{"session":{"url":"https://example.com"}}'

# Generate random session key and IV
session_key = get_random_bytes(16)
iv = get_random_bytes(16)
print(f"Session key (hex): {session_key.hex()}")
print(f"IV (hex): {iv.hex()}")
print()

# === AES-CTR Encryption ===
iv_int = int.from_bytes(iv, byteorder='big')

# Encrypt data
ctr = Counter.new(128, initial_value=iv_int)
cipher = AES.new(session_key, AES.MODE_CTR, counter=ctr)
encrypted = cipher.encrypt(test_data)

print(f"Encrypted data (hex): {encrypted.hex()}")
print(f"Encrypted data (b64): {base64.b64encode(encrypted).decode()}")
print()

# === RSA Encryption ===
key_iv_plain = f"{session_key.hex()}|{iv.hex()}"
print(f"Key|IV plaintext: {key_iv_plain}")

rsa_cipher = PKCS1_v1_5.new(rsa_key)
encrypted_key_iv = rsa_cipher.encrypt(key_iv_plain.encode('utf-8'))
ki_b64 = base64.b64encode(encrypted_key_iv).decode()
print(f"ki (b64): {ki_b64}")
print(f"ki length: {len(ki_b64)}")
print()

# === Test JSON.stringify wrapping ===
data_b64 = base64.b64encode(encrypted).decode()
print(f"data_b64: {data_b64}")
print(f"JSON.stringify(data_b64): {json.dumps(data_b64)}")
print()

# Check: what does the server get when receiving the full JSON?
payload = {
    "id": "test_id",
    "data": json.dumps(data_b64),  # With json wrapping
    "custom": json.dumps(data_b64),
    "ki": ki_b64
}
full_json = json.dumps(payload)
print(f"Full payload: {full_json[:200]}...")

# The server would parse this and get:
# data = '"base64string"'  (string with quotes)
parsed = json.loads(full_json)
print(f"Parsed data value: {repr(parsed['data'])}")

# What if we DON'T json wrap?
payload2 = {
    "id": "test_id",
    "data": data_b64,  # Without json wrapping
    "custom": data_b64,
    "ki": ki_b64
}
full_json2 = json.dumps(payload2)
print(f"Without json wrap: {full_json2[:200]}...")
parsed2 = json.loads(full_json2)
print(f"Parsed data value: {repr(parsed2['data'])}")
