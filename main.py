# 使用到DanmakuRender数据库中的api复制来的基本没改，懒能动就行。
# 哔哩哔哩cookie文件请保存在biliup/cookies.json，否则不知道是否会出错没测试。
# File path: app.py
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session
from flask_socketio import SocketIO, emit
import re
import requests
import time
from api.douyu import douyu
from api.huya import huya
from api.twitch import twitch
from api.douyin import douyin
from api.cc import cc
from api.bilibili import bilibili

# Setup logging
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

# Initialize Flask app
app = Flask(__name__)
app.debug = True
app.secret_key = 'IruDahIYD9cSq39gHwXTSv2BfMQiRvVsgO7LXRDBpKCjysk'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and SocketIO
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

# Define VideoLink model
class VideoLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raw_link = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)

class IframeLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create all tables
with app.app_context():
    db.create_all()

# Define platform handlers
def handle_huya(raw_link):
    match_huya = re.match(r'https://www\.huya\.com/(\w+)', raw_link)
    if match_huya:
        rid = match_huya.group(1)
        api = huya(rid)
        return api.get_stream_url()
    return None

def handle_douyu(raw_link):
    match_douyu = re.search(r'https://www\.douyu\.com/[^0-9]*(\d+)', raw_link)
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

@app.route('/', methods=['GET'])
def home():
    video_links = VideoLink.query.all()
    iframe_links = IframeLink.query.all()
    return render_template('index.html', video_links=video_links)

@app.route('/iframe.html', methods=['GET'])
def iframe():
    iframe_links = IframeLink.query.all()
    return render_template('iframe.html', iframe_links=iframe_links)

@app.route('/add_video', methods=['POST'])
def add_video():
    raw_link = request.form.get('video_link')
    stream_url = (
        handle_huya(raw_link) or 
        handle_douyu(raw_link) or 
        handle_twitch(raw_link) or 
        handle_douyin(raw_link) or 
        handle_cc(raw_link) or 
        handle_bilibili(raw_link) or 
        handle_numeric_bilibili(raw_link) or  
        None
    )
    if stream_url:
        existing_link = VideoLink.query.filter_by(raw_link=raw_link).first()
        if existing_link:
            return jsonify(error="提示：相同链接一个小时只能输入一次"), 400

        video_link = VideoLink(raw_link=raw_link, link=stream_url, timestamp=datetime.utcnow(), last_checked=datetime.utcnow())
        db.session.add(video_link)
        db.session.commit()
        return jsonify(id=video_link.id, raw_link=video_link.raw_link, link=video_link.link)
    else:
        return jsonify(error="无效的链接"), 400

@app.route('/add_video_iframe', methods=['POST'])
def add_video_iframe():
    raw_link = request.form.get('iframe_link')
    stream_url = (
        iframe_huya(raw_link) or 
        iframe_bilibili(raw_link) or 
        handle_numeric_iframe(raw_link) or 
        None
    )
    if stream_url:
        iframe_link = IframeLink(link=stream_url)
        db.session.add(iframe_link)
        db.session.commit()
        return jsonify(id=iframe_link.id, link=iframe_link.link)
    else:
        return jsonify(error="无法获取 iframe 链接"), 400

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

    video = VideoLink.query.get(video_id)
    if video:
        db.session.delete(video)
        db.session.commit()
        logger.info(f"视频 {video_id} 成功删除。")
        return jsonify(success=True)
    else:
        logger.error(f"视频 {video_id} 未找到.")
        return jsonify(error="视频未找到"), 404

@app.route('/delete_all_videos', methods=['POST'])
def delete_all_videos():
    secret_key = request.form.get('secret_key')
    
    if secret_key != app.secret_key:
        logger.warning("无效的密钥尝试。")
        return jsonify(error="无效的密钥"), 403

    VideoLink.query.delete()
    IframeLink.query.delete()
    db.session.commit()
    logger.info("旧视频已删除。")
    return jsonify(success=True)

@app.route('/get_video_links', methods=['GET'])
def get_video_links():
    video_links = VideoLink.query.all()
    return jsonify([{'id': video_link.id, 'raw_link': video_link.raw_link, 'link': video_link.link} for video_link in video_links])

def delete_old_videos():
    while True:
        with app.app_context():
            cutoff = datetime.utcnow() - timedelta(hours=48)
            old_videos = VideoLink.query.filter(VideoLink.timestamp < cutoff).all()
            for video in old_videos:
                db.session.delete(video)
                logger.info(f"视频在过去48小时内没有被推送，已被删除: {video.id}")
            db.session.commit()
        time.sleep(60*60)

socketio.start_background_task(delete_old_videos)

def check_video_streams():
    max_attempts = 60
    while True:
        with app.app_context():
            video_links = VideoLink.query.all()
            for video in video_links:
                try:
                    response = requests.head(video.link, timeout=5)
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
                            db.session.commit()
                            socketio.emit('update_stream', {'id': video.id, 'link': new_stream_url})
                            socketio.emit('notify_user', {'message': f"Stream {video.id} has been refreshed."})
                        else:
                            video.attempts += 1
                            if video.attempts >= max_attempts:
                                db.session.delete(video)
                                logger.info(f"失效视频流一个小时内多次重试还是失效已删除: {video.id}")
                                socketio.emit('notify_user', {'message': f"Invalid stream {video.id} has been deleted after multiple retries."})
                            db.session.commit()
                    else:
                        video.last_checked = datetime.utcnow()
                        video.attempts = 0
                        db.session.commit()
                except Exception as e:
                    logger.error(f"检查视频流时出错：{e}")
        time.sleep(60)

socketio.start_background_task(check_video_streams)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, allow_unsafe_werkzeug=True)
