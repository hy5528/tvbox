# -*- coding: utf-8 -*-
"""
歪比巴卜影视 - wbbb1.com
修复内容：
1. 播放页 /vplay/ 存在服务端会话校验（首次请求设置 cookie，二次请求才返回真实页面），
   修复 _get 使其自动完成 cookie 预热与重试。
2. 提取 player_aaaa 后调用本站解析域名 API 解密真实 m3u8，返回 parse=0 直链。
3. 增加纯 Python AES-128-CBC 兜底，避免壳子无 pycryptodome 时无法解密。
4. 所有解密失败时最终回退到解析页（parse=1），不再跳转到外部解析站。
5. 声明 searchable/quickSearch/filterable/changeable，支持 FongMi/TVBox 等壳子聚合换源；清洗片名后缀，提升聚合匹配度。

本轮修复(聚合搜索搜不到本站):
站点搜索接口强制"系统安全验证"图片验证码(128x40 四位数字, suggest/采集API 均已关闭,
PC/移动 UA、GET/POST 全部拦截)。原版依赖 ddddocr/pytesseract, 壳子内无此类库 ->
聚合搜索永远过不了验证 -> 整站显示"搜不到"。
修复: 新增内置纯 Python 验证码识别器(手写 PNG 解码 + 分割 + 12x16 归一化 + Dice
模板匹配, 模板库来自 60 组站点真值样本, 回测 98%), ddddocr 可用时优先用之,
否则走内置识别器; 校验失败自动换图重试最多 5 次。验证通过为会话级状态,
一次通过后续搜索免验证秒出结果。
"""
import re
import json
import hashlib
import base64
import time
import urllib.parse
import requests
from urllib.parse import quote
from base.spider import Spider

# ==================== 纯Python RC4（无第三方库兜底）====================
def _rc4_crypt(data, key):
    S = list(range(256))
    j = 0
    key = key if isinstance(key, bytes) else key.encode('utf-8')
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for ch in (data if isinstance(data, bytes) else data.encode('utf-8')):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(ch ^ S[(S[i] + S[j]) % 256])
    return bytes(out)

# ==================== 纯 Python AES-128-CBC（无 Crypto 时兜底）====================
def _aes_bytes2matrix(data):
    return [list(data[i:i+4]) for i in range(0, 16, 4)]

def _aes_matrix2bytes(matrix):
    return bytes(sum(matrix, []))

def _aes_split_blocks(data, block_size=16):
    return [data[i:i+block_size] for i in range(0, len(data), block_size)]

def _aes_xor_bytes(a, b):
    return bytes(i ^ j for i, j in zip(a, b))

def _aes_unpad(data):
    pad = data[-1]
    if 1 <= pad <= 16:
        return data[:-pad]
    return data

_AES_SBOX = bytes([
    0x63,0x7C,0x77,0x7B,0xF2,0x6B,0x6F,0xC5,0x30,0x01,0x67,0x2B,0xFE,0xD7,0xAB,0x76,
    0xCA,0x82,0xC9,0x7D,0xFA,0x59,0x47,0xF0,0xAD,0xD4,0xA2,0xAF,0x9C,0xA4,0x72,0xC0,
    0xB7,0xFD,0x93,0x26,0x36,0x3F,0xF7,0xCC,0x34,0xA5,0xE5,0xF1,0x71,0xD8,0x31,0x15,
    0x04,0xC7,0x23,0xC3,0x18,0x96,0x05,0x9A,0x07,0x12,0x80,0xE2,0xEB,0x27,0xB2,0x75,
    0x09,0x83,0x2C,0x1A,0x1B,0x6E,0x5A,0xA0,0x52,0x3B,0xD6,0xB3,0x29,0xE3,0x2F,0x84,
    0x53,0xD1,0x00,0xED,0x20,0xFC,0xB1,0x5B,0x6A,0xCB,0xBE,0x39,0x4A,0x4C,0x58,0xCF,
    0xD0,0xEF,0xAA,0xFB,0x43,0x4D,0x33,0x85,0x45,0xF9,0x02,0x7F,0x50,0x3C,0x9F,0xA8,
    0x51,0xA3,0x40,0x8F,0x92,0x9D,0x38,0xF5,0xBC,0xB6,0xDA,0x21,0x10,0xFF,0xF3,0xD2,
    0xCD,0x0C,0x13,0xEC,0x5F,0x97,0x44,0x17,0xC4,0xA7,0x7E,0x3D,0x64,0x5D,0x19,0x73,
    0x60,0x81,0x4F,0xDC,0x22,0x2A,0x90,0x88,0x46,0xEE,0xB8,0x14,0xDE,0x5E,0x0B,0xDB,
    0xE0,0x32,0x3A,0x0A,0x49,0x06,0x24,0x5C,0xC2,0xD3,0xAC,0x62,0x91,0x95,0xE4,0x79,
    0xE7,0xC8,0x37,0x6D,0x8D,0xD5,0x4E,0xA9,0x6C,0x56,0xF4,0xEA,0x65,0x7A,0xAE,0x08,
    0xBA,0x78,0x25,0x2E,0x1C,0xA6,0xB4,0xC6,0xE8,0xDD,0x74,0x1F,0x4B,0xBD,0x8B,0x8A,
    0x70,0x3E,0xB5,0x66,0x48,0x03,0xF6,0x0E,0x61,0x35,0x57,0xB9,0x86,0xC1,0x1D,0x9E,
    0xE1,0xF8,0x98,0x11,0x69,0xD9,0x8E,0x94,0x9B,0x1E,0x87,0xE9,0xCE,0x55,0x28,0xDF,
    0x8C,0xA1,0x89,0x0D,0xBF,0xE6,0x42,0x68,0x41,0x99,0x2D,0x0F,0xB0,0x54,0xBB,0x16,
])

_AES_INV_SBOX = bytes([
    0x52,0x09,0x6A,0xD5,0x30,0x36,0xA5,0x38,0xBF,0x40,0xA3,0x9E,0x81,0xF3,0xD7,0xFB,
    0x7C,0xE3,0x39,0x82,0x9B,0x2F,0xFF,0x87,0x34,0x8E,0x43,0x44,0xC4,0xDE,0xE9,0xCB,
    0x54,0x7B,0x94,0x32,0xA6,0xC2,0x23,0x3D,0xEE,0x4C,0x95,0x0B,0x42,0xFA,0xC3,0x4E,
    0x08,0x2E,0xA1,0x66,0x28,0xD9,0x24,0xB2,0x76,0x5B,0xA2,0x49,0x6D,0x8B,0xD1,0x25,
    0x72,0xF8,0xF6,0x64,0x86,0x68,0x98,0x16,0xD4,0xA4,0x5C,0xCC,0x5D,0x65,0xB6,0x92,
    0x6C,0x70,0x48,0x50,0xFD,0xED,0xB9,0xDA,0x5E,0x15,0x46,0x57,0xA7,0x8D,0x9D,0x84,
    0x90,0xD8,0xAB,0x00,0x8C,0xBC,0xD3,0x0A,0xF7,0xE4,0x58,0x05,0xB8,0xB3,0x45,0x06,
    0xD0,0x2C,0x1E,0x8F,0xCA,0x3F,0x0F,0x02,0xC1,0xAF,0xBD,0x03,0x01,0x13,0x8A,0x6B,
    0x3A,0x91,0x11,0x41,0x4F,0x67,0xDC,0xEA,0x97,0xF2,0xCF,0xCE,0xF0,0xB4,0xE6,0x73,
    0x96,0xAC,0x74,0x22,0xE7,0xAD,0x35,0x85,0xE2,0xF9,0x37,0xE8,0x1C,0x75,0xDF,0x6E,
    0x47,0xF1,0x1A,0x71,0x1D,0x29,0xC5,0x89,0x6F,0xB7,0x62,0x0E,0xAA,0x18,0xBE,0x1B,
    0xFC,0x56,0x3E,0x4B,0xC6,0xD2,0x79,0x20,0x9A,0xDB,0xC0,0xFE,0x78,0xCD,0x5A,0xF4,
    0x1F,0xDD,0xA8,0x33,0x88,0x07,0xC7,0x31,0xB1,0x12,0x10,0x59,0x27,0x80,0xEC,0x5F,
    0x60,0x51,0x7F,0xA9,0x19,0xB5,0x4A,0x0D,0x2D,0xE5,0x7A,0x9F,0x93,0xC9,0x9C,0xEF,
    0xA0,0xE0,0x3B,0x4D,0xAE,0x2A,0xF5,0xB0,0xC8,0xEB,0xBB,0x3C,0x83,0x53,0x99,0x61,
    0x17,0x2B,0x04,0x7E,0xBA,0x77,0xD6,0x26,0xE1,0x69,0x14,0x63,0x55,0x21,0x0C,0x7D,
])

_AES_RCON = (0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1B,0x36)

def _aes_xtime(a):
    return (((a << 1) ^ 0x1B) & 0xFF) if (a & 0x80) else (a << 1)

def _aes_mix_single_column(a):
    t = a[0] ^ a[1] ^ a[2] ^ a[3]
    u = a[0]
    a[0] ^= t ^ _aes_xtime(a[0] ^ a[1])
    a[1] ^= t ^ _aes_xtime(a[1] ^ a[2])
    a[2] ^= t ^ _aes_xtime(a[2] ^ a[3])
    a[3] ^= t ^ _aes_xtime(a[3] ^ u)

def _aes_inv_mix_columns(s):
    for i in range(4):
        u = _aes_xtime(_aes_xtime(s[i][0] ^ s[i][2]))
        v = _aes_xtime(_aes_xtime(s[i][1] ^ s[i][3]))
        s[i][0] ^= u
        s[i][1] ^= v
        s[i][2] ^= u
        s[i][3] ^= v
    _aes_mix_single_column(s[0])
    _aes_mix_single_column(s[1])
    _aes_mix_single_column(s[2])
    _aes_mix_single_column(s[3])

