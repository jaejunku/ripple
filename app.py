from flask import Flask, render_template, request, json, jsonify
import requests, geocoder
# from flask_sql

app = Flask(__name__)

# def get_coordinates():
#     # The maps_key defined below isn't a valid Google Maps API key.
#     # You need to get your own API key.
#     # See https://developers.google.com/maps/documentation/timezone/get-api-key

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    response = geocoder.ip('me')
    coords = response.latlng
    return render_template('home.html', response=coords)

if __name__ == '__main__':
    app.run()
