import os
import geocoder
import requests
from datetime import datetime
from flask import Flask, session, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, BooleanField


app = Flask(__name__)
google_api_key = 'YOUR GOOGLE API KEY'
app.config['SECRET_KEY'] = 'YOUR SECRET KEY'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

association_table = db.Table('association',
                             db.Column('collection_id', db.String, db.ForeignKey('collection.id')),
                             db.Column('song_id', db.String, db.ForeignKey('song.song_uri'))
                             )


# Database classes: A collection can have many songs, a song can have many posts

class Collection(db.Model):
    id = db.Column(db.String, primary_key=True)
    lat = db.Column(db.Float)
    address = db.Column(db.String, nullable=False)
    name = db.Column(db.String)
    long = db.Column(db.Float)
    songs = db.relationship('Song', secondary=association_table, backref=db.backref('collections', lazy='dynamic'),
                            lazy='dynamic')
    posts = db.relationship('Post', backref='collection', lazy='dynamic')

    def __repr__(self):
        return f"Collection('{self.id}')"


class Song(db.Model):
    song_uri = db.Column(db.String, primary_key=True)
    song_preview = db.Column(db.String)
    artist = db.Column(db.String, nullable=False)
    song_title = db.Column(db.String, nullable=False)
    album_picture = db.Column(db.String, nullable=False)
    users = db.relationship('Post', backref='songs', lazy='dynamic')

    def __repr__(self):
        return f"Song('{self.song_uri}', '{self.song_title}')"


class Post(db.Model):
    post_id = db.Column(db.Integer, primary_key=True)
    post_content = db.Column(db.Text)
    post_title = db.Column(db.String)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    song_id = db.Column(db.String, db.ForeignKey('song.song_uri'), nullable=False)
    collection_id = db.Column(db.String, db.ForeignKey('collection.id'), nullable=False)
    author_id = db.Column(db.String, nullable=False)
    author_name = db.Column(db.String, nullable=False)

    def __repr__(self):
        return f"Post('{self.post_id}', '{self.date_posted}')"


class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField('Search')


class PostForm(FlaskForm):
    is_anonymous = BooleanField('Anonymous')
    content = TextAreaField('Memory')
    submit = SubmitField('Post')
    post_title = StringField()


# TODO replace with dummy key

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'access_token' in session and session['access_token'] is not None:
        user_profile = requests.get('https://api.spotify.com/v1/me',
                                    headers={'Authorization': 'Bearer ' + session['access_token']})
        user_json = user_profile.json()
        session['current_user_name'] = user_json.get("display_name")
        session['current_user_id'] = user_json.get("id")
        # Calculate collections near user
        # Get rough estimate of user's location
        coords = geocoder.ip('me').latlng
        if coords is None:
            ip = request.remote_addr
            coords = geocoder.ip(str(ip))
            lat = coords[0]
            lng = coords[1]
        else:
            lat = coords[0]
            lng = coords[1]
        nearby_collections = Collection.query.order_by(
            (lat - Collection.lat) * (lat - Collection.lat) +
            (lng - Collection.long) * (lng - Collection.long)).limit(50).all()
        # Query user's personal collections, when rendering in template do if statements to avoid repeat collections
        user_posts = Post.query.filter_by(author_id=session['current_user_id']).all()
        user_collections = []
        for post in user_posts:
            if post.collection_id not in user_collections:
                user_collections.append(post.collection_id)
        final_user_collections = []
        for collection in user_collections:
            place_name = Collection.query.filter_by(id=collection).first()
            if place_name is not None:
                final_user_collections.append(place_name)
        return render_template('home.html',
                               display_name=user_json.get("display_name"),
                               nearby_collections=nearby_collections,
                               user_collections=final_user_collections,
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
        'https://accounts.spotify.com/authorize?client_id=YOURCLIENTID&response_type=code'
        '&redirect_uri=http%3A%2F%2Frippleforspotify.herokuapp.com%2Fcallback%2F')


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
            'redirect_uri': 'http://rippleforspotify.herokuapp.com/callback/',
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
    headers = {'Authorization': 'Basic YOUR SPOTIFY CLIENT ID:YOUR SPOTIFY CLIENT SECRET'}
    new_token_response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=payload)
    new_token_json = new_token_response.json()
    session['access_token'] = new_token_json.get("access_token")


