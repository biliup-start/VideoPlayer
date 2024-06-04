# 使用到DanmakuRender数据库中的api复制来的基本没改，懒能动就行。
# 哔哩哔哩cookie文件请保存在biliup/cookies.json，否则不知道是否会出错没测试。
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import session
from flask_socketio import SocketIO, emit
import re
import requests
import time
import logging
from api.douyu import douyu
from api.huya import huya
from api.twitch import twitch
from api.douyin import douyin
from api.cc import cc
from api.bilibili import bilibili

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logfile = './log.txt'
fh = logging.FileHandler(logfile, mode='a')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

app = Flask(__name__)
app.debug = True
app.secret_key = 'IruDahIYD9cSq39gHwXTSv2BfMQiRvVsgO7LXRDBpKCjysk' # 输入你的密钥或者改成环境变量
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

class VideoLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raw_link = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    attempts = db.Column(db.Integer, default=0)
    format = db.Column(db.String(10), nullable=True)
    error_state = db.Column(db.String(255), nullable=True)

class IframeLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def extract_unique_id(raw_link):
    patterns = {
        'douyu': r'https://www\.douyu\.com/(?:.*rid=|)(\d+)',
        'huya': r'https://www\.huya\.com/(\w+)',
        'twitch': r'https://www\.twitch\.tv/(\w+)',
        'douyin': r'https://live\.douyin\.com/(\w+)',
        'cc': r'https://cc.163.com/(\w+)',
        'bilibili': r'https://live\.bilibili\.com/[^0-9]*(\d+)'
    }
    for platform, pattern in patterns.items():
        match = re.search(pattern, raw_link)
        if match:
            return platform, match.group(1)
    if raw_link.isdigit():
        return 'bilibili', raw_link
    return None, None

def handle_huya(raw_link):
    match_huya = re.match(r'https://www\.huya\.com/(\w+)', raw_link)
    if match_huya:
        rid = match_huya.group(1)
        api = huya(rid)
        return api.get_stream_url()
    return None

def handle_douyu(raw_link):
    match_douyu = re.search(r'https://www\.douyu\.com/(?:.*rid=|)(\d+)', raw_link)
    if match_douyu:
        rid = match_douyu.group(1)
        api = douyu(rid)
        return api.get_stream_url()
    return None

def handle_twitch(raw_link):
    match_twitch = re.match(r'https://www\.twitch\.tv/(\w+)', raw_link)
    if match_twitch:
        rid = match_twitch.group(1)
        api = twitch(rid)
        return api.get_stream_url()
    return None

def handle_douyin(raw_link):
    match_douyin = re.match(r'https://live\.douyin\.com/(\w+)', raw_link)
    if match_douyin:
        rid = match_douyin.group(1)
        api = douyin(rid)
        return api.get_stream_url()
    return None

def handle_cc(raw_link):
    match_cc = re.match(r'https://cc.163.com/(\w+)', raw_link)
    if match_cc:
        rid = match_cc.group(1)
        api = cc(rid)
        return api.get_stream_url()
    return None

def handle_bilibili(raw_link):
    match_bilibili = re.match(r'https://live\.bilibili\.com/[^0-9]*(\d+)', raw_link)
    if match_bilibili:
        rid = match_bilibili.group(1)
        api = bilibili(rid)
        return api.get_stream_url()
    return None

def handle_numeric_bilibili(raw_link):
    if raw_link.isdigit():
        bilibili_link = f'https://live.bilibili.com/{raw_link}'
        return handle_bilibili(bilibili_link)
    return None

def handle_numeric_iframe(raw_link):
    if raw_link.isdigit():
        bilibili_link = f'https://live.bilibili.com/{raw_link}'
        return iframe_bilibili(bilibili_link)
    return None

def iframe_huya(raw_link):
    match_huya = re.match(r'https://www\.huya\.com/(\d+)', raw_link)
    if match_huya:
        rid = match_huya.group(1)
        return f'<iframe width="100%" height="100%" frameborder="0" scrolling="no" src="https://liveshare.huya.com/iframe/{rid}"></iframe>'
    return None

def iframe_bilibili(raw_link):
    match_bilibili = re.match(r'https://live\.bilibili\.com/(\d+)', raw_link)
    if match_bilibili:
        cid = match_bilibili.group(1)
        return f'<div class="video-wrapper"><iframe src="https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={cid}&autoplay=0&mute=1" frameborder="no" framespacing="0" scrolling="no" allow="autoplay; encrypted-media" allowfullscreen="true"></iframe></div>'
    return None

def handle_hls_flv_ts(raw_link):
    if any(ext in raw_link for ext in ['.flv', '.m3u8', '.ts']):
        return raw_link
    return None

@app.route('/', methods=['GET'])
def home():
    video_links = VideoLink.query.all()
    iframe_links = IframeLink.query.all()
    return render_template('index.html', video_links=video_links)

