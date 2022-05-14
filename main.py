from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
from flask_pymongo import PyMongo
import os, json, requests, base64
import config, Logger

logger=Logger.logging_start(config.Debug)

app = Flask(__name__)
app.config["MONGO_URI"] = config.MongoUri
app.config['ID_UPLOAD_FOLDER'] = config.UploadFolder + "/id"
mongo = PyMongo(app).db

def send_base64(mime, encoded):

    url = "https://base64.ai/api/scan"

    payload = json.dumps({
    "image": f"data:{mime};base64,{encoded}"
    })
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'ApiKey {config.base64_email}:{config.base64_api}'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    return response.json()

def index():
    return "Hi!"
app.add_url_rule('/', 'index', index, methods=["POST", "GET"])

def id_detect():
    if request.method == "POST":
        image = request.files['image']
        if image.filename == '':
            return {"status": "error", "message": "No selected file."}
        filename = secure_filename(image.filename)
        savedpath = os.path.join(app.config['ID_UPLOAD_FOLDER'], filename)
        image.save(savedpath)
        data = {
            "n_id": "",
            "name": "",
            "surname": ""
        }
        with open(savedpath, 'rb') as image_file:
            try:
                encoded_string = str(base64.b64encode(image_file.read())).replace("b'", "")
                base64_response = send_base64(image.mimetype, encoded_string.replace("'", ""))[0]
            except Exception as e:
                print(e)
                return {'status': 'error', 'message': 'An error occured while encoding and scanning document.'}
            print(base64_response)
            if base64_response['model']['type'] == 'id/tur' and base64_response['fields']['documentType']['isValid']:
                if base64_response['fields']['nationalIdNumber']['isValid']:
                    data['n_id'] = base64_response['fields']['nationalIdNumber']['value']
                else:
                    return {'status': 'error', 'message': 'National ID Number is Invalid.'}
                data['name'] = base64_response['fields']['givenName']['value']
                data['surname'] = base64_response['fields']['familyName']['value']
            else:
                return {"status": "error", "message": "ID is invalid."}
            return data
app.add_url_rule('/id', 'id_detect', id_detect, methods=["POST", "GET"])
        
def register():
    print('xd')
    if request.method == "POST":
        body = request.get_json()
        if mongo.users.find_one({'n_id': body['n_id']}) is not None:
            return {"status": "error", "message": "Already registered national id."}
        inserted = mongo.users.insert_one(body)
        resp = mongo.users.find_one({'_id': inserted.inserted_id})
        del resp['_id']
        return resp
app.add_url_rule('/register', 'register', register, methods=["POST", "GET"])

try:
    app.run(host=config.Host, port=config.Port, debug=config.Debug)
except Exception as e:
    logger.critical("Couldn't created webserver.")
    logger.error("ERROR", e)