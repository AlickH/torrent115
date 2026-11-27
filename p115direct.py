#!/usr/bin/env python3
"""115 直链：按 115 客户端协议加密请求 /app/chrome/downurl 拿签名下载地址。

直链签名绑定请求它的 User-Agent，下载时必须用同一个 UA，否则 CDN 返回
403 invalid signature。
"""
import base64
import json
import os
import time
import urllib.parse
import zlib

import net

API = "https://proapi.115.com/os_windows/2.0/ufile/downurl"
APP_VER = "36.2.28"

_N = int(
    "8686980c0f5a24c4b9d43020cd2c22703ff3f450756529058b1cf88f09b86021"
    "36477198a6e2683149659bd122c33592fdb5ad47944ad1ea4d36c6b172aad633"
    "8c3bb6ac6227502d010993ac967d1aef00f0c8e038de2e4d3bc2ec368af2e9f1"
    "0a6f1eda4f7262f136420c07c331b871bf139f74f3010e3c4fe57df3afb71683", 16)
_E = 0x10001
_KL = (_N.bit_length() + 7) // 8

_XOR_SEED = bytes([
    0xf0, 0xe5, 0x69, 0xae, 0xbf, 0xdc, 0xbf, 0x8a, 0x1a, 0x45, 0xe8, 0xbe, 0x7d, 0xa6, 0x73, 0xb8,
    0xde, 0x8f, 0xe7, 0xc4, 0x45, 0xda, 0x86, 0xc4, 0x9b, 0x64, 0x8b, 0x14, 0x6a, 0xb4, 0xf1, 0xaa,
    0x38, 0x01, 0x35, 0x9e, 0x26, 0x69, 0x2c, 0x86, 0x00, 0x6b, 0x4f, 0xa5, 0x36, 0x34, 0x62, 0xa6,
    0x2a, 0x96, 0x68, 0x18, 0xf2, 0x4a, 0xfd, 0xbd, 0x6b, 0x97, 0x8f, 0x4d, 0x8f, 0x89, 0x13, 0xb7,
    0x6c, 0x8e, 0x93, 0xed, 0x0e, 0x0d, 0x48, 0x3e, 0xd7, 0x2f, 0x88, 0xd8, 0xfe, 0xfe, 0x7e, 0x86,
    0x50, 0x95, 0x4f, 0xd1, 0xeb, 0x83, 0x26, 0x34, 0xdb, 0x66, 0x7b, 0x9c, 0x7e, 0x9d, 0x7a, 0x81,
    0x32, 0xea, 0xb6, 0x33, 0xde, 0x3a, 0xa9, 0x59, 0x34, 0x66, 0x3b, 0xaa, 0xba, 0x81, 0x60, 0x48,
    0xb9, 0xd5, 0x81, 0x9c, 0xf8, 0x6c, 0x84, 0x77, 0xff, 0x54, 0x78, 0x26, 0x5f, 0xbe, 0xe8, 0x1e,
    0x36, 0x9f, 0x34, 0x80, 0x5c, 0x45, 0x2c, 0x9b, 0x76, 0xd5, 0x1b, 0x8f, 0xcc, 0xc3, 0xb8, 0xf5,
])
_XOR_CLIENT = bytes([0x78, 0x06, 0xad, 0x4c, 0x33, 0x86, 0x5d, 0x18, 0x4c, 0x01, 0x3f, 0x46])
_RSA_CLIENT_KEY = bytes([0x8d, 0xa5, 0xa5, 0x8d])


# ── ECDH 传输层（115 客户端与服务器约定的固定会话密钥） ──────────────────
_CRC_SALT = b"^j>WD3Kr?J2gLFjD4W2y@"
_AES_PUBKEY = bytes.fromhex("1d030e80a178dceececda377de128d8ed9ddcf55ae61ed46ea121a1cfc81")
_AES_KEY = bytes.fromhex("fb1a19d652f5aaf7bc651d0f69bf422f")
_AES_IV = bytes.fromhex("69bf422f49960550a0ad44ec3446cb4c")


def _token(timestamp=0):
    body = bytearray()
    body += _AES_PUBKEY[:15]
    body += b"\x00s\x00\x00\x00"
    body += timestamp.to_bytes(4, "little")
    body += _AES_PUBKEY[15:]
    body += b"\x00\x01\x00\x00\x00"
    body += (zlib.crc32(_CRC_SALT + body) & 0xFFFFFFFF).to_bytes(4, "little")
    return base64.b64encode(bytes(body)).decode()


def _pkcs7_pad(data):
    size = 16 - len(data) % 16
    return data + bytes([size]) * size


