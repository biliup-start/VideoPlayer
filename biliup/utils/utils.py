import random
import subprocess
import json
import time
import re
import os
import glob

from easydict import EasyDict as edict
from os.path import exists, abspath, splitext
from uuid import uuid1
from datetime import datetime


__all__ = [
    'rename_safe',
    'isvideo',
    'concat_rid',
    'split_url',
    'replace_keywords',
    'replace_invalid_chars',
    'sec2hms',
    'hms2sec',
    'BGR2RGB',
    'RGB2BGR',
    'uuid',
    'get_platform',
    'safe_filename',
    'cookiestr2dict',
    'random_user_agent',
    'retry_safe',
]


def random_user_agent() -> str:
    version = random.randint(100, 120)
    return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36 Edg/{version}.0.0.0'

def cookiestr2dict(cookie_str:str):
    cookies_dict = {}
    for cookie in cookie_str.split('; '):
        key, value = cookie.split('=', 1)
        cookies_dict[key] = value
    return cookies_dict

def get_platform(url:str) -> str:
    if 'bilibili.com' in url:
        return 'bilibili'
    elif 'youtube.com' in url:
        return 'youtube'
    
def retry_safe(func, max_retries=5, sleep_interval=1):
    if max_retries <= 0:
        max_retries = 2**32-1
    for idx in range(max_retries):
        ret = func()
        if ret:
            return ret
        else:
            time.sleep(sleep_interval)
    return None

def rename_safe(src:str, dst:str, retry:int=10):
    dst:str = dst
    retry = max(1, int(retry))
    retry_cnt = 0
    if not exists(src):
        return False

    if exists(dst):
        cnt = len(glob.glob(splitext(dst)[0] + '*'))
        dst = splitext(dst)[0] + f'({cnt})' + splitext(dst)[1]
    
    while retry_cnt < retry:
        try:
            os.rename(src, dst)
            return dst
        except Exception as e:
            retry_cnt += 1
            if retry_cnt >= retry:
                return False
        time.sleep(0.1)

    return False

def safe_filename(filename:str) -> str:
    if not exists(filename):
        return filename

    if exists(filename):
        cnt = len(glob.glob(splitext(filename)[0] + '*'))
        filename = splitext(filename)[0] + f'({cnt})' + splitext(filename)[1]
    return filename

def isvideo(path: str) -> bool:
    ext = path.split('.')[-1]
    if ext in ['mp4', 'flv', 'ts', 'mkv', 'webm', 'm4v', 'mov', 'avi', 'mpg', 'mpeg','wmv']:
        return True
    else:
        return False

def concat_rid(plat: str, rid: str) -> str:
    if plat in ['bilibili', 'douyin']:
        url = f'https://live.{plat}.com/{str(rid)}'
    elif plat == 'cc':
        url = f'https://cc.163.com/{str(rid)}'
    elif plat == 'twitch':
        url = f'https://www.twitch.tv/{str(rid)}'
    else:
        url = f'https://www.{plat}.com/{str(rid)}'
    return url

def split_url(url: str):
    domain = re.search(r'(?:https?:\/\/)?(?:[^@\/\n]+@)?(?:www\.)?([^:\/?\n]+)', url).group(1)
    platform = domain.split('.')[-2]
    rid = re.search(r'(?:https?:\/\/)?(?:[^@\/\n]+@)?(?:www\.)?[^:\/?\n]+\/([^\/\?\n]+)', url).group(1)

    if platform == 'douyu':
        try:
            int(rid)
        except:
            if 'rid=' in url:
                rid = re.findall(r'rid=[0-9]*', url)[0][4:]
    if platform == "163":
        platform = "cc"
    return platform, rid

def replace_keywords(string:str, kw_info:dict=None, replace_invalid:bool=False):
    if not kw_info:
        return string

    class dict_wapper(edict):
        def __getitem__(self, _key):
            res = super().__getitem__(_key)
            if isinstance(res, str) and replace_invalid:
                return replace_invalid_chars(res)
            return res
        def __missing__(self, key:str):
            if key.lower() in self.keys():
                return self[key.lower()]
            return ''

    def to_lower(match):
        return match.group().lower()

    string = re.sub(r'(?<!\{)\{.*?\}(?!\})', to_lower, string)
    if isinstance(kw_info, dict):
        kw_info = dict_wapper(kw_info)

    result = string.format_map(kw_info)
    
    return result

def replace_invalid_chars(string:str) -> str:
    return re.sub(r"[\\/:;.*?\"<>|]", "", str(string))

def sec2hms(sec:float):
    sec = float(sec)
    t_m,t_s = divmod(sec ,60)   
    t_h,t_m = divmod(t_m,60)
    return t_h, t_m, t_s

def hms2sec(hrs:float,mins:float,secs:float):
    return float(hrs)*3600 + float(mins)*60 + float(secs)

def BGR2RGB(color):
    return color[4:6] + color[2:4] + color[0:2]

def RGB2BGR(color):
    return BGR2RGB(color)

def uuid(len:int=None):
    struuid = uuid1().hex
    if len is None: 
        return struuid
    return struuid[:len]