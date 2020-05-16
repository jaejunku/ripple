from flask import Flask, render_template
from flask_sql

app = Flask(__name__)


@app.route('/')
@app.route('/home')
def home():
    return render_template()



if __name__ == '__main__':
    app.run()