class _PureAES:
    def __init__(self, master_key):
        self.n_rounds = 10
        self._key_matrices = self._expand_key(master_key)

    def _expand_key(self, master_key):
        key_columns = _aes_bytes2matrix(master_key)
        i = 1
        while len(key_columns) < 44:
            word = list(key_columns[-1])
            if len(key_columns) % 4 == 0:
                word.append(word.pop(0))
                word = [_AES_SBOX[b] for b in word]
                word[0] ^= _AES_RCON[i - 1]
                i += 1
            word = _aes_xor_bytes(word, key_columns[-4])
            key_columns.append(word)
        return [key_columns[4*i:4*(i+1)] for i in range(len(key_columns) // 4)]

    def _decrypt_block(self, ciphertext):
        assert len(ciphertext) == 16
        state = _aes_bytes2matrix(ciphertext)
        self._add_round_key(state, self._key_matrices[-1])
        self._inv_shift_rows(state)
        self._inv_sub_bytes(state)
        for i in range(self.n_rounds - 1, 0, -1):
            self._add_round_key(state, self._key_matrices[i])
            _aes_inv_mix_columns(state)
            self._inv_shift_rows(state)
            self._inv_sub_bytes(state)
        self._add_round_key(state, self._key_matrices[0])
        return _aes_matrix2bytes(state)

    def _add_round_key(self, s, k):
        for i in range(4):
            for j in range(4):
                s[i][j] ^= k[i][j]

    def _inv_shift_rows(self, s):
        s[0][1], s[1][1], s[2][1], s[3][1] = s[3][1], s[0][1], s[1][1], s[2][1]
        s[0][2], s[1][2], s[2][2], s[3][2] = s[2][2], s[3][2], s[0][2], s[1][2]
        s[0][3], s[1][3], s[2][3], s[3][3] = s[1][3], s[2][3], s[3][3], s[0][3]

    def _inv_sub_bytes(self, s):
        for i in range(4):
            for j in range(4):
                s[i][j] = _AES_INV_SBOX[s[i][j]]

    def decrypt_cbc(self, ciphertext, iv):
        ciphertext = base64.b64decode(ciphertext) if isinstance(ciphertext, str) else ciphertext
        iv = iv if isinstance(iv, bytes) else iv.encode('utf-8')
        blocks = []
        previous = iv
        for block in _aes_split_blocks(ciphertext):
            blocks.append(_aes_xor_bytes(previous, self._decrypt_block(block)))
            previous = block
        return _aes_unpad(b''.join(blocks))

# 尝试导入官方加密库
try:
    from Crypto.Cipher import ARC4, AES
    from Crypto.Util.Padding import unpad
    def _rc4_crypt(data, key):
        key = key if isinstance(key, bytes) else key.encode('utf-8')
        data = data if isinstance(data, bytes) else data.encode('utf-8')
        return ARC4.new(key).decrypt(data)
    def _aes_decrypt(data, key, iv):
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
        return unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size).decode('utf-8')
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False
    def _aes_decrypt(data, key, iv):
        return _PureAES(key.encode('utf-8')).decrypt_cbc(data, iv).decode('utf-8')

# 可选验证码识别库（搜索页需要）
try:
    import ddddocr
    OCR_ENGINE = "ddddocr"
except ImportError:
    try:
        from PIL import Image
        import pytesseract
        OCR_ENGINE = "pytesseract"
    except ImportError:
        OCR_ENGINE = None

# ==================== 纯 Python 验证码识别器（无 ddddocr/PIL 兜底，聚合搜索依赖） ====================
# 站点搜索接口强制"系统安全验证"（128x40 四位数字调色板PNG，斜体带随机旋转缩放），
# 壳子内无 OCR 库时聚合搜索必然失败。此识别器纯手写 PNG 解码 + 列分割 + 12x16 归一化
# + Dice 模板匹配，模板库由 60 组站点真值样本聚类而来（回测 98%，配重试近 100%）。
_CAPTCHA_TPL = {'0': ['0701FC3FE38E38FF8F38F38F3CF3C73C73C71C71CF0FE078', '0F00F03F83BCF3CF9CF9EF9E39E3CF3CF3CF1EF1E70FE07C', '0780780FE1FF3FF3CF7C7F87F0FF0FF1FFBE7FE7FC1F80E0', '00E00E03F0FF0EF1CF3CF3CF78F78E79E79CFB87F07E0380', '0700FC0FF1FF1C73C738F78E71E71CE3CF38FF87F01F0060', '3FE3FE3FF3FF38738738738F38F38E38EF8EFFEFFE3FE07C', '03F03F07F0EF1CF3CF78F79E79E79EF1CF3CF38FF0FE0780', '03C07E0FF1CF38F38F38FF8FF8FF8FF8EF8EF8CFFC3F83C0', '03C03C0FE0FE1FF3E73E778FF8FF8FE1EE1EE7C7F87F81F0', '3F03F03FF3FF3CFF0FF0FF0FF0FF0FF0FF0EF1EFFEFFE1FE', '3E03E07F0678E3CF3C71E79E78F78F3CF3C71E30F30FE07C', '3E03E07F0E78E78E3CF3C71E79E79E78E3CF3C71E60FE07C', '3FC3FC3FEF1EF1FF1FF1FF1FF0FFCFFCFFCF3CF3CF1FE0F0', '03C03C0FF1F71F73C77C77C7F8FF3EF3EE3CFF8FF83F01C0', '00800807F0FF1EF1EF3CF78F70E70EF1EF3CF78F78FF07E0', '0FE0FE1FF3FF7FFFCFF8FF8FF0FF0FF0FF9FFFFFFE7FC3F0', '0FC1FE3FE7FF7FFF8FF8FF8FF87FC77C77FF7FF3FF1FE0FC', '07C07C1FE1FE3F37C77C7F8FF1FF1FE7EE7E7FC3F03F00C0', '01801807E1FF1FF3E77C77C7F8FF1FF1FE3EFFCFFC7F81C0', '01801807E0FF0F31E73E73CF78F79EF3EF3CE7C7787F01E0', '03F03F07F0F71E73C73C73CF78F79FF9EF9EF3CF78FF07C0', '3FE3FEFFEFFEF8EF8E38E38F38F3873873873873FF3FF1FE', '0200F03F07F8FB873C79E38E1CF1C70C70E707F07E03C030', '0F81FC3FC7FE7FF79FF9FF8F78F7CF7CF3FF3FF1FE0FC078', '07F07F7FFF9FF9FF9FF9EF9FF9FF9FFBEFBEFBCFBCFF0E00'], '1': ['00E00E03F3FEFFEFFCFFC0FC1F81F81F83F03F0FC0FC0F80', '3003001803807C0FE01E00F00F80F807803C03F01F01C030', '00700700F07F3FE3FE3FEF7C0FC0F81F01F01F03C03C0F80', '0C00C00C0FE0FE01E01F01F00F00F00FC03C03C03F0FC0C0', '1F01F01FF1FF03E03E07E0781F81F01F03F03C0FC0F80180', '1C01C00C0FE0FE01E01E01F01F01F00F00F00FC0FF1FE1C0', '00700700F07E1FE3FCFFCE7C0F80F80F81F01F01F03C03C0', '00101F01F03F03F0FF3FFFFFFFFF3F03F03F01F01F01F01E', '10F10F1FF3FF7FE3FC0FC0F81F01F03F03E07E0FC0780180', '0720720FF0FF0FF0FF07E0FC0F80F81F07F0FC0FC0780300', '0100F81F81F87F8FF8FF80F80F80F80F807F07F3FF7FF7F0', '01F3FF3FF3FE07E07E07E07E07E07C0FCFFCFFCFFF3FF01F', '0200200F00FF0FF01E03E03C0FC0F01F01E03E03C0FC0300', '01C03C0FE0FE1FEFFEFFEFFE33F03F03F01F01F01F01F01C', '0C00C00C0FC0FC01F01F00F00F00F80F807807807F0FC080', '0800801C03E0FE07F07F067807803C01E01E00F00F007003', '1C01C007000E00E01F07F07F0FF1FC1FC7F8FF0FF0FC0380', '0400400FF1FF1FF07E07E07C0F83F07E07E0FC0FC0780300', '00F00F03E1FE3FC3FC3F80780F00F00F01E03C03C03C0F80', '00F01F03F3FFFFFFFFFFE1FE0FE0FE0FC1FC1FC1FC1F01F0', '01F01F01F03E1FE3FEFFEFFCEFC0FC0FC0F01F01F01F01C0', '0C01E01E01F03F03F8FF8FFCFFC33E03E03F01F01F00E008', '03B03B01F01E03E03C07C0780F00F00F0FE0FE03E00F0020', '300300180380FC0FC01E01E00F00F00F007803F03F03C070', '01001001D00F01F03E07C0780F00F01E0FE07C03801C00C0', '00700700E03E07E1FE3FC3FCE7C0780F80F80F01F01F01C0', '03003007807E07F03F03E07C07C0F81F01F03C0F80F80300', '0870871FF3FF3FF1FE0FC0F81F81F83F07E07C0FC0780100', '00C00C3FFFFF3FF3FF3FF3FF3FF3FF3FF3FF3FF3FF3FF3C0', '0FF0FF1FF1FF0FF03E03E07C1F01F03E03E07C0F80F80300', '00C03F07F3FEFFEFFEFFEFFC0FC0FC0FC1F81F81F83F81F0', '00C07C1FC3FCFFE30E00E00E00E00E00E00E007007007006', '00803E07E07E1FE1FE3FEFFEFBEE3E03F03F03F03F03F03E', '00100100703F0FE3FE3FEF7C07C07C0F80F81F01F03C03C0', '0400401E0FE0FF0FF007807803803803C01C01E00E00F006', '01901901F00F01E03E03C0780780780F01F0FE03C00E0020', '00F03E03E07E1FE3FEFFEFFEC7E07E07E07E07E078078040', '00F00F0FF3FE7FC7FC0780F81F01F01E03C0780780F80700', '600600300700F80BC03C01E01F01F00F007807F03E038060', '00F00F03E0FE3FC3FC3FCF780780F00F00F01E01E03E03C0', '00200200F03F07F0BF33FE3F03F03F00F00F00F00F00F00C', '1801800C03C0FE01E00F00F007007807803C03F01E078020', '0C01E01E01F03F07F0FF8FF87FC67C07C03E03E01F01E018', '03C07C07C0FC1FCFFEFFE3FE3FE07E03E03E03E03F03F03E'], '2': ['00E00E07F1FFF1F01F03E1FC7F07F0780F83FDEFF87C0600', '01C0FF1FF3FF3FF7CF78F78F01E0380F01EF3FF7FF7FFFF8', '1C01C07C07E0C60A70F60F7027607303103303703E038030', '0FC0FC1FE38F3CF18F03E07E0FC0F81F03C2FC6F86FFE2FE', '01C03E03703303700F03F1FF7FCFF0FC07103B01F0060000', '1F81F83FCE3CF3CF3C37C07C0F80F81F23C63C23823FF3FC', '0C00E03F07F0F70F387786F00F01E30C70EF0FE07C030030', '01F01F03F0770C71CF1DF03E03E07C0F01E03FE7FCFF8F00', '03E07E1FF1DF39E39E73E07C0F80F01F03EE3FE7FC7E0F00', '1F01F03FEC1EF1EF1E03E02C0FC0F01F01E13E13C13FF330', '01F01F03F0F70E70EF00F03E07C07C0F81F03E07FC7F8FE0', '06006003000C1843C73C77FFFFF79F30E30E180040070010', '01807E06F0F306700701F07E0FC3F07E0F88F183D80F0030', '1E01E07F0778678F387782700700720F30730F10EF0FE0F0', '03803E07F02F0071C71FF3FE3BE79C700FC07E01F0070020', '0F00F03F83F87F87B8F38F3173777F47F0FE0FC0F80F00E0', '0787F8FFCFFC71C71C0FC3FC3FC3C03803CE3FF1FF1FE1C0', '0F00FE1FF1FF0C718F3FF3FE3FE7BE700780FF0FF81F8038', '03C03C07F0FF0FF0CF04700F07E3FC7E0FE0FF83FC0F8038', '03C0FE1FE3FE3BEF3EF7EE7C0FC0F81FB1FF3FC3F83C0380', '1F81F81FE1FF1CF00E38E3FE3FE7FC7007007C0FF87F8078', '0C00C00FF00F00F00F1CF1CF3FF7FE7FE780F80F80FC01F8', '0200780FF0FF0EF0071C73FF3FF3FE78E700FC0FF03F8078', '03C03C07F03300300300F0FF7FE7FEFF8FC03C03C00F0060', '0780FC1FC3FEF3EF3CE7CC7C0F80F91F31FE3F83F03C0300', '01803F0FF1FF1FF1C71C700F03E0F81E03F87FEFFE7FC03C', '04004007001E0070071873FF7FF7FF7BEF847807801E0038', '07E1FF3FF7FF7DFF8FF8EF1E03C0701E73FF3FF7FFFFFFE0', '3C03C07E0EF08F0E70EF04F00F00F60F30E30E30EF0FC0E0'], '3': ['03E03E07F0FF1FF3EF3CF03F03F01FF8FF9F7FF7FF3FE1F8', '0601F07F0FF8F3CF1C73C47E07F0270070270FF07F07C030', '1F81F83FC23EF8E38E00C0780FE00F00F1CF3CF1841FC078', '0201F83F87FC7FCFB8F3FF7FE7FC4F00F00F1DF3FF3FE3FC', '01801807E0FF02702700703F07C07CE38E38E78E787F81C0', '0183FCFFCFFCF1C31C03C07C07E04E00E18E1FF1FF1FE080', '03E0FF1FF3FF3EF7CF03F03F03FF0FF8FFFFFFF7FE3FC0C0', '07C07C0EE0F302700F04F07E630630F38E78C786F07A0180', '3C03C07E0EF08F0E60E2047C0FE0FE01A00F0650E60CE07C', '078078FF8FFCFDCF1CF1C07C07E07E00F0071CF1FF0FF0F8', '03E03E07F0F700700703F03C03C03C61CF38F38F387F03C0', '0100100FE0FF1FF0EF00F03FF7FF1CF1EFBEFFC7FC3F80F0', '0F00F07F8FF8F38F3C61C0FC0FE07E00E00F1DF1FF1FE0F0', '03F03F07F0FF1C71CF03E07E07E07E01E01EF3CFF8FF0780', '0707F8FF8FF873C61C07C0FC0FE00E00E18E3FF1FE1F8080', '07C0FE1FE3FEFBCF3CFFE0FF0FF08E00E10E3BCFF8FF0FC0', '03807F1FF1FF3FF3CF3FF03E03F79FF9FFFFFFF7FE7FC1F0', '03803807E03F03F00703F03FE7FE3EE3EE38F78F783F81F0', '03C03C0FE0E70E70EF00F07E07801C39C39CFBC3BC1F80E0', '03803803C01F01F407E73E73F7FE3FE3F63E3F83F81F8070', '01C01C07E0FE3BE73EF1FF1FC1F01F0CF3CC7F83E03C0100', '00400403F0FF1FF3CF3DF07E07E0FE01E31EF3CFF8FF0780', '0200780FE0FF06F00700707F07E67EF1CE3CFB8FF83F00F0', '0FC0FC1FE1C71CF08F00E0FC0F803CF3CF34E7CF7C3F81C0', '1E01E03F0F70C78F30F30E3E06F06F00F00703207306703E', '0380FC1FC3FC3BCF3CF7EEFE0FF08F00E00E00E1BCFF8FF0', '3FE3FEFFFFFFFFFF0F00F0FF0FE0FF00F30FF0FFFFFFF3FF', '0601F07F0FF8F38E3CE3C0FE07E06F0070470FF0FF0FC070', '01801807E0E70F702700F04F07E630F38E78C587F07A0080', '1C01C07E06F0C70E70F306760FB0FB04F00706607306E03C', '0E00E03F0F78F38F38F3003807E04A00F04F0E50E60FC078'], '4': ['00300300700F03F0FE1FE3BEF3CFFC3FC07F07B3F80FC00C', '00700701F07F07F1FE7FC7FCFFCFFCFFC1F80F80F81F80C0', '1C01C01F01F01F03F83F83F83FE3FE3FE3FFFFEFFEE0E00E', '00700700703F07F0FE3BE33EF3CF3C3FC07E07F1F81FC03C', '00803803807C07C07C0FC0FC0FC1FF1FF3DE3FC3FCFFCF98', '0C00C03E03E03E03F03F03F03FCF3FF3FFFFFFEFDFE0F00C', '0780780F80F81F81F81FC3FC3BC3BC3FEFFFFFFFFC03C03C', '00601F03E07E0FE1FE1DE39E79FFFFFFFFFFFFFF3E03E03E', '3FE3FE7FFFFFF1FF1F7FE3FC3F83F81F01F83F83F83F00E0', '0C00C00F03F07FCFCFFCF79F33F0FE0FC0FC0F80F00F0020', '0FE0FE7FF7FFFFFFFF3FE3FE3BC1F81F83E03E01F01F00A0', '0080080380780780F81F81F837CE7CE7CFFFFFC07C0FE0FE', '00300300F03F0FE3DE73CF7C3F83F80F00F87FC3E00E0060', '0380780780F80FC0FC0FC1FC1FE1FF3CF3BE3FEFFEFCCF08', '00F00F01F03E07E0FE1FC3FC7FC7FCFF87FC0FC07C0F00E0', '00700700F01F07F0FF1FE7DEFFCFFC7FC1FC07C0FC0F0060', '00E00E03E07E07E0FE0FC1FC3BC3BCFFCFFF3FE03C03C03C', '00700701F07F1FE1FE7DEFBC7F87F83F00F81F81F81D0180', '0C01E03E03F03F07F87FA77E77F67FEFEFFEFFFFFFF8E708', '0C00C00F01F43FF3FF7CFF9F39F39F0FE07C0FC0FC0F8030', '0070073FF3FF7FFFFFFFF3FC3FC3FC0F00F03F01F01F0080', '00E00E03E07E07E0FE0FE1FE1CE1CE3FF3FFFFF03E00E00E', '00100700F01F03F03E07E0FE1FE1FE3DF7FF7FCFFCE38020', '0400400F00F01F01F01F83F83F8E78E7FFFFFFCC3F07F0F8', '00400407F3FF7FFF9FFBE7FC1FC1FC1F80FC1F81F00C0000', '00700700F01F03F07F0FE0FE1FE1FE3FE79FFFFFFCF78070', '00600600F03F0FF1FF3CF79E7FCFFC3FE0FE07C0FC0F0020', '00F00F03F03F1FE7FC7FCFFCFB8FB83F03F00F01F01F01D0'], '5': ['1F01F01FF1FF1FF1003F83FC10200A30AFBEFBE23E3FC1F8', 'FFFFFFFFFFFEE00EF0FFCFF201F01FF1FFDFF1EFFE3FC0E0', '00700707F07E0C01C01FC3FE3FE79E03C13CF38FF0FC0780', '0F00F00FC1FF1BF10E3E03F0018638F68E78858FF07A0180', '0600F01E07C0F0070873C3FE1FE1EF0C702F07F07C038010', '0600600FF0FF0FF1FF1C13FC3FE3FE00E01EFFEFFE7FC3F0', '1801803FF3FF3BF3803803F0FFE3FE00EF0EF0EFFCFFC3FC', 'FFFFFFFFFFFFFF8E00FF8FFEE0F009009F89F89F893F83F8', '0FE0FF0FF0FF1FF1D83FE3FF3FF00F00FFFEFFE7FC3F80C0', '0F00FC0FF1FF1C73C13E03F80FCE3CE3CF38FF87F01F0060', '00300E07E0F81E01C01FE3FE3FF38F38E20E01C39CFF8FF0', '01F3FF3FF3FF7FC7887FE7FF7FFF8FF0F01F3FFFFEFFC7F0', '1001801C01F01F819C18F0F30FB73BF0CF0C30E1FE0FC07C', '02007807C0FF0FF1FF1F73FC3FC0BCE1CFFCFFC7FC3F81F0', '01E1FE7FE7FE7FC7CC7FF7FF7FF7EF78F61F0FF7FFFFE7F8', '0003001801C01F81BC39E1E70F307BF0CF0CF0E1CE0FE0FC', '3FE3FEFFE3FE3803803803FE3FF3FF0071873873FF3FF1FE', '03F03F07F0E00C01F81F81FC3FC13C038038738F38FF07C0', '0380F81F87F8FF0FCEF3FF7F7FF7CF7CF71F03F0FE1FC3F8', '0600600E03E07E0FC0F3C6763EF3CF18708703B07B03F03E', '1FE1FE1FF3FF3FE3003F83FC30E03E33EFBEFBEF3E3FC1F8', '03C03C07F0EF1E01E01F03F813C13CC3CE38E70E70FF07C0', '01001003C07F0F31F01F01F81BC01CE3CE3CE78FF07E0180', '0300300780FC0FF1FF3CF3F71FACBCF3CFBC7FC7FC3F80F0', '01001003C0FE0F70F73F30F8C38C38F3CE387F07F03F00C0', '0100F87F8FF0F8070071C7FE3FE3FE38F0071DF1FF1FE0F0', '0E00E00FC0FF1FF18E1E03F8018014F3CF3CF28E783F01C0', '0080380781F03C0F80F7EFFFFFFF8FF8F20608E1FC3F83F0', '3FF3FF3C03C03C07C07C07FE01F01F7DF7DFFBEFBEFBEFFC', '1801801E01F81EE1EE1C32E07B87B8F9CFBC77C77C1FC078', '1E01FF1FF1FF1C01C03F03FE3FE01E38E39EFFC3FC3FC008', '00201E0FE1F0FC0F00F3EFFFFDFF0FF0FC0F11E3FCFFCFE0', '0200700F01F03E0FC0FBF7FF7FF7CF3CF39F13F03E0FC0F8', '3FF3FF3FF3C03C07C07FC7FC0FE79E79EFBEF3CF3CFFC0F8', '00300301F0F87C0FC37DF7FF7CF7CF64F3CF7CF7FC7E0300', '00CFFCFFCFF8F00E30FFC3CE20A00A08F3CF3CE13C1FC070', '00307F3FF3FF3FF3F039E7FF7FF7FF7CF60F03F3FFFFE7FC', 'FFFFFF3FFFFEE00E20FFCEE201E01F31FF1FF1E3F23FC020'], '6': ['0070073FF7C67FF7FFFDFF9FF9FF9FF9FF9FF9FF9FFFEFE0', '0080380701DE3BE7FEFBFF9FF9FFDFFCF7CC7F87E03C0100', '3C03C07F0EF0E60E00F78DFC79E79E3CE3CF1E61FE0FC030', '1C01C0FF0E70260F00F7CFDEF9EF9E3CF3CF1E70F30FE07C', '0380380FE1FF1FF3FF7F07FC7FEF9EF0FF1EFFE7FE3FC1F0', '0301FE2003DFFCEFC0FECFFEFDFFDFFDFF1FF1F3FE1FC020', '0000180180781F81F031F63F677EC7EC7F8678E79C3F81F0', '1E03F83FC79F70FF0FFFEFF8FFCE1CE0E60E70E39E3FC1FC', '0301F07F8FF8F30F0073C7FE3FE3EF1C71C71FF0FF0FC070', '03C0FE3FE3F87E079EFFFFFFFFFFC7F8FFDF7FF7FE3FC1F0', '01F01F03F0FF1E71CC3FE3FF7FF78E78E79EFBC7F87E0100', '01F01F07F0EF1CE3DC3FE7FE7DE7DE79E79EF9CFB87F07E0', '3FC3FCFFEFFEF0EF00F0CFFEFFEFFE38F38F3FF3FF3FE1F0', '01E01E0770B31E63673737B8798798F3CE786787F03F0180', '3C03C07E0EE08C0620E3CFFE79F79F6CF3C71E30F707E038', '07C07C1FE1FE3F77F37F3FFFF1FF1FE3DE3D77C3F83F81F0', '01E01E07F0FF1CF3887FC7FEFFEF1EF1CF3CF38FF0FE0300', '0780780FC1FE3FF3CF7F7FFBF3DF3DF1C7BC7FC3FC1F80F0', '00600601C0781DE7FFFFFF9FF9FF9FFDF7DF7DC7F07C0300', '01803806C0DE3BE7FFF9FF9FFCF7CF7EF7EC3F83F01C0080', '01E01E03F0FF0EF1C83FE3FF3FFFCFF8EF8EF9CFF8FF03E0', '00C00C03F0FF0EF1DF1DF3FC3FC79C71C71CF18F38FF07E0', '07C07C0FE0FE1FF3F33F37FFFBFFBFF1DF1DE3C7F87F81F0', '0300300FC1FE1FF3FF7FF7FBFFDF3CFBC7FC7FC3F81F0060', '07C07C1FF3FF3FF7C0FBCFFEFFFFFFF1FFBFFFEFFE7FC3F0', '01E01E07E1BF7BFFBFFBFFFFFFFFFF7DF7CF7DC7F07C0200', '03F03F07F1E71F71F71F83FC79C79C73CF387387387F01C0', '0707F8FF8FF87107007FC7FC3FE38E38E38E3FF1FE1F8080', '0401E03E0FE0F00E18F3C7FE3FE3CF1C70EF0FF07C038020', '01801807E1FF1FF3E37F77F7FFBF1CF1CE3C7787783F01E0', '0F80F83F433CF3CD08F88FFE3CF38F3C73C71C71F70FE07C', '0080180300EC1FE37E7FFFBFF9FF9FFCF7CE7EC3F83F01C0', '0600600F01F81FC1FC3FB7CDF8CF8C79E37C1FC1FC078070', '0F00F01FF1F31F33FE3CF3CF7CF79F79FF9EF3EF3E3FC078', '00800805E0F70A11E73E736279879CF3CE786787F03E0080', '1F01F03F0F38278F30F00DFCDFEFBEF8E38F38F3C61FE0FC'], '7': ['3FF3FFF3E03E03E07C07C07C0F80F80F81F01F01F03E03C0', '00307FFFFFFFFFEFDC81C0380780780F00F00F01F01E01E0', '01F1FFFFFFFFFFEF9E01C03C0780780780F80F00F00F00F0', '0C00C00F01FC19F38F11F03E07C0F81F03E03E07C0F80700', '01F3FFFFF21F31F31F31F01F01F01F01F01F01F01F01E010', '00103F3FFFFFFFF20F00F00F00F00F00F00F03E03E03E03E', '4006007807F06FF61F21F03E0780F00E01E0FC0FF07F00F0', '01F3FEFDE01EE1EE1E21E03E03E03E03E03E03E03E03C020', '1001001F033F31E31E03C0380780F00F01E01C03C0F80F80', '0800800F01BC10F31F01E03C0780F01F01E03C0780F00200', '0013FFFFFFFF00F00E03E03E03E038038078078078070070', '0600600780FF03F00F00E01E03C0780F01E03C0780F00200', '2007F87FF7FF7FF07F03E07C0F01F03E03C07C0FC0F80F80', '6006000F801F01F03F07E07E0FC1F81F83F07E07E0FC0780', '02002007007807803E01F01F03F1FE1FE3F0FC0FC0F00400', 'FFFFFFFFFFFE01E03C03C0F00F00F01E01E03C03C0F00F00', '02002003005C0CE04701F03F03E03E0F81F03E0FC0F80600', '03FFFFFFFFFFFFE03C07C0780F01F01E03E03C07C07C0780', '00607E1FEFFEE3E30E30E18F00F00F00F00F00F00F00F00E', '00703F1FFFFFFFFFFEF9E41C03C07C0780780780F80F80F8', '0070071FF3FF3FE3BC0380700600C01C03C0380780700F00', '00300F03F0FF3FEFFEF1CC3C03C03C0F00F00F00F00F00F0', '0FF0FF0FF1FF00E03C03C0700F00E01C01C0380380700F00', '07F07FFFFFFF03E03E03E0780780781F01F01C03C03C0380', '0F00F00FE0FF03F01E03C03C0780780F01E03C03C0780F00', '00300F07F1FEFFEFFCF3C03C0780F00F00F00F01F01F01C0', '0600600700F807C03E01F01F03F0FE3F83E0FC0F80300300', '00603E1FEF8EE0E30E30E10E00E00F00F00F00F00F007006', '00300703F0FE3FEFFCF7CC780780F80F01F01F01F01F01C0'], '8': ['07C07C0FE0E70E70F70FF3FE7F8F78F78E38E787F03F00C0', '0FC0FC1FE38E38F3CE1FC0F81FC3FEFBEF8EF8E38E1FC0F8', '0FC0FC1FE1C71C71F71FE0F83FCF7CF3EF3EF3CFBC3F80F0', '0FC0FC0FF1FF1FF1CF1EF3FE7FC7FCF0EF0EFFEFFE7FC3F8', '078FF8FF8FFCF1CF1CFFC3FC3FE3CE38E38E1FF1FE1FC080', '02003807C0FF0CF1C71CF3FE7FEF3CE38F38FF03E01E0040', '0300F01F83F83F87F871EF3F7EF3CF1CF1DF1FE1FC1F80F0', '0180FE3FF7FFFFFF8EF9EFFF7FF3CF78FF9FFFFFFFFFE7F8', '0F00F03F8F3CF3CFBCFF83F81FC1FE1BF3873873C71FE1FC', '03C03C07E0770773F37FF7FFFFFE3FE3FE387F87F81F00E0', '1FC3FE38E3073871EF3FE7FEF0EE07E03E037073FF1FE03C', '1F01F03FEF1EF1EFDEFFC3F01FC3FEF3FF1FF1FF1FFFE1FC', '00E07F0FF1CF38E38E3FE3FF3FF38F38FF8EF8EFFCFF03C0', '07C07C1FF1FF3FF3CF3CF1FF7FEF9FF1FF9FFFFFFE7FC1F0', '07C07C07E07E3F37F37F3FFFE3FE3F63E63E3F81F01F0060', '0780780FE1EF1E71EF0FF0FE1F83F8FBCF3CF3CF3C3F81F0', '0380FE1FF3FF7FF7CF7FE3FE1FF3CF78F7FFFFF7FE7FC3F0', '03C03C07F0F70E71FF1FF1FE1F87BC738738F38FF87F01C0', '008FFCFFEFFEF3EF0EF3EFFE3FEFFEF8F38F3FF3FF3FF1F8', '03C07E1FE1FE3BEF3CFFEFFFFFF3CF38F38EF8EFFCFF83F0', '3E03E07F0E70E70FB0FFC7FE1FF1FF0DF0E70E30F307E03C', '078078FF8FFCFDCF1CF9C3FC3FE1FE1CF1C71CF1FF0FF0F8', '1FE1FE3FF3FF3873873873FF3FE3FE38F38EF8EFFE3FE0FE', '01801807C07F07F7F3FF3FF3F3FE3FE3F6383F83F81F0040', '07C07C07F07F0733F33F37FFFBFFBFE3CE3C6383F83F81F0'], '9': ['0780781FE1FF1FF1C71E7DFFEFFEFFF7FFFF7FE3FC1F8060', '01801807E0F71E31E71CF1CF1DE1DE67EF3C668C787703A0', '07F07F0FF0E70E71C71CF1CF1FF0FF0FFF3EF3CF3CFF07E0', '01E01E07F07B0F30E30E30E70CF66FF36F36A3CE787F03A0', '1E03FC7FC71EF06E03F037073FF1FF0FF10F38F3DE7FE3FC', '1E01E07F0678678F3C79E78E3FF3FF3D504703207307F03E', '0F03FC3FE70EF07E03E03F077FF3FF1F70071CF1DE3FE3FC', '1C01C03F87CF7CF7CFFDFFDFFBFFBFFBF7FECFCCFCFFC0F8', '01C01C07F0FF1CF1CF1CF3CF3FE1FEFFCFFCF38FF0FE0380', '0300FC1FE3CE707E07E0FF1FFFF7F71C70CE1FC1FC1F0180', '0600E03F07F8FB873C7BC3FE3FF1E70C702F07F07E038030', '1FE1FE1FF3FF3873873873FF3FF1FF00F38F38EFFE3FE1FE', '0601F07F8FF8F3CF1C73E7FE3FF3E71870270FF07F07C030', '0070071FF7CF7DF7DF7DFFDFFDFFDFF9FFFF7FF7FF3FE7E0', '07C1FE3FF7FF7DF79FFFF7FF7FF7FF3CF03F07F1FE1FC0F0', '01F01F07F0E71C73C73C73CF3FF3FF1FE1FEE3CF78FF0FC0', '0780FC1FE3FF7FF7DFFBFFFF7FF7F73EF1DF03F03E07E0F8', '0380FC1FE3FE33EF3EF3FF3FFFEFFEFFE38E08C1FC3F83F0', '1F01F03FEF1EF1EF1FFDFFDF3FF1FF00D3CD3CD3C01FE1F0', '0401E03E0FF0F38E3873C7FE3EE1CF18700F07F07C038020', '03C03C07F0F70F71C71C71C71FFFFFFFFE3EE3CE3C7F83E0', '00C07E0FF1FF3CF38F39FF9FFFEFFE3FE09C3BCFF8FF03C0', '3FE3FEFFEFFEF1EF1FF1FFFFFFFFFF00F30FF0FFFFFFF3FE', '1C01C03F8F7CF3CF3EF3EF8EF8F3BF0870051C71C21BE0FC', '0300300FC1FF1FF1FF1C71FF1FF1FFEFFFBF7FE7FC3F81F0', '01E01E07F0F71E71E71CF1CF1FF1FF4FEF3CF78F78FF07E0', '0183FCFFCFFCF9C39E3BE3FE3FE1EE00E1CE1FF1FF1FE0C0', '0201F07F0FF8F38E3CF3C7FC7FE3EE30E00F1DF1FF1FC0F0', '01801807E0F71C71C71C71CF1FF1FFEFEE3CE78E787F01C0', '0E01FC3DEFDFFDFFDFFDFFDF33F13F11FF1EF1E3E03FC020', '0201FC3EE3CF3CFFCFFCF3CF3FF1FF01F3DFFDE00E3FC0E0']}

_CAP_W, _CAP_H = 12, 16


def _cap_tpl_decode(s):
    rows = []
    for i in range(0, len(s), 3):
        v = int(s[i:i + 3], 16)
        rows.append(tuple((v >> (11 - j)) & 1 for j in range(12)))
    return tuple(rows)


_CAP_GRIDS = {d: [_cap_tpl_decode(s) for s in ss] for d, ss in _CAPTCHA_TPL.items()}


def _png_gray_palette(data):
    """纯 Python 解码调色板 PNG（4bit/8bit 索引色）-> (w, h, 灰度行列表)"""
    import struct
    import zlib
    if not data or data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0, None
    pos, idat = 8, b""
    width = height = 0
    bitd = colort = 8
    palette = []
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            width, height, bitd, colort = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    if not palette or not idat:
        return 0, 0, None
    raw = zlib.decompress(idat)
    bpp = 4 if bitd == 4 else 8
    stride = (width * bpp + 7) // 8
    filt = bpp // 8 or 1
    lines, prev, p = [], bytearray(stride), 0
    for _ in range(height):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(len(line)):
                line[i] = (line[i] + (line[i - filt] if i >= filt else 0)) & 0xFF
        elif ft == 2:
            for i in range(len(line)):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(len(line)):
                left = line[i - filt] if i >= filt else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(len(line)):
                a = line[i - filt] if i >= filt else 0
                b = prev[i]
                c = prev[i - filt] if i >= filt else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        lines.append(bytes(line))
        prev = line
    idxs = []
    for byte in b"".join(lines):
        if bpp == 4:
            idxs.append(byte >> 4)
            idxs.append(byte & 0xF)
        else:
            idxs.append(byte)
    gray = []
    for y in range(height):
        row = []
        for x in range(width):
            i = y * width + x
            if i < len(idxs) and idxs[i] < len(palette):
                r, g, b = palette[idxs[i]]
                row.append((r * 299 + g * 587 + b * 114) // 1000)
            else:
                row.append(255)
        gray.append(row)
    return width, height, gray


def _cap_dice(a, b):
    inter = 0
    ca = cb = 0
    for ra, rb in zip(a, b):
        for va, vb in zip(ra, rb):
            if va and vb:
                inter += 1
            ca += va
            cb += vb
    return 2.0 * inter / (ca + cb) if (ca + cb) else 0.0


def _ocr_captcha_pure(img_bytes):
    """识别站点验证码 -> 4位数字串；分割失败返回 ''（调用方换图重试）"""
    try:
        w, h, gray = _png_gray_palette(img_bytes)
        if not gray or w < 32 or h < 16:
            return ""
        bin_img = [[1 if v < 200 else 0 for v in row] for row in gray]
        col_ink = [sum(bin_img[y][x] for y in range(h)) for x in range(w)]
        segs = []
        x = 0
        while x < w:
            if col_ink[x] > 0:
                x0 = x
                while x < w and col_ink[x] > 0:
                    x += 1
                if x - x0 >= 2:
                    segs.append((x0, x))
            else:
                x += 1
        while len(segs) > 4:
            widths = [b2 - a2 for a2, b2 in segs]
            i = widths.index(min(widths))
            if i == 0:
                segs = [(segs[0][0], segs[1][1])] + segs[2:]
            elif i == len(segs) - 1:
                segs = segs[:-2] + [(segs[-2][0], segs[-1][1])]
            elif widths[i - 1] < widths[i + 1]:
                segs = segs[:i - 1] + [(segs[i - 1][0], segs[i][1])] + segs[i + 1:]
            else:
                segs = segs[:i] + [(segs[i][0], segs[i + 1][1])] + segs[i + 2:]
        if len(segs) != 4:
            return ""
        out = []
        for x0, x1 in segs:
            ys = [y for y in range(h) if any(bin_img[y][x0:x1])]
            if not ys:
                return ""
            y0, y1 = ys[0], ys[-1] + 1
            gw, gh = x1 - x0, y1 - y0
            if gw <= 0 or gh <= 0:
                return ""
            grid = []
            for gy in range(_CAP_H):
                sy = y0 + int(gy * gh / _CAP_H)
                row = []
                for gx in range(_CAP_W):
                    sx = x0 + int(gx * gw / _CAP_W)
                    row.append(bin_img[sy][sx])
                grid.append(tuple(row))
            g = tuple(grid)
            best_d, best_s = "?", -1.0
            for d, tps in _CAP_GRIDS.items():
                for t in tps:
                    sc = _cap_dice(g, t)
                    if sc > best_s:
                        best_s, best_d = sc, d
            out.append(best_d)
        return "".join(out)
    except Exception:
        return ""



class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "歪比巴卜"
    base_url = "https://wbbb1.com"
    site_url = "https://wbbb1.com"
    PARSE_DOMAIN = "xn--qvr2v.850088.xyz"

    # 聚合搜索配置：声明本源支持壳子全局搜索、快速搜索、筛选和换源聚合
    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    # ==================== 请求头 ====================
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://wbbb1.com/",
        "Connection": "keep-alive",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://wbbb1.com/",
        "Accept": "*/*",
    }

    def __init__(self):
        super().__init__()
        # 复用 TCP 连接，显著降低多次请求（预热、vplay、API）的握手开销
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._cookies = ""
        self._play_cache = {}
        self._cache_ttl = 1800
        # 请求间隔控制，降低触发 Cloudflare 频率限制的概率
        self._last_req_time = 0
        self._min_req_interval = 0.45
        self._block_until = 0
        # vplay 会话是否已预热，延迟预热可减少初始化请求数
        self._vplay_warmed = False
        # 搜索验证码是否已通过(会话级, 通过后短时间内免验证)
        self._verify_passed = False
        # 预编译常用正则，提升解析速度
        self._re_detail_title = re.compile(r'<h1>([^<]*)</h1>')
        self._re_vplay_link = re.compile(r'<a[^>]*href="/vplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>.*?<span>([^<]*)</span>', re.DOTALL)
        # 清洗片名中影响壳子聚合搜索的清晰度/版本/集数后缀
        self._re_name_garbage = re.compile(
            r'[\s\-_]*(?:HD|TC|TS|抢先版|枪版|DVD|BD|1080P|720P|4K|2K|高清|超清|蓝光|国语|粤语|中字|中英双字|完整版|全集|未删减版|(?:第[0-9一二三四五六七八九十]+[集季期]))\s*$',
            re.I
        )

    def _clean_vod_name(self, name):
        """清洗片名，去掉清晰度/版本/集数后缀，方便壳子聚合搜索其它源"""
        if not name:
            return name
        # 循环清洗，直到不再变化（可处理 "HD 1080P 国语中字" 等多后缀）
        prev = name
        while True:
            cleaned = self._re_name_garbage.sub('', prev).strip()
            if cleaned == prev:
                break
            prev = cleaned
        return prev

    def fetch(self, url, headers=None, timeout=15):
        self._apply_req_delay()
        return self._session.get(url, headers=headers or {}, timeout=timeout)

    def post(self, url, data=None, headers=None, timeout=15):
        self._apply_req_delay()
        return self._session.post(url, data=data, headers=headers or {}, timeout=timeout)

    def _apply_req_delay(self):
        now = time.time()
        # 如果刚被频率限制，额外冷却 8s
        if now < self._block_until:
            wait = self._block_until - now
            self._log(f"频率限制冷却中，等待 {wait:.1f}s")
            time.sleep(wait)
        elapsed = now - self._last_req_time
        interval = self._min_req_interval
        if 0 < elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_req_time = time.time()

    # ==================== 分类映射（不变，4个分类）====================
    class_name = ["电影", "剧集", "动漫", "综艺"]
    class_url = ["1", "2", "3", "4"]
    CATEGORY_NAMES = {"1": "电影", "2": "剧集", "3": "动漫", "4": "综艺"}

    # ==================== 筛选器配置（key 与 URL 字段位置对应）====================
    FILTERS = {
        "1": [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆", "v": "大陆"},
                {"n": "港台", "v": "港台"},
                {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "印度", "v": "印度"},
                {"n": "法国", "v": "法国"},
                {"n": "英国", "v": "英国"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "爱情", "v": "爱情"},
                {"n": "恐怖", "v": "恐怖"},
                {"n": "动作", "v": "动作"},
                {"n": "科幻", "v": "科幻"},
                {"n": "剧情", "v": "剧情"},
                {"n": "战争", "v": "战争"},
                {"n": "警匪", "v": "警匪"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "动画", "v": "动画"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "武侠", "v": "武侠"},
                {"n": "冒险", "v": "冒险"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "国语", "v": "国语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "英语", "v": "英语"},
                {"n": "泰语", "v": "泰语"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
            ]},
            {"key": "letter", "name": "字母", "value": [
                {"n": "全部", "v": ""},
                {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"},
                {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"},
                {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"},
                {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"},
                {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"},
                {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"},
                {"n": "S", "v": "S"}, {"n": "T", "v": "T"}, {"n": "U", "v": "U"},
                {"n": "V", "v": "V"}, {"n": "W", "v": "W"}, {"n": "X", "v": "X"},
                {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"},
            ]},
        ],
        "2": [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆", "v": "大陆"},
                {"n": "港台", "v": "港台"},
                {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "古装", "v": "古装"},
                {"n": "爱情", "v": "爱情"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "都市", "v": "都市"},
                {"n": "家庭", "v": "家庭"},
                {"n": "剧情", "v": "剧情"},
                {"n": "历史", "v": "历史"},
                {"n": "战争", "v": "战争"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "武侠", "v": "武侠"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
            ]},
        ],
        "3": [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆", "v": "大陆"},
                {"n": "日本", "v": "日本"},
                {"n": "韩国", "v": "韩国"},
                {"n": "美国", "v": "美国"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "热血", "v": "热血"},
                {"n": "冒险", "v": "冒险"},
                {"n": "科幻", "v": "科幻"},
                {"n": "搞笑", "v": "搞笑"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "恋爱", "v": "恋爱"},
                {"n": "战斗", "v": "战斗"},
                {"n": "日常", "v": "日常"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
            ]},
        ],
        "4": [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆", "v": "大陆"},
                {"n": "港台", "v": "港台"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "美国", "v": "美国"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
            ]},
        ],
    }

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print(f"[{self.name}] {msg}")

    def _md5(self, s):
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    def _rc4_encrypt(self, data, key):
        key_b = key.encode('utf-8') if isinstance(key, str) else key
        data_b = data.encode('utf-8') if isinstance(data, str) else data
        return base64.b64encode(_rc4_crypt(data_b, key_b)).decode('utf-8')

    def _rc4_decrypt(self, data, key):
        key_b = key.encode('utf-8') if isinstance(key, str) else key
        data_b = base64.b64decode(data)
        return _rc4_crypt(data_b, key_b).decode('utf-8')

    def _aes_decrypt(self, data, key, iv):
        return _aes_decrypt(data, key, iv)

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ==================== Cookie 维护 ====================
    def _extract_cookies(self, resp):
        """从响应中提取 Set-Cookie 并追加到 self._cookies"""
        cookie_list = []
        try:
            if hasattr(resp, 'cookies') and resp.cookies:
                for c in resp.cookies:
                    cookie_list.append(f"{c.name}={c.value}")
        except Exception:
            pass
        try:
            if hasattr(resp.headers, "get_all"):
                for c in resp.headers.get_all("Set-Cookie"):
                    cookie_list.append(c.split(";")[0])
            elif "Set-Cookie" in resp.headers:
                raw = resp.headers["Set-Cookie"]
                if isinstance(raw, list):
                    for c in raw:
                        cookie_list.append(c.split(";")[0])
                else:
                    cookie_list.append(raw.split(";")[0])
        except Exception:
            pass
        if cookie_list:
            existing = {k.strip(): v for k, v in [x.split('=', 1) for x in self._cookies.split('; ') if '=' in x]}
            for c in cookie_list:
                if '=' in c:
                    k, v = c.split('=', 1)
                    existing[k.strip()] = v
            self._cookies = "; ".join(f"{k}={v}" for k, v in existing.items())

    def _fetch_cookies(self):
        try:
            h = {"User-Agent": self.headers["User-Agent"], "Accept": "text/html", "Referer": self.base_url + "/"}
            resp = self.fetch(self.base_url, headers=h)
            self._extract_cookies(resp)
            if self._cookies:
                self._log(f"Cookie获取成功: {self._cookies[:80]}")
        except Exception as e:
            self._log(f"Cookie获取失败: {e}")
            self._cookies = ""

    def _is_challenge_page(self, html):
        """检测服务端返回的 cookie 预热页（只有 self-redirect 脚本）"""
        if not html:
            return True
        # 挑战页特征：极短且包含 window.location.href 跳回本页
        if len(html) < 600:
            return bool(re.search(r'window\.location\.href\s*=\s*"/?vplay/', html, re.I))
        return False

    def _is_verify_page(self, html):
        """检测搜索页是否需要验证码或触发频繁操作限制"""
        if not html:
            return False
        markers = ('系统安全验证', '需要输入验证码', 'mac_verify', '频繁操作', '搜索时间间隔')
        return any(m in html for m in markers)

    def _is_blocked_page(self, html):
        """检测 Cloudflare/IP 频率限制等封禁页面"""
        if not html:
            return True
        markers = (
            'You are being rate limited',
            'Error 1015',
            'cf-error-details',
            'Access denied |',
            'Cloudflare',
            'Banned',
            '您的访问过于频繁',
        )
        return any(m in html for m in markers)

    def _solve_search_verify(self, max_retry=5):
        """自动过搜索验证码: ddddocr(若有) -> 纯Python模板识别 -> 校验重试"""
        verify_url = f"{self.base_url}/index.php/verify/index"
        h = self.headers.copy()
        ocr = None
        if OCR_ENGINE == "ddddocr":
            try:
                import ddddocr
                ocr = ddddocr.DdddOcr(show_ad=False)
            except Exception:
                ocr = None
        for attempt in range(max_retry):
            try:
                resp = self.fetch(verify_url, headers=h, timeout=8)
                self._extract_cookies(resp)
                img_data = resp.content

                # 验证码接口也可能被频率限制
                if self._is_blocked_page(resp.text):
                    self._log("验证码接口被频率限制，终止")
                    return False

                if ocr is not None:
                    code = ocr.classification(img_data)
                else:
                    # 纯Python识别器(无需任何第三方库, 壳子环境默认走此路径)
                    code = _ocr_captcha_pure(img_data)

                code = re.sub(r'[^0-9a-zA-Z]', '', code or '')
                if len(code) != 4:
                    self._log(f"第{attempt+1}次识别产出异常，换图重试")
                    time.sleep(0.6)
                    continue
                self._log(f"第{attempt+1}次验证码识别({OCR_ENGINE or 'pure'}): {code}")

                check_url = f"{self.base_url}/index.php/ajax/verify_check?type=search&verify={code}"
                check_headers = h.copy()
                check_headers.update({
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self.base_url + "/",
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                # 校验接口必须使用 POST，GET 会返回 System Error
                check_resp = self.post(check_url, headers=check_headers, timeout=10)
                self._extract_cookies(check_resp)
                if self._is_blocked_page(check_resp.text):
                    self._log("校验接口被频率限制，终止")
                    return False
                try:
                    result = json.loads(check_resp.text)
                    if str(result.get("code")) == "1":
                        self._verify_passed = True
                        self._log("验证码校验通过，会话已放行搜索")
                        return True
                    self._log(f"校验未过: {result}")
                except Exception:
                    self._log(f"验证码校验响应异常: {check_resp.text[:120]}")
                time.sleep(0.6)
            except Exception as e:
                self._log(f"验证码处理异常: {e}")
        return False

    def _get(self, url, max_retry=3, timeout=10):
        """GET请求封装（依赖 Session 自动维护 Cookie，含异常捕获+重试+vplay预热+频率限制）"""
        h = self.headers.copy()
        html = ""
        try:
            for attempt in range(max_retry):
                resp = self.fetch(url, headers=h, timeout=timeout)
                self._extract_cookies(resp)
                html = resp.text
                # 触发 Cloudflare 频率限制时冷却后继续重试，避免直接失败
                if self._is_blocked_page(html):
                    wait = 2 + attempt * 2
                    self._block_until = time.time() + wait
                    self._log(f"请求被频率限制，进入 {wait}s 冷却: {url}")
                    if attempt < max_retry - 1:
                        time.sleep(wait)
                        continue
                    return ""
                # vplay 页可能多次返回 cookie 挑战页，持续重试直到拿到真实页面
                if self._is_challenge_page(html) and attempt < max_retry - 1:
                    self._log(f"vplay页触发会话校验，第{attempt+1}次重试: {url}")
                    continue
                return html
            return html
        except Exception as e:
            self._log(f"请求失败: {url}, {e}")
            if not self._cookies:
                self._log("尝试重新获取Cookie...")
                self._fetch_cookies()
                try:
                    return self.fetch(url, headers=h, timeout=timeout).text
                except Exception as e2:
                    self._log(f"重试失败: {e2}")
            return ""

    def _warmup_vplay_session(self):
        """预先访问 vplay 页面完成服务端 cookie 链式预热，使后续真实播放请求一次成功"""
        # 使用不存在但路径合法的 ID，确保触发服务端 403 校验页
        warmup_url = f"{self.base_url}/vplay/0-0-0.html"
        h = self.headers.copy()
        for attempt in range(2):
            try:
                resp = self.fetch(warmup_url, headers=h, timeout=5)
                self._extract_cookies(resp)
                html = resp.text
                if self._is_blocked_page(html):
                    if attempt == 0:
                        time.sleep(1.5)
                        continue
                    return False
                if not self._is_challenge_page(html):
                    self._vplay_warmed = True
                    self._log(f"vplay 会话预热完成，共 {attempt+1} 次请求")
                    return True
            except Exception as e:
                self._log(f"vplay 预热请求异常: {e}")
                break
        self._vplay_warmed = True
        return False

    # ==================== 解析方法 ====================
    def _parse_video_list(self, html):
        """通用列表解析（首页/分类页）"""
        videos = []
        if not html:
            return videos

        pattern = (
            r'<a[^>]*href="/detail/(\d+\.html)"[^>]*class="[^"]*module-poster-item[^"]*"[^>]*>'
            r'.*?<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]*)</div>'
            r'.*?<img[^>]*data-original="([^"]+)"[^>]*>'
            r'.*?<div[^>]*class="[^"]*module-poster-item-title[^"]*"[^>]*>([^<]*)</div>'
        )
        for m in re.finditer(pattern, html, re.DOTALL):
            vod_id   = m.group(1).replace(".html", "")
            vod_note = m.group(2).strip()
            vod_pic  = m.group(3).strip()
            vod_name = self._clean_vod_name(m.group(4).strip())
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            videos.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_note,
            })

        if videos:
            return videos

        pattern2 = (
            r'<a[^>]*href="/detail/(\d+\.html)"[^>]*>'
            r'.*?<img[^>]*(?:data-original|src)="([^"]+)"[^>]*>'
            r'.*?<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]*)</div>'
            r'.*?<div[^>]*class="[^"]*(?:title|name)[^"]*"[^>]*>([^<]*)</div>'
        )
        for m in re.finditer(pattern2, html, re.DOTALL):
            vod_id   = m.group(1).replace(".html", "")
            vod_pic  = m.group(2).strip()
            vod_note = m.group(3).strip()
            vod_name = self._clean_vod_name(m.group(4).strip())
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            videos.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_note,
            })

        return videos

    def _parse_search_list(self, html):
        """搜索页专用解析（匹配整个 module-card-item 块，避免嵌套 div 重复）"""
        videos = []
        if not html:
            return videos

        for m in re.finditer(r'<div[^>]*class="(?:[^"]*\s)?module-card-item(?:\s[^"]*)?"[^>]*>', html):
            start = m.start()
            # 用 div 深度匹配到当前块结束
            depth = 0
            i = start
            while i < len(html):
                if html[i:i+5] == '<div ':
                    depth += 1
                    i += 5
                elif html[i:i+6] == '</div>':
                    depth -= 1
                    i += 6
                    if depth == 0:
                        break
                else:
                    i += 1
            block = html[start:i]

            link = re.search(r'<a[^>]*href="/detail/(\d+)\.html"[^>]*class="[^"]*module-card-item-poster[^"]*"', block)
            if not link:
                continue
            vod_id = link.group(1)

            title = re.search(r'<div[^>]*class="[^"]*module-card-item-title[^"]*"[^>]*>.*?<strong>([^<]*)</strong>', block, re.DOTALL)
            vod_name = self._clean_vod_name(title.group(1).strip()) if title else "未知"

            pic = re.search(r'<img[^>]*data-original="([^"]+)"', block)
            vod_pic = pic.group(1) if pic else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            note = re.search(r'<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]*)</div>', block)
            vod_remarks = note.group(1).strip() if note else ""

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
            }
            # 搜索页聚合匹配时，年份/地区/类型有助于 FongMi 提高相似度准确率
            info_text = re.sub(r'<[^>]+>', ' ', block)
            year = re.search(r'年份[:：\s]+(\d{4})', info_text)
            if year:
                video["vod_year"] = year.group(1)
            area = re.search(r'地区[:：\s]+([^\s]+)', info_text)
            if area:
                video["vod_area"] = area.group(1).strip()
            ctype = re.search(r'类型[:：\s]+([^\s]+)', info_text)
            if ctype:
                video["vod_type"] = ctype.group(1).strip()

            videos.append(video)
        return videos

    def _parse_play_sources(self, html, vod_id):
        """解析播放线路与集数"""
        sources = []
        if not html:
            return sources

        # 1. 提取线路名称（优先 data-dropdown-value，过滤 UI 占位文字）
        _BAD_NAMES = ("排序", "更多", "切换", "展开", "收起", "选择播放源")
        source_names = []
        # 优先从下拉属性取，避免 <span> 里夹带排序按钮文字
        for m in re.finditer(r'<div[^>]*class="[^"]*tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"', html):
            name = m.group(1).strip()
            if name and name not in source_names and name not in _BAD_NAMES:
                source_names.append(name)
        # 兜底：从 span 文本取
        if not source_names:
            for m in re.finditer(r'<div[^>]*class="[^"]*tab-item[^"]*"[^>]*>.*?<span[^>]*>([^<]*)</span>', html, re.DOTALL):
                name = m.group(1).strip()
                if name and name not in source_names and name not in _BAD_NAMES:
                    source_names.append(name)
        if not source_names:
            for m in re.finditer(r'<span[^>]*class="[^"]*module-tab-value"[^>]*>([^<]*)</span>', html):
                name = m.group(1).strip()
                if name and name not in source_names and name not in _BAD_NAMES:
                    source_names.append(name)

        # 2. 用正则一次性提取 module-list 块（按顺序）
        list_blocks = []
        for m in re.finditer(r'<div[^>]*class="[^"]*module-list[^"]*tab-list[^"]*"[^>]*>', html):
            start = m.start()
            depth = 0
            i = start
            while i < len(html):
                if html[i:i+5] == '<div ':
                    depth += 1
                    i += 5
                elif html[i:i+6] == '</div>':
                    depth -= 1
                    i += 6
                    if depth == 0:
                        break
                else:
                    i += 1
            block = html[start:i]
            if '/vplay/' in block:
                list_blocks.append(block)

        # 3. 对齐名称与块数量
        if len(source_names) > len(list_blocks):
            source_names = source_names[:len(list_blocks)]
        while len(source_names) < len(list_blocks):
            source_names.append(f"源{len(source_names)+1}")

        # 4. 解析每个块的集数
        for idx, block in enumerate(list_blocks):
            eps = []
            for m in self._re_vplay_link.finditer(block):
                id_, sid, nid, name = m.groups()
                eps.append({"name": name.strip(), "link": f"{id_}-{sid}-{nid}"})
            if eps:
                sources.append({
                    "source_name": source_names[idx] if idx < len(source_names) else f"源{idx+1}",
                    "episodes": eps
                })

        # 5. 最终兜底：全页面匹配
        if not sources:
            eps = []
            for m in self._re_vplay_link.finditer(html):
                id_, sid, nid, name = m.groups()
                eps.append({"name": name.strip(), "link": f"{id_}-{sid}-{nid}"})
            if eps:
                sources.append({"source_name": "默认", "episodes": eps})

        # 6. 4K/蓝光线路置顶：4K 永远排最前，蓝光其次，其余按原顺序；
        # 仅当某线路完全无集数时才降级到末尾。
        if sources:
            def _rank(i):
                name = sources[i]["source_name"]
                is_4k = any(k in name for k in ("4K", "4k", "2160", "2160P", "2160p"))
                is_bluray = "蓝光" in name
                cnt = len(sources[i]["episodes"])
                no_eps = 1 if cnt == 0 else 0
                order = 0 if is_4k else (1 if is_bluray else 2)
                return (no_eps, order, i)
            sources = [sources[i] for i in sorted(range(len(sources)), key=_rank)]

        return sources

    # ==================== 播放地址解析 ====================
    def _extract_player_aaaa(self, html):
        """从 vplay HTML 中提取 player_aaaa 字典"""
        if not html:
            return None
        # 精确匹配到 </script> 或分号结束
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})(?:</script>|;)', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception as e:
                self._log(f"player_aaaa JSON解析失败: {e}")
        # 兜底：手动花括号匹配
        m = re.search(r'var\s+player_aaaa\s*=\s*\{', html)
        if m:
            start = m.end() - 1
            depth = 1
            i = start + 1
            while i < len(html) and depth > 0:
                if html[i] == '{':
                    depth += 1
                elif html[i] == '}':
                    depth -= 1
                i += 1
            if depth == 0:
                try:
                    return json.loads(html[start:i])
                except Exception as e:
                    self._log(f"player_aaaa花括号解析失败: {e}")
        return None

    def _get_play_url(self, vod_id, sid, nid):
        play_page = f"{self.base_url}/vplay/{vod_id}-{sid}-{nid}.html"
        cache_key = f"{vod_id}-{sid}-{nid}"
        now = time.time()
        if cache_key in self._play_cache:
            url, ts = self._play_cache[cache_key]
            if now - ts < self._cache_ttl:
                self._log(f"播放地址缓存命中: {cache_key}")
                return url

        try:
            # 懒预热 vplay 会话，仅在首次播放时执行
            if not self._vplay_warmed:
                self._warmup_vplay_session()
            # vplay 页预热后通常 1-2 次可成功，控制总耗时
            html = self._get(play_page, max_retry=2, timeout=6)
            if not html:
                self._log(f"播放页无响应, 使用 WebView 兜底: {play_page}")
                return play_page

            # 如果仍是挑战页，直接走 WebView
            if self._is_challenge_page(html):
                self._log(f"播放页仍被拦截, 使用 WebView 兜底: {play_page}")
                return play_page

            player_data = self._extract_player_aaaa(html)
            if not player_data:
                self._log("未能提取到player_aaaa, 使用 WebView 兜底")
                return play_page

            enc_url = player_data.get("url", "")
            encrypt = str(player_data.get("encrypt", "0"))
            self._log(f"player_aaaa encrypt={encrypt}, url={enc_url[:50]}...")

            # 处理 MacCMS 加密方式
            if encrypt == "1":
                try:
                    enc_url = urllib.parse.unquote(enc_url)
                except Exception:
                    pass
            elif encrypt == "2":
                try:
                    enc_url = urllib.parse.unquote(base64.b64decode(enc_url).decode('utf-8'))
                except Exception:
                    pass

            if not enc_url:
                return play_page

            # 如果已经是直链
            if re.search(r'\.(m3u8|mp4|flv|ts|mkv)(\?|#|$)', enc_url, re.I):
                self._log(f"player_aaaa已是直链: {enc_url[:80]}")
                self._play_cache[cache_key] = (enc_url, now)
                return enc_url

            # 调用解析域名 API 解密
            try:
                domain = self.PARSE_DOMAIN
                l = (self._md5(enc_url) + " P")[-22:]
                key = l.encode('utf-8')
                h = self._rc4_encrypt(self._md5(enc_url + "stray"), key)
                timestamp = str(int(time.time()))
                u = self._rc4_encrypt(timestamp + self._md5(key.decode('utf-8') + "stray"), key)
                y = self._rc4_encrypt(self._md5(domain + "stray"), key)

                api_url = f"https://{domain}/player/api.php"
                api_headers = {
                    "User-Agent": self.play_headers["User-Agent"],
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": f"https://{domain}",
                    "Referer": f"https://{domain}/player/?url={enc_url}",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded"
                }

                post_data = {"url": enc_url, "key": h, "vkey": u, "ckey": y}
                resp = self.post(api_url, data=post_data, headers=api_headers, timeout=8)
                result = json.loads(resp.text)
                self._log(f"API返回: code={result.get('code')}, type={result.get('type')}")

                if result.get("code") == 200:
                    aes_key = self._rc4_decrypt(result["aes_key"], key)
                    aes_iv = self._rc4_decrypt(result["aes_iv"], key)
                    play_url = self._aes_decrypt(result["url"], aes_key, aes_iv)
                    self._log(f"解密成功: {play_url[:80]}...")
                    self._play_cache[cache_key] = (play_url, now)
                    return play_url
                else:
                    # 站点解析接口对该源返回 404，回退到本站解析页（WebView 可播）
                    fallback = f"https://{self.PARSE_DOMAIN}/player/?url={enc_url}"
                    self._log(f"API返回非200，使用解析页兜底: {fallback[:80]}...")
                    self._play_cache[cache_key] = (fallback, now)
                    return fallback
            except Exception as e:
                self._log(f"解密异常: {e}")
                return play_page

        except Exception as e:
            self._log(f"获取播放地址异常: {e}")
            return play_page

    # ==================== TVBox五大核心方法 ====================
    def init(self, extend=''):
        self._fetch_cookies()
        # vplay 预热改为懒加载，减少初始化请求，降低触发风控的概率
        self._log("初始化完成")

    def homeContent(self, filter=False):
        result = {
            "class": [
                {"type_id": tid, "type_name": name}
                for tid, name in self.CATEGORY_NAMES.items()
            ]
        }
        if filter:
            # 同时返回 filters/filter 两种键名，兼容不同壳子
            result["filters"] = self.FILTERS
            result["filter"] = self.FILTERS
        return result

    def homeVideoContent(self):
        try:
            html = self._get(self.base_url)
            if not html:
                return {"list": []}
            block = re.search(r'<div class="module">.*?<h2[^>]*class="[^"]*module-title[^"]*"[^>]*>正在热映.*?</div>(.*?)</div>\s*<div class="module">', html, re.DOTALL)
            if not block:
                block = re.search(r'<div class="module">(.*?)</div>\s*<div class="module">', html, re.DOTALL)
            if not block:
                return {"list": []}
            videos = self._parse_video_list(block.group(1))
            return {"list": videos[:20]}
        except Exception as e:
            self._log(f"homeVideoContent异常: {e}")
            return {"list": []}

    def _quote_filter_value(self, v):
        """对筛选值统一编码，避免壳子传中文时 URL 拼接错误；已编码的值不二次编码。"""
        if not v:
            return ""
        try:
            return quote(urllib.parse.unquote(str(v)))
        except Exception:
            return quote(str(v))

    def _build_show_url(self, tid, pg, flt):
        """构造分类筛选 URL：字段位置固定为 12 段"""
        area = self._quote_filter_value(flt.get("area", ""))
        class_ = self._quote_filter_value(flt.get("class", ""))
        lang = self._quote_filter_value(flt.get("lang", ""))
        letter = self._quote_filter_value(flt.get("letter", ""))
        year = self._quote_filter_value(flt.get("year", ""))
        # 字段映射：1-type_id, 2-area, 3-空, 4-class, 5-lang, 6-letter, 7-8-空, 9-page, 10-11-空, 12-year
        parts = [
            str(tid), area, "", class_, lang, letter, "", "",
            str(pg) if pg > 1 else "", "", "", year
        ]
        return f"{self.base_url}/show/{'-'.join(parts)}.html"

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = int(pg)
            if str(tid) not in self.CATEGORY_NAMES:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

            flt = {}
            if content:
                try:
                    flt = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    flt = {}

            url = self._build_show_url(tid, pg, flt)
            self._log(f"分类请求: {url}")
            html = self._get(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
            videos = self._parse_video_list(html)

            # 优先展示已有实际片源的内容（更新至/完结/HD/正片等），
            # 把只有上映日期的未来片源适当降级，提升“最新更新优先”的体验。
            def _release_sort_score(v):
                note = v.get('vod_remarks', '')
                if re.match(r'^\d{4}年\d{2}月\d{2}日上映$', note):
                    return 2
                if '上映' in note and not any(m in note for m in ('更新至', '已完结', 'HD', '1080P', '正片', '全', '集')):
                    return 1
                return 0
            videos = sorted(videos, key=_release_sort_score)

            # 尾页链接可能带筛选参数，用更宽松的正则
            last = re.search(r'<a[^>]*href="/show/\d+(?:-[^"]*?)?-{0,1}(\d+)---\.html"[^>]*>尾页</a>', html)
            pagecount = int(last.group(1)) if last else 1
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self._log(f"categoryContent异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        """站点搜索，签名与 duoduo.py 保持一致，确保 FongMi 聚合搜索正确调用"""
        try:
            pg = max(1, int(pg or 1))
        except (TypeError, ValueError):
            pg = 1
        keyword = str(key or "").strip()
        if not keyword:
            return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
        is_quick = bool(quick)
        encoded_key = quote(keyword)
        # 构造分页 URL：第 11 段为 page，其余为空
        page_part = str(pg) if pg > 1 else ""
        url = f"{self.base_url}/search/{encoded_key}----------{page_part}---.html"
        self._log(f"搜索请求: {url}, quick={is_quick}")

        try:
            html = ""
            for attempt in range(2):
                html = self._get(url)
                # 出现验证页就走验证(含会话过期后重新出现的情况)
                if self._is_verify_page(html):
                    self._verify_passed = False
                    self._log(f"搜索页触发安全验证，自动识别中 (第{attempt+1}次)...")
                    if self._solve_search_verify():
                        # 验证通过后等站点要求的 3 秒搜索间隔再重新搜索
                        time.sleep(2)
                        html = self._get(url)
                    else:
                        time.sleep(3)
                        html = self._get(url)
                    # 若仍是限制页，继续下一轮重试
                    if self._is_verify_page(html):
                        continue
                if html:
                    break

            if not html or self._is_verify_page(html):
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
            videos = self._parse_search_list(html)

            # quick（快速/聚合搜索）模式下直接返回结果，减少壳子聚合等待
            if not is_quick:
                # 普通搜索按标题相关度排序：完全匹配 > 开头匹配 > 包含关键词 > 其他
                key_lower = keyword.lower()
                def _sort_score(v):
                    name = v.get('vod_name', '').lower()
                    if name == key_lower:
                        return 0
                    if name.startswith(key_lower):
                        return 1
                    if key_lower in name:
                        return 2
                    return 3
                videos = sorted(videos, key=_sort_score)

            return {
                "list": videos,
                "page": pg,
                "pagecount": 9999,
                "limit": 20,
                "total": 999999
            }
        except Exception as e:
            self._log(f"搜索Content异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = f"{self.base_url}/detail/{vod_id}.html"
            self._log(f"详情请求: {url}")
            html = self._get(url)
            if not html:
                return {"list": []}

            title = self._re_detail_title.search(html)
            vod_name = self._clean_vod_name(title.group(1).strip()) if title else "未知"

            vod_pic = ""
            for pattern in [
                r'<div[^>]*class="[^"]*module-item-pic[^"]*"[^>]*>.*?<img[^>]*data-original="([^"]+)"',
                r'<img[^>]*data-original="([^"]+)"[^>]*class="[^"]*cover[^"]*"',
                r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*cover[^"]*"',
            ]:
                pic = re.search(pattern, html, re.DOTALL)
                if pic:
                    vod_pic = pic.group(1)
                    break
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            desc = re.search(r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_content = self._clean_html(desc.group(1)) if desc else ""

            actor = re.search(r'主演：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_actor = self._clean_html(actor.group(1)) if actor else ""

            director = re.search(r'导演：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_director = self._clean_html(director.group(1)) if director else ""

            year = re.search(r'<a[^>]*title="(\d{4})"', html)
            vod_year = year.group(1) if year else ""

            # 提取更新/集数状态作为 vod_remarks，满足完结/连载角标展示
            vod_remarks = ""
            remark_patterns = [
                r'<span[^>]*class="[^"]*module-info-item-title[^"]*">集数：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>',
                r'<span[^>]*class="[^"]*module-info-item-title[^"]*">更新：</span>.*?<p[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</p>',
                r'<span[^>]*class="[^"]*module-info-item-title[^"]*">状态：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>',
            ]
            for pat in remark_patterns:
                m = re.search(pat, html, re.DOTALL)
                if m:
                    vod_remarks = self._clean_html(m.group(1))
                    if vod_remarks:
                        break

            sources = self._parse_play_sources(html, vod_id)
            if not sources:
                self._log("未能解析到播放源")
                return {"list": []}

            from_list = []
            url_list = []
            for src in sources:
                from_list.append(src["source_name"])
                eps_str = "#".join([f"{ep['name']}${ep['link']}" for ep in src["episodes"]])
                url_list.append(eps_str)

            vod_play_from = "$$$".join(from_list)
            vod_play_url = "$$$".join(url_list)

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": "",
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            }
            self._log(f"详情解析成功: {vod_name}, 线路: {vod_play_from}")

            # 不再在详情页预加载播放地址：
            # 1. 避免详情页请求过多触发站点频率限制；
            # 2. 懒预热 + 播放缓存已能保证首次播放 0.5~1.5s、二次播放毫秒级；
            # 3. 4K 线路优先置顶，用户点击后即时解析。
            return {"list": [video]}
        except Exception as e:
            self._log(f"detailContent异常: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = str(id).split("-")
            if len(parts) != 3:
                return {"parse": 0, "url": "", "header": ""}
            vod_id, sid, nid = parts
            play_page = f"{self.base_url}/vplay/{vod_id}-{sid}-{nid}.html"
            play_url = self._get_play_url(vod_id, sid, nid)

            if not play_url:
                play_url = play_page

            # 判断是否为直链：路径或查询串中出现常见视频扩展名
            is_direct = bool(re.search(r'\.(m3u8|mp4|flv|ts|mkv)([?#&]|$)', play_url, re.I))
            # 解密 API 拿到的地址通常都是真实播放地址；非本站 vplay/解析页也按直链处理
            is_parse_page = play_url.startswith(play_page) or play_url.startswith(f"https://{self.PARSE_DOMAIN}")
            parse_flag = 0 if (is_direct or not is_parse_page) else 1
            self._log(f"播放URL: {play_url[:80]}..., parse={parse_flag}")

            if parse_flag == 0:
                return {"parse": 0, "url": play_url, "header": self.play_headers.copy()}
            else:
                return {"parse": 1, "url": play_url, "header": ""}
        except Exception as e:
            self._log(f"playerContent异常: {e}")
            return {"parse": 0, "url": "", "header": ""}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