@app.route('/search', methods=['GET', 'POST'])
def search_location():
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(url_for('search_location_call', input_location=search_form.search.data))
    return render_template('search.html', form=search_form, searchtype="LOCATION",
                           login_authorized=check_authorization())


@app.route('/search/<string:input_location>', methods=['GET', 'POST'])
def search_location_call(input_location):
    # Search query is the input from form
    search_request = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?key=' + google_api_key
                                  + '&query=' + input_location.replace(" ", "+"))
    # Now convert the response into Python dictionary
    results = search_request.json()
    # If results is empty list (no results found), we want to ask again
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
                                  + '&place_id=' + str(place_id) + '&fields=name')
    # Now convert the response into Python dictionary
    results = search_request.json()
    place_name = results['result']['name']
    # If collection doesn't exit in the database yet
    if Collection.query.filter_by(id=place_id).first() is None:
        return render_template('place.html', place_id=place_id, in_db=False,
                               address=address.replace("%20", " ").replace("%2C", " "),
                               place_name=place_name, login_authorized=check_authorization())
    else:
        posts = Post.query.filter_by(collection_id=place_id).order_by(Post.date_posted.desc())
        posts_dict = {}
        for post in posts:
            posts_dict[post] = Song.query.filter_by(song_uri=post.song_id).first()
        return render_template('place.html', in_db=True, posts_dict=posts_dict, place_id=place_id,
                               address=address.replace("%20", " ").replace("%2C", " "), place_name=place_name,
                               login_authorized=check_authorization())


# These functions are for searching a song that will lead to collections containing the song
@app.route('/searchsong', methods=['GET', 'POST'])
def search_song():
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(
            url_for('song_search_results', input_music=search_form.search.data))
    return render_template('search.html', title='Search Music', form=search_form,
                           searchtype="SONG", login_authorized=check_authorization())


