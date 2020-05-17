from flask import Flask, render_template, redirect, request, json, jsonify, url_for

import requests, geocoder

# from flask_sql

app = Flask(__name__)

# def get_coordinates():
#     # The maps_key defined below isn't a valid Google Maps API key.
#     # You need to get your own API key.
#     # See https://developers.google.com/maps/documentation/timezone/get-api-key

google_api_key = 'AIzaSyC7rX_hVNjF2MH2uQM4StN7tDtkHd0AqAk'
#TODO replace with dummy key


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    return render_template('home.html', text='hello')

@app.route('/near', methods=['GET', 'POST'])
def near():
    # Approximate user geolocation with ip address
    coords = geocoder.ip('me').latlng
    lat = str(coords[0])
    lng = str(coords[1])
    # Search query is the input from form
    inputlocation = "warwick road"
    search_request = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?key=' + google_api_key
    + '&query=' + inputlocation.replace(" ", "+") + '&location=&' + lat + ',' + lng
    + '&radius=5000&keyword=')
    # Now convert the response into Python dictionary
    results = search_request.json()
    #TODO display each result from the dictionary, allow users to pick one.
    #TODO if there is no match, allow search again or route to far-search
    return render_template('home.html', text=results)


# @app.route('/home/<str:user_id>')
#
# @app.route('/home/<str:user_id>')


if __name__ == '__main__':
    app.run()
