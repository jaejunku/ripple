import geocoder
import requests
from flask import Flask, flash, render_template, redirect, url_for, request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField

# from flask_sql

app = Flask(__name__)

# def get_coordinates():
#     # The maps_key defined below isn't a valid Google Maps API key.
#     # You need to get your own API key.
#     # See https://developers.google.com/maps/documentation/timezone/get-api-key

google_api_key = 'AIzaSyC7rX_hVNjF2MH2uQM4StN7tDtkHd0AqAk'
app.config['SECRET_KEY'] = 'b87cd65425cbfb553740894dcc2fd0fe'


# TODO replace with dummy key


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    submit = SubmitForm()

    return render_template('layout.html', title='Home')


class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField('Search')


class SubmitForm(FlaskForm):
    submit = SubmitField()


@app.route('/authorize', methods=['GET'])
def authorize():
    return redirect(
        'https://accounts.spotify.com/authorize?client_id=2bf4792df3c4489bb9720d3346d63f53&response_type=code'
        '&redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fcallback%2F')


@app.route('/callback/', methods=['GET', 'POST'])
def callback():
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://127.0.0.1:5000/callback/',
        'client_id': '2bf4792df3c4489bb9720d3346d63f53',
        'client_secret': 'c615ba249c4249a1a55cf459b606819b'
    }
    token_response = requests.post('https://accounts.spotify.com/api/token', data=payload)
    token_text = token_response.json()
    return render_template('layout.html', token_response=token_text, code=code)

@app.route('/refreshaccesstoken')
def refresh_access_token():
    pass

@app.route('/near', methods=['GET', 'POST'])
def near():
    search_form = SearchForm()
    if search_form.validate_on_submit():
        return redirect(url_for('search_near', input_location=search_form.search.data))
    return render_template('near.html', title='Search Near', form=search_form)


@app.route('/near/<string:input_location>', methods=['GET', 'POST'])
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
        return render_template('search_results.html', title='Oops', error=True)
    else:
        # Create a list of locations, most relevant location comes first
        location_list = []
        for location in results['results']:
            location_dict = {'formatted_address': location['formatted_address'],
                             'latitude': location['geometry']['location']['lat'],
                             'longitude': location['geometry']['location']['lng'], 'name': location['name'],
                             'place_id': location['place_id']}
            location_list.append(location_dict)
    return render_template('search_results.html', title='Search Results', location_list=location_list)


@app.route('/home/<string:place_id>', methods=['GET', 'POST'])
def location(place_id):
    return render_template('place.html', place_id=place_id)


# @app.route('/<string:place_id>/<string:music_search>/)
#
# @app.route('/<string:place_id>/<string:music_search>/)


# @app.route('/home/<str:user_id>')
# @app.route('/home/<str:user_id>')


if __name__ == '__main__':
    app.run()
