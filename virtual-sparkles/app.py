import pygsheets
from flask import Flask, jsonify, send_from_directory
import os
from dotenv import load_dotenv
import random

load_dotenv()

app = Flask(__name__, static_folder='public')

# Authenticate with Google Sheets
gc = pygsheets.authorize(service_file='/Users/lucyschodell/Desktop/virtual-sparkles/virtual-sparkles-2d7ffc2eda03.json') #replace with your credentials.json file name

def get_sheet_data():
    sheet_id = os.getenv('SHEET_ID')
    sh = gc.open_by_key(sheet_id)

    quotes_sheet = sh.worksheet_by_title('Quotes')
    quotes_data = quotes_sheet.get_all_records()

    photos_sheet = sh.worksheet_by_title('Photos')
    photos_data = photos_sheet.get_all_records()

    random_quote = random.choice(quotes_data)
    random_photo = random.choice(photos_data)

    return {
        'quote': random_quote['quote'],
        'addedBy': random_quote['addedBy'],
        'photoUrl': random_photo['photoUrl'],
        'instagramName': random_photo['instagramName'],
        'instagramLink': random_photo['instagramLink'],
    }

@app.route('/data')
def data():
    data = get_sheet_data()
    return jsonify(data)

@app.route('/')
def serve_static():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
