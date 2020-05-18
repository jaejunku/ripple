import geocoder
import requests
from flask import Flask, render_template, redirect, url_for
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
    return render_template('layout.html', title='Home')


class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField('Search')


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
    # TODO display each result from the dictionary, allow users to pick one.
    # TODO if there is no match, allow search again or route to far-search
    # If results is empty list (no results found), we want to ask again or give option to find somewhere far away
    # Redirect to new route?
    if not results['results']:
        return render_template('search_results.html')
    else:
        location_list = []
        for location in results['results']:
            location_dict = {}
            location_dict['formatted_address'] = location['formatted_address']
            location_dict['latitude'] = location['geometry']['location']['lat']
            location_dict['longitude'] = location['geometry']['location']['lng']
            location_dict['name'] = location['name']
            location_dict['place_id'] = location['place_id']
            location_list.append(location_dict)
    return render_template('search_results.html', title='Search Results', location_list=location_list)


# @app.route('/home/<str:user_id>')
# @app.route('/home/<str:user_id>')


if __name__ == '__main__':
    app.run()