@app.route('/searchsong/<string:input_music>', methods=['GET', 'POST'])
def song_search_results(input_music):
    search_request = requests.get('https://api.spotify.com/v1/search',
                                  headers={'Authorization': 'Bearer ' + session['access_token']},
                                  params={'q': input_music,
                                          'type': ['track']}
                                  )
    search_json = search_request.json()
    if 'error' in search_json:
        return render_template('song_search_results.html', error=True, search_json=search_json,
                               login_authorized=check_authorization())
    elif not search_json['tracks']['items']:
        return render_template('song_search_results.html', message='No results were found for this track.',
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
        return render_template('song_search_results.html', tracks_list=tracks_list,
                               login_authorized=check_authorization())


@app.route('/searchsong/getcollection/<string:song_uri>', methods=['GET', 'POST'])
def get_collections_from_song(song_uri):
    song = Song.query.filter_by(song_uri=song_uri).first()
    if not song:
        return render_template('collections_from_song.html', error=True)
    final_list = song.collections.all()
    if not final_list:
        return render_template('collections_from_song.html', error=True)
    return render_template('collections_from_song.html', final_list=final_list)


# These functions are for searching for/adding a song to a specific collection
@app.route('/collection/<string:place_id>/address/<string:address>/searchmusic', methods=['GET', 'POST'])
def search_music(place_id, address):
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(
            url_for('music_search_results', input_music=search_form.search.data, place_id=place_id, address=address))
    return render_template('search.html', title='Search Music', form=search_form, search_type='Music',
                           searchtype="SONG", login_authorized=check_authorization())


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
                               place_id=place_id, address=address, login_authorized=check_authorization())
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

    music_search_request = requests.get('https://api.spotify.com/v1/tracks/' + str(song_uri[14:]),
                                        headers={'Authorization': 'Bearer ' + session['access_token']})
    music_search_json = music_search_request.json()
    album_picture = music_search_json['album']['images'][1]['url']

    if post_form.validate_on_submit():
        if not Collection.query.filter_by(id=place_id).first():
            search_request = requests.get(
                'https://maps.googleapis.com/maps/api/place/details/json?key=' + google_api_key
                + '&place_id=' + str(place_id) + '&fields=name,geometry')
            search_json = search_request.json()
            lat = search_json['result']['geometry']['location']['lat']
            lng = search_json['result']['geometry']['location']['lng']
            name = search_json['result']['name']
            collection = Collection(id=place_id, lat=lat, long=lng, address=address, name=name)
            db.session.add(collection)
            db.session.commit()

        if post_form.is_anonymous.data:
            post_author_id = session['current_user_id']
            post_author_name = 'Anonymous'
        else:
            post_author_id = session['current_user_id']
            post_author_name = session['current_user_name']

        if 'error' in music_search_json:
            return render_template('music_search_results.html', error=True, search_json=music_search_json,
                                   message=song_uri[14:],
                                   login_authorized=check_authorization())
        else:
            # If song is not in database yet
            song = Song.query.filter_by(song_uri=song_uri).first()
            if not song:
                song_title = music_search_json['name']
                artist = music_search_json['artists'][0]['name']
                preview_url = music_search_json['preview_url']
                song = Song(song_uri=song_uri, song_title=song_title, album_picture=album_picture,
                            artist=artist, song_preview=preview_url)
                db.session.add(song)
                db.session.commit()
            # If song is in database
            collection = Collection.query.filter_by(id=place_id).first()
            collection.songs.append(song)
            db.session.commit()

            post = Post(post_content=post_form.content.data, post_title=post_form.post_title.data, song_id=song_uri,
                        collection_id=place_id,
                        author_id=post_author_id, author_name=post_author_name)
            db.session.add(post)
            db.session.commit()

            return redirect(url_for('location', place_id=place_id, address=address, author_id=post_author_id,
                                    post_author_name=post_author_name))
    return render_template('post.html', form=post_form, pictureurl=album_picture)


@app.route('/nearbycollections')
def nearby_collections():
    if 'access_token' in session and session['access_token'] is not None:
        user_profile = requests.get('https://api.spotify.com/v1/me',
                                    headers={'Authorization': 'Bearer ' + session['access_token']})
        user_json = user_profile.json()
        session['current_user_name'] = user_json.get("display_name")
        session['current_user_id'] = user_json.get("id")
        # Calculate collections near user
        # Get rough estimate of user's location
        coords = geocoder.ip('me').latlng
        if coords is None:
            ip = request.remote_addr
            coords = geocoder.ip(str(ip))
            lat = coords[0]
            lng = coords[1]
        else:
            lat = coords[0]
            lng = coords[1]
        nearby = Collection.query.order_by(
            (lat - Collection.lat) * (lat - Collection.lat) +
            (lng - Collection.long) * (lng - Collection.long)).limit(50).all()
        return render_template('nearby_collections.html', nearby_collections=nearby)
    else:
        return render_template('home.html', login_authorized=False)



@app.route('/personalcollections')
def user_collections():
    user_posts = Post.query.filter_by(author_id=session['current_user_id']).all()
    user_collections = []
    for post in user_posts:
        if post.collection_id not in user_collections:
            user_collections.append(post.collection_id)
    final_user_collections = []
    for collection in user_collections:
        place_name = Collection.query.filter_by(id=collection).first()
        if place_name is not None:
            final_user_collections.append(place_name)
    return render_template('personal_collections.html', personal_collections=final_user_collections)


if __name__ == '__main__':
    scheduler = APScheduler()
    scheduler.add_interval_job(func=refresh_access_token, seconds=3500)
    scheduler.start()
    app.run()
