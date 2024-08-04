import html
import random

try:
    from .BaseAPI import BaseAPI
except ImportError:
    from BaseAPI import BaseAPI
import requests
import re
import base64
from lxml import etree
import urllib.parse
import hashlib
import time
import logging


class huya(BaseAPI):
    header = {
        'Content-Type': 'application/x-www-form-urlencoded',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36 Edg/88.0.705.68",
    }
    header_mobile = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/75.0.3770.100 Mobile Safari/537.36 '
    }

    def __init__(self, rid: str) -> None:
        self.rid = rid
        self.sess = requests.Session()
        if not self.rid.isdigit():
            try:
                response = self._get_response()
                selector = etree.HTML(response)
                self.rid = selector.xpath('//*[@class="host-rid"]/em')[0].text
            except:
                pass
        
    def __del__(self):
        self.sess.close()

    def _get_response(self, mobile=False):
        if not mobile:
            room_url = 'https://www.huya.com/' + self.rid
            response = self.sess.get(url=room_url, headers=self.header, timeout=5).text
        else:
            room_url = 'https://m.huya.com/' + self.rid
            response = self.sess.get(url=room_url, headers=self.header_mobile, timeout=5).text
        return response

    def _get_api_response(self):
        room_url = 'https://mp.huya.com/cache.php?m=Live&do=profileRoom&roomid=' + str(self.rid)
        data = self.sess.get(url=room_url, headers=self.header_mobile, timeout=5).json()
        return data

    def is_available(self) -> bool:
        try:
            response = self._get_response(mobile=True)
            liveLineUrl = re.findall(r'"liveLineUrl":"([\s\S]*?)",', response)[0]
            liveline = base64.b64decode(liveLineUrl).decode('utf-8')
            return True
        except:
            return False

    def onair(self) -> bool:
        try:
            data = self._get_api_response()
            status = data['data']['realLiveStatus']
            if status == 'ON':
                return True
            elif status == 'OFF':
                return False
            else:
                response = self._get_response(mobile=True)
                liveLineUrl = re.findall(r'"liveLineUrl":"([\s\S]*?)",', response)[0]
                liveline = base64.b64decode(liveLineUrl).decode('utf-8', errors='ignore')
                if liveline and 'replay' not in liveline:
                    return True
                else:
                    return False
        except Exception as e:
            logging.debug(e)
            return None

    def get_info(self):
        """
        return: title,uname,face_url,keyframe_url
        """
        response = self._get_api_response()
        data = response['data']['liveData']
        try:
            title = data['introduction']
        except:
            title = 'huya' + self.rid
        try:
            uname = data['nick']
        except:
            uname = 'huya' + self.rid
        try:
            face_url = data['avatar180']
        except:
            face_url = None
        try:
            keyframe_url = data['screenshot']
        except:
            keyframe_url = None
        return title, uname, face_url, keyframe_url

    def _parse_anti_code(self, anticode, streamName):
        qr = urllib.parse.parse_qs(anticode)

        qr['ver'] = ['1']
        qr['sv'] = ['2110211124']
        qr['seqid'] = [str(int(time.time()) * 1000 + 0)]
        ss = hashlib.md5(f"{qr.get('seqid', [])[0]}|{qr['ctype'][0]}|{qr.get('t', [''])[0]}".encode()).hexdigest()

        fm = base64.b64decode(qr['fm'][0]).decode()
        fm = fm.replace("$0", '0')
        fm = fm.replace("$1", streamName)
        fm = fm.replace("$2", ss)
        fm = fm.replace("$3", qr['wsTime'][0])
        qr.pop('fm')
        qr['wsSecret'] = [hashlib.md5(fm.encode()).hexdigest()]
        return urllib.parse.urlencode(qr, doseq=True)

    def get_stream_urls(self, **kwargs) -> str:
        data = self._get_api_response()

        urls = []
        baseSteamInfoList = data['data']['stream']['baseSteamInfoList']
        for streamInfo in baseSteamInfoList:
            url_query = urllib.parse.parse_qs(streamInfo["sFlvAntiCode"])
            uid = random.randint(1400000000000, 1499999999999)
            ws_time = hex(int(time.time() + 21600))[2:]
            seq_id = round(time.time() * 1000) + uid
            ws_secret_prefix = base64.b64decode(urllib.parse.unquote(url_query['fm'][0]).encode()).decode().split("_")[0]
            ws_secret_hash = hashlib.md5(
                f'{seq_id}|{url_query["ctype"][0]}|{url_query["t"][0]}'.encode()).hexdigest()
            ws_secret = hashlib.md5(
                f'{ws_secret_prefix}_{uid}_{streamInfo["sStreamName"]}_{ws_secret_hash}_{ws_time}'.encode()).hexdigest()
            
            url = f'{streamInfo["sFlvUrl"]}/{streamInfo["sStreamName"]}.{streamInfo["sFlvUrlSuffix"]}?wsSecret={ws_secret}&wsTime={ws_time}&seqid={seq_id}&ctype={url_query["ctype"][0]}&ver=1&fs={url_query["fs"][0]}&t={url_query["t"][0]}&uid={uid}&ratio=0'
            urls.append({
                'stream_cdn': streamInfo['sCdnType'].lower(),
                'stream_type': 'flv',
                'stream_url': url
            })
        return urls
    
    def get_stream_url(self, stream_cdn=None, stream_type=None, **kwargs) -> str:
        stream_type = stream_type or 'flv'

        avail_urls = self.get_stream_urls()
        selected_urls = []
        for url_info in avail_urls:
            if stream_cdn and url_info['stream_cdn'] != stream_cdn:
                continue
            if stream_type and url_info['stream_type'] != stream_type:
                continue
            uri = url_info['stream_url']
            try:
                if 'direct' not in uri and self.sess.get(url=uri, headers=self.header_mobile, stream=True, timeout=3).status_code == 200:
                    selected_urls.append(uri)
                    break
            except Exception as e:
                pass
        
        if not selected_urls:
            logging.warning(f'虎牙{self.rid}没有满足 {stream_cdn},{stream_type} 的流，将使用默认选项.')
            return random.choice(avail_urls)['stream_url']
        else:
            return random.choice(selected_urls)


if __name__ == '__main__':
    api = huya('132549')
    print(api.get_stream_url())
