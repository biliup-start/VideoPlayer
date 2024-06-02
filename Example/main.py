# 使用到DanmakuRender数据库中的api复制来的基本没改，懒能动就行。
# 哔哩哔哩cookie文件请保存在login_info/bilibili.json，否则不知道是否会出错没测试。
# 导入所需的库
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import re
from api.douyu import douyu
from api.huya import huya
from api.twitch import twitch  
from api.douyin import douyin  
from api.cc import cc  
from api.bilibili import bilibili  

from sqlalchemy.orm import Session

# 初始化Flask应用
app = Flask(__name__)
app.debug = True
app.secret_key = 'c211995c6399997888d379fb2eb88faa'  # 请替换为你的密钥
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)
migrate = Migrate(app, db)

session = Session()

# 定义VideoLink模型
class VideoLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raw_link = db.Column(db.String(255), nullable=False)  # 新增：原始链接
    link = db.Column(db.String(255), nullable=False)  # 处理后的流链接
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # 添加时间戳字段

class iframeLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # 添加时间戳字段

# 创建所有数据库表
with app.app_context():
    db.create_all()

# 定义处理各个平台的函数
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

# 检查输入是否只包含数字
def handle_numeric_bilibili(raw_link):
    if raw_link.isdigit():
        bilibili_link = f'https://live.bilibili.com/{raw_link}'
        stream_url = handle_bilibili(bilibili_link)
        return stream_url
    else:
        return None

def handle_numeric_iframe(raw_link):
    if raw_link.isdigit():
        bilibili_link = f'https://live.bilibili.com/{raw_link}'
        iframe_url = iframe_bilibili(bilibili_link)
        return iframe_url
    else:
        return None

# 定义处理iframe直播链接的函数
def iframe_huya(raw_link):
    match_huya = re.match(r'https://www\.huya\.com/(\d+)', raw_link)
    if match_huya:
        rid = match_huya.group(1)
        return f'<iframe width="100%" height="100%"  frameborder="0" scrolling="no" src="https://liveshare.huya.com/iframe/{rid}"></iframe>'
    return None

def iframe_bilibili(raw_link):
    match_bilibili = re.match(r'https://live\.bilibili\.com/(\d+)', raw_link)
    if match_bilibili:  
        cid = match_bilibili.group(1)
        iframe_link = f'<div class="video-wrapper"><iframe src="https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={cid}&autoplay=0&mute=1" frameborder="no" framespacing="0" scrolling="no" allow="autoplay; encrypted-media" allowfullscreen="true"></iframe></div>'
        return iframe_link
    return None

# 定义路由和视图函数
@app.route('/', methods=['GET'])
def home():
    video_links = VideoLink.query.all()
    iframe_links = iframeLink.query.all()
    return render_template('index.html', video_links=video_links)

@app.route('/iframe.html', methods=['GET'])
def iframe():
    iframe_links = iframeLink.query.all() 
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
        raw_link  
    )
    if stream_url:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        existing_link = VideoLink.query.filter_by(raw_link=raw_link).filter(VideoLink.timestamp >= one_hour_ago).first()
        if existing_link:
            return jsonify(error="提示：相同链接一个小时只能输入一次"), 400

        video_link = VideoLink(raw_link=raw_link, link=stream_url, timestamp=datetime.utcnow())
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
        raw_link  
    )
    if stream_url:
        iframe_link = iframeLink(link=stream_url)
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
        iframe_link = db.session.get(iframeLink, iframe_id)
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
    video_id = request.form['video_id']
    secret_key = request.form['secret_key']
    
    if secret_key != app.secret_key:
        return jsonify(error="无效的密钥"), 403

    video = VideoLink.query.get(video_id)
    if video:
        db.session.delete(video)
        db.session.commit()
        return jsonify(success=True)
    else:
        return jsonify(error="视频未找到"), 404

@app.route('/delete_all_videos', methods=['POST'])
def delete_all_videos():
    secret_key = request.form['secret_key']
    
    if secret_key != app.secret_key:
        return jsonify(error="无效的密钥"), 403

    VideoLink.query.delete()
    iframeLink.query.delete()  
    db.session.commit()
    return jsonify(success=True)

@app.route('/get_video_links', methods=['GET'])
def get_video_links():
    video_links = VideoLink.query.all()
    return jsonify([{'id': video_link.id, 'raw_link': video_link.raw_link, 'link': video_link.link} for video_link in video_links])

def delete_old_videos():
    while True:
        with app.app_context():
            cutoff = datetime.utcnow() - timedelta(days=1)
            old_videos = VideoLink.query.filter(VideoLink.timestamp < cutoff).all()
            for video in old_videos:
                db.session.delete(video)
            db.session.commit()
        time.sleep(86400)  # 每24小时运行一次

# 启动Flask应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5002)
