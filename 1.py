from flask import Flask, render_template, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import re

app = Flask(__name__)
app.secret_key = 'c211995c6399997888d379fb2eb88faa'  # replace with your secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class VideoLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(255), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET'])
def home():
    video_links = VideoLink.query.all()
    return render_template('index.html', video_links=video_links)

@app.route('/add_video', methods=['POST'])
def add_video():
    raw_link = request.form.get('video_link')
    match = re.match(r'https://live\.bilibili\.com/(\d+)', raw_link)
    if match:
        cid = match.group(1)
        iframe_link = f'<div class="video-wrapper"><iframe src="https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={cid}&autoplay=0" frameborder="no" framespacing="0" scrolling="no" allow="autoplay; encrypted-media" allowfullscreen="true"></iframe></div>'
        video_link = VideoLink(link=iframe_link)
    else:
        video_link = VideoLink(link=raw_link)
    db.session.add(video_link)
    db.session.commit()
    return jsonify(id=video_link.id, link=video_link.link)

@app.route('/delete_video', methods=['POST'])
def delete_video():
    video_id = request.form.get('video_id')
    video_link = VideoLink.query.get(video_id)
    if video_link:
        db.session.delete(video_link)
        db.session.commit()
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True, port=5002)
