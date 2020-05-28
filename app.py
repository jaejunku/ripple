import geocoder
import requests
from datetime import datetime
from flask import Flask, session, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import StringField, SubmitField, TextAreaField, BooleanField

# TODO let users add pictures to posts
# TODO let users (optionally) specify more specific locations when adding post
# TODO add integration for Spotify song preview when hovering over album picture
# TODO frontend design

app = Flask(__name__)
google_api_key = 'AIzaSyC7rX_hVNjF2MH2uQM4StN7tDtkHd0AqAk'
app.config['SECRET_KEY'] = 'b87cd65425cbfb553740894dcc2fd0fe'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)


# Database classes: A collection can have many songs, a song can have many posts
class Collection(db.Model):
    id = db.Column(db.String, primary_key=True)
    lat = db.Column(db.Float)
    address = db.Column(db.String, nullable=False)
    long = db.Column(db.Float)
    songs = db.relationship('Song', backref='collection', lazy=True)
    posts = db.relationship('Post', backref='collection', lazy=True)

    def __repr__(self):
        return f"Collection('{self.id}')"


class Song(db.Model):
    song_uri = db.Column(db.String, primary_key=True)
    song_preview = db.Column(db.String)
    artist = db.Column(db.String, nullable=False)
    song_title = db.Column(db.String, nullable=False)
    album_picture = db.Column(db.String, nullable=False)
    users = db.relationship('Post', backref='song', lazy=True)
    collection_id = db.Column(db.String, db.ForeignKey('collection.id'), nullable=False)

    def __repr__(self):
        return f"Song('{self.song_uri}', '{self.song_title}')"


class Post(db.Model):
    post_id = db.Column(db.Integer, primary_key=True)
    # post_picture = db.Column(db.String)
    post_content = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    song_id = db.Column(db.String, db.ForeignKey('song.song_uri'), nullable=False)
    collection_id = db.Column(db.String, db.ForeignKey('collection.id'), nullable=False)
    author_id = db.Column(db.String, nullable=False)
    author_name = db.Column(db.String, nullable=False)

    def __repr__(self):
        return f"Post('{self.post_id}', '{self.date_posted}')"


# TODO add data required validator
class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField('Search')


class PostForm(FlaskForm):
    is_anonymous = BooleanField('Anonymous')
    content = TextAreaField('Memory')
    submit = SubmitField('Post')


# TODO replace with dummy key

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'access_token' in session:
        user_profile = requests.get('https://api.spotify.com/v1/me',
                                    headers={'Authorization': 'Bearer ' + session['access_token']})
        user_json = user_profile.json()
        session['current_user_name'] = user_json.get("display_name")
        session['current_user_id'] = user_json.get("id")
        # Calculate collections near user
        # Get rough estimate of user's location
        coords = geocoder.ip('me').latlng
        lat = str(coords[0])
        lng = str(coords[1])
        nearby_collections = Collection.query.order_by(
            ((lat - Collection.lat) * (lat - Collection.lat) +
             (lng - Collection.long) * (lng - Collection.long))).limit(5).all()
        # Collection.query.filter(
        #     (func.degrees(
        #         func.acos(
        #             func.sin(func.radians(lat)) * func.sin(func.radians(Collection.lat)) +
        #             func.cos(func.radians(lat)) * func.cos(func.radians(Collection.lat)) *
        #             func.cos(func.radians(lng - Collection.long))
        #         )
        #     ) * 60 * 1.1515 * 1.609344) <= distance)

        return render_template('home.html',
                               display_name=user_json.get("display_name"),
                               nearby_collections=nearby_collections,
                               id=user_json.get("id"),
                               email=user_json.get("email"),
                               images=user_json.get("images"),
                               access_token=session['access_token'],
                               token_type=session['token_type'],
                               refresh_token=session['refresh_token'],
                               login_authorized=True
                               )
    else:
        return render_template('home.html', login_authorized=False)


def check_authorization():
    if 'access_token' in session:
        return True
    else:
        return False