@app.route('/iframe.html', methods=['GET'])
def iframe():
    iframe_links = IframeLink.query.all()
    return render_template('iframe.html', iframe_links=iframe_links)

@app.route('/<path:path>', methods=['GET'])
def catch_all(path):
    return redirect(url_for('home'), code=302)

@app.route('/add_video', methods=['POST'])
def add_video():
    raw_link = request.form.get('video_link')

    existing_failed_link = VideoLink.query.filter_by(raw_link=raw_link, error_state="请求超时").first()
    if existing_failed_link:
        return jsonify(error="当前地区无法观看"), 403

    try:
        platform, unique_id = extract_unique_id(raw_link)
        if not unique_id:
            return jsonify(error="无效的链接"), 400
        existing_link = VideoLink.query.filter_by(raw_link=raw_link).first()
        if existing_link:
            return jsonify(error="提示：相同链接一个小时只能输入一次"), 400
        for link in VideoLink.query.all():
            link_platform, link_id = extract_unique_id(link.raw_link)
            if platform == link_platform and unique_id == link_id:
                return jsonify(error="提示：该房间号已存在"), 400
        stream_url = (
            handle_huya(raw_link) or
            handle_douyu(raw_link) or
            handle_twitch(raw_link) or
            handle_douyin(raw_link) or
            handle_cc(raw_link) or
            handle_bilibili(raw_link) or
            handle_numeric_bilibili(raw_link) or
            handle_hls_flv_ts(raw_link) or
            None
        )
        if stream_url:
            video_link = VideoLink(
                raw_link=raw_link,
                link=stream_url,
                timestamp=datetime.utcnow(),
                last_checked=datetime.utcnow(),
                format='hls' if stream_url.endswith('.m3u8') else 'flv' if stream_url.endswith('.flv') else 'ts' if stream_url.endswith('.ts') else None
            )
            db.session.add(video_link)
            db.session.commit()
            return jsonify(id=video_link.id, raw_link=video_link.raw_link, link=video_link.link)
        else:
            return jsonify(error="无效的链接或流"), 400
    except requests.exceptions.ConnectTimeout as e:
        video_link = VideoLink(
            raw_link=raw_link,
            link="",
            timestamp=datetime.utcnow(),
            last_checked=datetime.utcnow(),
            error_state="请求超时"
        )
        db.session.add(video_link)
        db.session.commit()
        return jsonify(error="当前地区无法观看"), 403
    except requests.exceptions.RequestException as e:
        logger.error(f"请求视频流时出错：{e}")
        return jsonify(error="请求视频流时出错，请稍后再试"), 500
    except Exception as e:
        logger.error(f"添加视频时出错：{e}")
        return jsonify(error="未开播或无法获取流"), 500

@app.route('/add_video_iframe', methods=['POST'])
def add_video_iframe():
    raw_link = request.form.get('iframe_link')

    existing_failed_link = VideoLink.query.filter_by(raw_link=raw_link, error_state="请求超时").first()
    if existing_failed_link:
        return jsonify(error="当前地区无法观看"), 403

    try:
        platform, unique_id = extract_unique_id(raw_link)
        if not unique_id:
            return jsonify(error="无效的链接"), 400
        stream_url = (
            iframe_huya(raw_link) or
            iframe_bilibili(raw_link) or
            handle_numeric_iframe(raw_link) or
            None
        )
        if stream_url:
            existing_link = IframeLink.query.filter_by(link=stream_url).first()
            if existing_link:
                return jsonify(error="提示：相同链接一个小时只能输入一次"), 400
            for link in IframeLink.query.all():
                link_platform, link_id = extract_unique_id(link.link)
                if platform == link_platform and unique_id == link_id:
                    return jsonify(error="提示：该房间号已存在"), 400
            iframe_link = IframeLink(link=stream_url)
            db.session.add(iframe_link)
            db.session.commit()
            return jsonify(id=iframe_link.id, link=iframe_link.link)
        else:
            return jsonify(error="无效的链接或流"), 400
    except requests.exceptions.ConnectTimeout as e:
        video_link = VideoLink(
            raw_link=raw_link,
            link="",
            timestamp=datetime.utcnow(),
            last_checked=datetime.utcnow(),
            error_state="请求超时"
        )
        db.session.add(video_link)
        db.session.commit()
        return jsonify(error="当前地区无法观看"), 403
    except requests.exceptions.RequestException as e:
        logger.error(f"请求 iframe 视频流时出错：{e}")
        return jsonify(error="请求 iframe 视频流时出错，请稍后再试"), 500
    except Exception as e:
        logger.error(f"添加 iframe 视频时出错：{e}")
        return jsonify(error="未开播或无法获取流"), 500