def _pkcs7_unpad(data):
    if data and 0 < data[-1] < 16 and data[-data[-1]:] == bytes([data[-1]]) * data[-1]:
        return data[:-data[-1]]
    return data


def _aes_cbc(data, encrypt):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    cipher = Cipher(algorithms.AES(_AES_KEY), modes.CBC(_AES_IV))
    if encrypt:
        enc = cipher.encryptor()
        return enc.update(_pkcs7_pad(data)) + enc.finalize()
    data = data[:len(data) & -16]
    dec = cipher.decryptor()
    return _pkcs7_unpad(dec.update(data) + dec.finalize())


def _lz4_decompress(source):
    from lz4.block import decompress
    out = b""
    src = source
    while len(src) > 2:
        size = int.from_bytes(src[:2], "little")
        if not size:
            break
        out += decompress(src[2:size + 2], uncompressed_size=0x2000)
        src = src[size + 2:]
    return out


def _derive(seed, size):
    return bytes((((seed[i] + _XOR_SEED[size * i]) & 0xFF) ^ _XOR_SEED[size * (size - i - 1)]) for i in range(size))


def _xor(data, key):
    mod = len(data) % 4
    out = bytearray(data)
    for i in range(mod):
        out[i] ^= key[i % len(key)]
    for i in range(mod, len(out)):
        out[i] ^= key[(i - mod) % len(key)]
    return bytes(out)


def _rsa_encrypt(raw):
    out = bytearray()
    for start in range(0, len(raw), _KL - 11):
        chunk = raw[start:start + _KL - 11]
        pad = bytes(b % 0xFF + 1 for b in os.urandom(_KL - len(chunk) - 3))
        msg = b"\x00\x02" + pad + b"\x00" + chunk
        out += pow(int.from_bytes(msg, "big"), _E, _N).to_bytes(_KL, "big")
    return bytes(out)


def _rsa_decrypt(raw):
    out = bytearray()
    for start in range(0, len(raw), _KL):
        chunk = raw[start:start + _KL]
        val = pow(int.from_bytes(chunk, "big"), _E, _N).to_bytes(_KL, "big").lstrip(b"\x00")
        idx = next((i for i, b in enumerate(val) if b == 0 and i != 0), None)
        if idx is not None:
            out += val[idx + 1:]
    return bytes(out)


def encode(payload, key=None):
    key = key or os.urandom(16)
    body = bytearray(payload)
    body = _xor(bytes(body), _derive(key, 4))
    body = body[::-1]
    body = _xor(body, _XOR_CLIENT)
    return base64.b64encode(_rsa_encrypt(key + body)).decode()


def decode(text, key=None):
    """key 是编码时用的 16 字节随机种子；服务端在响应里回显它。"""
    raw = _rsa_decrypt(base64.b64decode(text))
    randkey, body = raw[:16], raw[16:]
    body = _xor(body, _derive(randkey, 12))
    body = body[::-1]
    return _xor(body, _derive(key, 4) if key else _RSA_CLIENT_KEY)


def download_url(cfg, pickcode, user_agent="Mozilla/5.0"):
    """返回该文件的签名直链。UA 必须与后续下载时发送的一致。"""
    if not cfg.get("p115_cookie"):
        raise RuntimeError("未登录 115")
    import re
    m = re.search(r"UID=(\d+)", cfg["p115_cookie"])
    payload = {"pickcode": str(pickcode)}
    if m:
        payload["user_id"] = int(m.group(1))
    seed = os.urandom(16)
    inner = {"data": encode(json.dumps(payload).encode(), key=seed)}
    body = _aes_cbc(urllib.parse.urlencode(inner).encode() + b"&", True)
    r = net.http_request(cfg, "POST", API,
                         params={"k_ec": _token(0), "app_ver": APP_VER},
                         data=body,
                         headers={"Cookie": cfg["p115_cookie"], "User-Agent": user_agent,
                                  "Content-Type": "application/x-www-form-urlencoded",
                                  "Referer": "https://115.com/"},
                         timeout=30)
    try:
        raw = _lz4_decompress(_aes_cbc(r.content, False))
        body_json = json.loads(raw.decode("utf-8", "ignore"))
    except Exception:
        raise RuntimeError(f"115 返回无法解析：{r.text[:120]}")
    if not body_json.get("state"):
        raise RuntimeError(f"115 拒绝获取直链：{body_json.get('message') or body_json.get('msg') or body_json}")
    info = json.loads(decode(body_json["data"], seed).decode("utf-8", "ignore") or "{}")
    for item in info.values():
        url = ((item.get("url") or {}) or {}).get("url") or item.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    raise RuntimeError("115 未返回下载地址")