@app.route('/logout', methods=['GET'])
def logout():
    key_list = list(session.keys())
    for key in key_list:
        session.pop(key)
    return redirect(url_for('home'))


@app.route('/authorize', methods=['GET'])
def authorize():
    return redirect(
        'https://accounts.spotify.com/authorize?client_id=2bf4792df3c4489bb9720d3346d63f53&response_type=code'
        '&redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fcallback%2F&scope=user-read-private%20user-read-email%20user'
        '-top-read%20')


@app.route('/callback/', methods=['GET', 'POST'])
def callback():
    # Use code obtained after user authorizes access to exchange it for token
    session['code'] = request.args.get('code')
    error = request.args.get('error')
    if error:
        return redirect(url_for('home'))
    else:
        payload = {
            'grant_type': 'authorization_code',
            'code': session['code'],
            'redirect_uri': 'http://127.0.0.1:5000/callback/',
            'client_id': '2bf4792df3c4489bb9720d3346d63f53',
            'client_secret': 'c615ba249c4249a1a55cf459b606819b'
        }
        token_response = requests.post('https://accounts.spotify.com/api/token', data=payload)
        token_json = token_response.json()
        session['access_token'] = token_json.get("access_token")
        session['token_type'] = token_json.get("token_type")
        session['refresh_token'] = token_json.get("refresh_token")
        return redirect(url_for('home'))


def refresh_access_token():
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token']
    }
    header = 'Authorization: Basic 2bf4792df3c4489bb9720d3346d63f53:c615ba249c4249a1a55cf459b606819b'
    new_token_response = requests.post('https://accounts.spotify.com/api/token', headers=header, data=payload)
    new_token_json = new_token_response.json()
    session['access_token'] = new_token_json.get("access_token")


@app.route('/search', methods=['GET', 'POST'])
def search_location():
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(url_for('search_location_call', input_location=search_form.search.data))
    return render_template('search.html', title='Search Far', form=search_form,
                           login_authorized=check_authorization())


@app.route('/search/<string:input_location>', methods=['GET', 'POST'])
def search_location_call(input_location):
    # Search query is the input from form
    search_request = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?key=' + google_api_key
                                  + '&query=' + input_location.replace(" ", "+"))
    # Now convert the response into Python dictionary
    results = search_request.json()
    # TODO if there is no match, allow search again or route to far-search
    # If results is empty list (no results found), we want to ask again or give option to find somewhere far away
    # Redirect to new route?
    if not results['results']:
        return render_template('place_search_results.html', title='Oops', error=True,
                               login_authorized=check_authorization())
    else:
        # Create a list of locations, most relevant location comes first
        location_list = []
        for result in results['results']:
            location_dict = {'formatted_address': result['formatted_address'],
                             'latitude': result['geometry']['location']['lat'],
                             'longitude': result['geometry']['location']['lng'], 'name': result['name'],
                             'place_id': result['place_id']}
            location_list.append(location_dict)
    return render_template('place_search_results.html', title='Search Results', location_list=location_list,
                           login_authorized=check_authorization())


@app.route('/collection/<string:place_id>/address/<string:address>', methods=['GET', 'POST'])
def location(place_id, address):
    search_request = requests.get('https://maps.googleapis.com/maps/api/place/details/json?key=' + google_api_key
                                  + '&place_id=' + str(place_id))
    # Now convert the response into Python dictionary
    results = search_request.json()
    place_name = results['result']['name']
    # If collection doesn't exit in the database yet
    if Collection.query.filter_by(id=place_id).first() is None:
        return render_template('place.html', place_id=place_id, in_db=False,
                               address=address.replace("%20", " ").replace("%2C", " "),
                               place_name=place_name, login_authorized=check_authorization())
    else:
        songs = Song.query.filter_by(collection_id=place_id)
        posts_dict = {}
        for song in songs:
            posts_dict[song] = Post.query.filter_by(song_id=song.song_uri, collection_id=place_id)
        return render_template('place.html', in_db=True, posts_dict=posts_dict, place_id=place_id,
                               address=address.replace("%20", " ").replace("%2C", " "), place_name=place_name,
                               login_authorized=check_authorization())


