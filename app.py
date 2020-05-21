import geocoder
import requests
from datetime import datetime
from flask import Flask, flash, session, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField

app = Flask(__name__)
google_api_key = 'AIzaSyC7rX_hVNjF2MH2uQM4StN7tDtkHd0AqAk'
app.config['SECRET_KEY'] = 'b87cd65425cbfb553740894dcc2fd0fe'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)


# Database classes: A collection can have many songs, a song can have many posts
class Collection(db.Model):
    id = db.Column(db.String, primary_key=True)
    songs = db.relationship('Song', backref='collection', lazy=True)

    def __repr__(self):
        return f"Collection('{self.id}')"


class Song(db.Model):
    song_uri = db.Column(db.String, primary_key=True)
    song_title = db.Column(db.String, nullable=False)
    album_picture = db.Column(db.String, nullable=False)
    users = db.relationship('Post', backref='song', lazy=True)
    collection_id = db.Column(db.String, db.ForeignKey('collection.id'), nullable=False)

    def __repr__(self):
        return f"Song('{self.song_uri}', '{self.song_title}')"


class Post(db.Model):
    post_id = db.Column(db.Integer, primary_key=True)
    post_title = db.Column(db.String(100))
    post_picture = db.Column(db.String)
    post_content = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    song_id = db.Column(db.String, db.ForeignKey('song.song_uri'), nullable=False)

    def __repr__(self):
        return f"Post('{self.post_id}', '{self.date_posted}')"


# TODO add data required validator
class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField('Search')


# TODO replace with dummy key

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'access_token' in session:
        user_profile = requests.get('https://api.spotify.com/v1/me',
                                    headers={'Authorization': 'Bearer ' + session['access_token']})
        user_json = user_profile.json()
        return render_template('home.html',
                               display_name=user_json.get("display_name"),
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
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')
    if error:
        return redirect(url_for('home'))
    else:
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'http://127.0.0.1:5000/callback/',
            'client_id': '2bf4792df3c4489bb9720d3346d63f53',
            'client_secret': 'c615ba249c4249a1a55cf459b606819b'
        }
        token_response = requests.post('https://accounts.spotify.com/api/token', data=payload)
        token_json = token_response.json()
        session['access_token'] = token_json.get("access_token")
        session['token_type'] = token_json.get("token_type")
        session['refresh_token'] = token_json.get("refresh_token")
        session['login_authorized'] = True
        return redirect(url_for('home'))


# TODO write function to refresh access token if expired
@app.route('/refreshaccesstoken')
def refresh_access_token(refresh_token):
    pass


@app.route('/searchnear', methods=['GET', 'POST'])
def near():
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(url_for('search_near', input_location=search_form.search.data))
    return render_template('search.html', title='Search Near', form=search_form, search_type='Near')


@app.route('/searchnear/<string:input_location>', methods=['GET', 'POST'])
def search_near(input_location):
    # Approximate user geolocation with ip address
    coords = geocoder.ip('me').latlng
    lat = str(coords[0])
    lng = str(coords[1])
    # Search query is the input from form
    search_request = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?key=' + google_api_key
                                  + '&query=' + input_location.replace(" ", "+") + '&location=&' + lat + ',' + lng
                                  + '&radius=5000&keyword=')
    # Now convert the response into Python dictionary
    results = search_request.json()
    # TODO if there is no match, allow search again or route to far-search
    # If results is empty list (no results found), we want to ask again or give option to find somewhere far away
    # Redirect to new route?
    if not results['results']:
        return render_template('place_search_results.html', title='Oops', error=True)
    else:
        # Create a list of locations, most relevant location comes first
        location_list = []
        for location in results['results']:
            location_dict = {'formatted_address': location['formatted_address'],
                             'latitude': location['geometry']['location']['lat'],
                             'longitude': location['geometry']['location']['lng'], 'name': location['name'],
                             'place_id': location['place_id']}
            location_list.append(location_dict)
    return render_template('place_search_results.html', title='Search Results', location_list=location_list)


@app.route('/collection/<string:place_id>/address/<string:address>', methods=['GET', 'POST'])
def location(place_id, address):
    # Route to display
    # If collection doesn't exit in the database yet
    if Collection.query.filter_by(id=place_id).first() is None:
        return render_template('place.html', place_id=place_id, in_db=False, address=address)
    else:
        songs = Song.query.filter_by(collection_id=place_id)
        return render_template('place.html', in_db=True, songs=songs, place_id=place_id, address=address)


@app.route('/collection/<string:place_id>/searchmusic', methods=['GET', 'POST'])
def search_music(place_id):
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(url_for('music_search_results', input_music=search_form.search.data, place_id=place_id))
    return render_template('search.html', title='Search Music', form=search_form, search_type='Music')


@app.route('/collection/<string:place_id>/musicsearchresults/<string:input_music>')
def music_search_results(place_id, input_music):
    search_request = requests.get('https://api.spotify.com/v1/search',
                                  headers={'Authorization': 'Bearer ' + session['access_token']},
                                  params={'q': input_music}
                                  )
    search_json = search_request.json()
    return render_template('music_search_results.html', search_json=search_json)


# @app.route('/home/<str:user_id>')
# @app.route('/home/<str:user_id>')


if __name__ == '__main__':
    app.run()