@app.route('/delete_video_iframe', methods=['POST'])
def delete_video_iframe():
    iframe_id = request.form.get('iframe_id')
    secret_key = request.form.get('secret_key')

    if secret_key != app.secret_key:
        return jsonify(error="无效的密钥"), 403

    if iframe_id is not None:
        iframe_link = db.session.get(IframeLink, iframe_id)
        if iframe_link:
            db.session.delete(iframe_link)
            db.session.commit()
            return jsonify(success=True)
        else:
            return jsonify(error="未找到 iframe 视频"), 404
    else:
        return jsonify(error="iframe_id 为空"), 400

@app.route('/delete_video', methods=['POST'])
def delete_video():
    video_id = request.form.get('video_id')
    secret_key = request.form.get('secret_key')

    if secret_key != app.secret_key:
        logger.warning("无效的密钥尝试。")
        return jsonify(error="无效的密钥"), 403

    try:
        video = VideoLink.query.get(video_id)
        if video:
            db.session.delete(video)
            db.session.commit()
            logger.info(f"视频 {video_id} 成功删除。")
            return jsonify(success=True)
        else:
            logger.error(f"视频 {video_id} 未找到。")
            return jsonify(error="视频未找到"), 404
    except Exception as e:
        logger.error(f"删除视频时出错：{e}")
        return jsonify(error="服务器内部错误"), 500

@app.route('/delete_all_videos', methods=['POST'])
def delete_all_videos():
    secret_key = request.form.get('secret_key')

    if secret_key != app.secret_key:
        logger.warning("无效的密钥尝试。")
        return jsonify(error="无效的密钥"), 403

    try:
        VideoLink.query.delete()
        IframeLink.query.delete()
        db.session.commit()
        logger.info("旧视频已删除。")
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"删除所有视频时出错：{e}")
        return jsonify(error="服务器内部错误"), 500

@app.route('/get_video_links', methods=['GET'])
def get_video_links():
    video_links = VideoLink.query.all()
    return jsonify([{'id': video_link.id, 'raw_link': video_link.raw_link, 'link': video_link.link} for video_link in video_links])

def make_request_with_retries(url, max_retries=5, timeout=5):
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.head(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise
            attempt += 1
            logger.warning(f"Attempt {attempt} failed for {url}, retrying...")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            attempt += 1
            logger.warning(f"Attempt {attempt} failed for {url}, retrying...")
            time.sleep(2 ** attempt)
    raise Exception("Max retries reached")

def delete_old_videos():
    while True:
        with app.app_context():
            cutoff = datetime.utcnow() - timedelta(hours=48)
            old_videos = VideoLink.query.filter(VideoLink.timestamp < cutoff).all()
            for video in old_videos:
                db.session.delete(video)
                logger.info(f"视频在过去48小时内没有被推送，已被删除： {video.id}")
            db.session.commit()
        time.sleep(60 * 60)

socketio.start_background_task(delete_old_videos)

def check_video_streams():
    max_attempts = 60
    while True:
        with app.app_context():
            video_links = VideoLink.query.all()
            for video in video_links:
                try:
                    response = make_request_with_retries(video.link)
                    if response.status_code < 200 or response.status_code >= 400:
                        logger.warning(f"检测到无效的流，正在重新获取：{video.link}")
                        new_stream_url = (
                            handle_huya(video.raw_link) or
                            handle_douyu(video.raw_link) or
                            handle_twitch(video.raw_link) or
                            handle_douyin(video.raw_link) or
                            handle_cc(video.raw_link) or
                            handle_bilibili(video.raw_link) or
                            handle_numeric_bilibili(video.raw_link) or
                            None
                        )
                        if new_stream_url:
                            video.link = new_stream_url
                            video.last_checked = datetime.utcnow()
                            video.attempts = 0
                            db.session.commit()
                            socketio.emit('update_stream', {'id': video.id, 'link': new_stream_url})
                            socketio.emit('notify_user', {'message': f"流 {video.id} 已刷新。"})
                        else:
                            video.attempts += 1
                            db.session.commit()
                            socketio.emit('notify_user', {'message': f"尝试 {video.attempts} 刷新流 {video.id} 失败。"})
                            if video.attempts >= max_attempts:
                                db.session.delete(video)
                                logger.info(f"失效视频流一个小时内多次重试还是失效已删除： {video.id}")
                                socketio.emit('notify_user', {'message': f"无效流 {video.id} 在多次重试后被删除。"})
                                db.session.commit()
                    else:
                        video.last_checked = datetime.utcnow()
                        video.attempts = 0
                        db.session.commit()
                except requests.exceptions.RequestException as e:
                    logger.error(f"检查视频流时出错：{e}")
        time.sleep(60)

socketio.start_background_task(check_video_streams)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, allow_unsafe_werkzeug=True)