@app.route('/collection/<string:place_id>/address/<string:address>/searchmusic', methods=['GET', 'POST'])
def search_music(place_id, address):
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(
            url_for('music_search_results', input_music=search_form.search.data, place_id=place_id, address=address))
    return render_template('search.html', title='Search Music', form=search_form, search_type='Music',
                           login_authorized=check_authorization())


@app.route('/collection/<string:place_id>/address/<string:address>/musicsearchresults/<string:input_music>')
def music_search_results(place_id, address, input_music):
    search_request = requests.get('https://api.spotify.com/v1/search',
                                  headers={'Authorization': 'Bearer ' + session['access_token']},
                                  params={'q': input_music,
                                          'type': ['track']}
                                  )
    search_json = search_request.json()
    if 'error' in search_json:
        return render_template('music_search_results.html', error=True, search_json=search_json,
                               login_authorized=check_authorization())
    elif not search_json['tracks']['items']:
        return render_template('music_search_results.html', message='No results were found for this track.',
                               login_authorized=check_authorization())
    else:
        tracks_list = []
        for track in search_json['tracks']['items']:
            track_dict = {'song': track['name'],
                          'artists': [artist['name'] for artist in track['artists']],
                          'track_uri': track['uri'],
                          'preview_url': track['preview_url'],
                          'album_name': track['album']['name'],
                          'album_images': track['album']['images']
                          }
            tracks_list.append(track_dict)
        return render_template('music_search_results.html', tracks_list=tracks_list, place_id=place_id, address=address,
                               login_authorized=check_authorization())


@app.route('/collection/<string:place_id>/address/<string:address>/addsong/<string:song_uri>', methods=['GET', 'POST'])
def add_song(place_id, address, song_uri):
    post_form = PostForm()
    if post_form.validate_on_submit():
        if Collection.query.filter_by(id=place_id).first() is None:
            search_request = requests.get(
                'https://maps.googleapis.com/maps/api/geocode/json?key=' + google_api_key + '&address=' +
                address.replace(" ", "+"))
            search_json = search_request.json()
            lat = search_json['results'][0]['geometry']['location']['lat']
            lng = search_json['results'][0]['geometry']['location']['lng']
            collection = Collection(id=place_id, lat=lat, long=lng, address=address)
            db.session.add(collection)
            db.session.commit()
        search_request = requests.get('https://api.spotify.com/v1/tracks/' + str(song_uri[14:]),
                                      headers={'Authorization': 'Bearer ' + session['access_token']})
        search_json = search_request.json()
        if 'error' in search_json:
            return render_template('music_search_results.html', error=True, search_json=search_json,
                                   message=song_uri[14:],
                                   login_authorized=check_authorization())
        else:
            album_picture = search_json['album']['images'][1]['url']
            song_title = search_json['name']
            artist = search_json['artists'][0]['name']
            preview_url = search_json['preview_url']
            song = Song(song_uri=song_uri, song_title=song_title, album_picture=album_picture, collection_id=place_id,
                        artist=artist, song_preview=preview_url)
            db.session.add(song)
            db.session.commit()
            if post_form.is_anonymous.data:
                post_author_id = 'Anonymous'
                post_author_name = 'Anonymous'
            else:
                post_author_id = session['current_user_id']
                post_author_name = session['current_user_name']
            post = Post(post_content=post_form.content.data, song_id=song_uri, collection_id=place_id,
                        author_id=post_author_id, author_name=post_author_name)
            db.session.add(post)
            db.session.commit()
            return redirect(url_for('location', place_id=place_id, address=address, author_id=post_author_id,
                                    post_author_name=post_author_name))
    return render_template('post.html', form=post_form)


# @app.route('/home/<str:user_id>')
# @app.route('/home/<str:user_id>')


if __name__ == '__main__':
    scheduler = APScheduler()
    scheduler.add_interval_job(func=refresh_access_token, seconds=3500)
    scheduler.start()
    app.run()
