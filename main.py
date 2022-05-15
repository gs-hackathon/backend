from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
from flask_pymongo import PyMongo
import os, json, requests, base64, re
from datetime import datetime
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

def mongo_insert(db, content, collection):
    x = mongo.counters.insert_one({'collection': collection})
    i_id = len(list(mongo.counters.find({'collection': collection})))
    content['id'] = i_id
    content['created_at'] = round(datetime.now().timestamp())
    content['updated_at'] = round(datetime.now().timestamp())
    return db.insert_one(content)

def mongo_update(db, query, content):
    content['updated_at'] = round(datetime.now().timestamp())
    return db.update_one(query, {'$set': content})

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
                #if base64_response['fields']['nationalIdNumber']['isValid']:
                #    data['n_id'] = base64_response['fields']['nationalIdNumber']['value']
                #else:
                #    return {'status': 'error', 'message': 'National ID Number is Invalid.'}
                data['n_id'] = base64_response['fields']['nationalIdNumber']['value']
                data['name'] = base64_response['fields']['givenName']['value']
                data['surname'] = base64_response['fields']['familyName']['value']
                data['isValid'] = base64_response['fields']['nationalIdNumber']['isValid']
            else:
                return {"status": "error", "message": "ID is invalid."}
            return data
        
def register():
    if request.method == "POST":
        body = request.get_json()
        if mongo.users.find_one({'n_id': body['n_id']}) is not None:
            return {"status": "error", "message": "Already registered national id."}
        body['challenges'] = []
        body['points'] = 0.00
        body['created_at'] = round(datetime.now().timestamp())
        body['updated_at'] = round(datetime.now().timestamp())
        inserted = mongo.users.insert_one(body)
        resp = mongo.users.find_one({'_id': inserted.inserted_id})
        del resp['_id']
        return resp

def login():
    if request.method == "POST":
        body = request.get_json()
        if mongo.users.find_one({'n_id': body['n_id']}) is None:
            return {"status": "error", "message": "This national id is not registered."}
        resp = mongo.users.find_one({'n_id': body['n_id']})
        del resp['_id']
        if resp['password'] == body['password']:
            return resp
        else:
            return {'status': 'error', 'message': 'Password is not match.'}

def user(u_id=None):
    if request.method == "GET":
        if u_id is not None:
            resp = mongo.users.find_one({'n_id': u_id})
            if resp is None:
                return {"status": "error", "message": "This national id is not registered."}
            del resp['_id']
            del resp['password']
            return resp
        else:
            users = [{k: v for k, v in x.items() if k != '_id' and k != 'password'} for x in list(mongo.users.find())]
            return {"list": sorted(users, key=lambda x: x['points'], reverse=True)}

def item(i_id=None):
    if i_id:
        data = mongo.items.find_one({'id': int(i_id)})
        print(data)
        if data:
            del data['_id']
            return data
        else:
            return {'status': 'error', 'message': 'No Item Finded With ID %s' % i_id}
    else:
        if request.method == "POST":
            body = request.get_json()
            body['continent_name'] = (re.sub(r'[^\w\s]', '', body['name'].lower()).replace(' ', '_')).translate(str.maketrans("çğıöşü", "cgiosu"))
            resp = mongo.items.find_one({'_id': inserted.inserted_id})
            inserted = mongo_insert(mongo.items, body, 'items')
            resp = mongo.items.find_one({'_id': inserted.inserted_id})
            del resp['_id']
            return resp
        elif request.method == "GET":
            get_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.items.find())]
            print(get_all)
            return {'list': get_all}

def challenges(c_id=None):
    if c_id:
        data = mongo.challenges.find_one({'id': int(c_id)})
        if data:
            del data['_id']
            return data
        else:
            return {'status': 'error', 'message': 'No Challenge Finded With ID %s' % c_id}
    else:
        if request.method == "POST":
            body = request.get_json()
            body['continent_name'] = (re.sub(r'[^\w\s]', '', body['name'].lower()).replace(' ', '_')).translate(str.maketrans("çğıöşü", "cgiosu"))
            inserted = mongo_insert(mongo.challenges, body, 'challenges')
            resp = mongo.challenges.find_one({'_id': inserted.inserted_id})
            del resp['_id']
            return resp
        elif request.method == "GET":
            get_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.challenges.find())]
            print(get_all)
            return {'list': get_all}

def challenge_assign(n_id, c_id=None):
    if request.method == "GET":
        if c_id is None:
            resp = mongo.users.find_one({'n_id': n_id})
            if resp is None:
                return {"status": "error", "message": "This national id is not registered."}
            return {'data': resp['challenges']}
        else:
            return {'status': 'error', 'message': 'Please remove challenge id in request for get user challenges.'}
    elif request.method == "POST":
        if c_id is not None:
            c_id = int(c_id)
            user = mongo.users.find_one({'n_id': n_id})
            challenge = mongo.challenges.find_one({'id': c_id})
            if user == None:
                return {"status": "error", "message": "This national id is not registered."}
            if challenge == None:
                return {"status": "error", "message": "This challenge id is not finded."}
            challenges = user['challenges']
            if c_id in challenges:
                return {"status": "error", "message": "User already have this challenge."}
            user['challenges'].append(c_id)
            user['updated_at'] = round(datetime.now().timestamp())
            updated = mongo_update(mongo.users, {'n_id': n_id}, {'challenges': user['challenges']})
            del user['_id']
            return user
        else:
            return {'status': 'error', 'message': 'Please give challenge id in request for assign challenge to user.'}

def unassign_challenge(n_id, c_id):
    if request.method == "POST":
        if c_id is not None:
            c_id = int(c_id)
            user = mongo.users.find_one({'n_id': n_id})
            challenge = mongo.challenges.find_one({'id': c_id})
            if user == None:
                return {"status": "error", "message": "This national id is not registered."}
            if challenge == None:
                return {"status": "error", "message": "This challenge id is not finded."}
            challenges = user['challenges']
            if c_id not in challenges:
                return {"status": "error", "message": "User does not have this challenge."}
            user['challenges'].remove(c_id)
            user['updated_at'] = round(datetime.now().timestamp())
            user['points'] = float(user['points']) + float(challenge['reward'])
            updated = mongo_update(mongo.users, {'n_id': n_id}, {'challenges': user['challenges'], 'points': user['points']})
            del user['_id']
            return user
        else:
            return {'status': 'error', 'message': 'Please give challenge id in request for assign challenge to user.'}

def order():
    if request.method == "GET":
        body = request.get_json()
        if body['order_status'] == 1:
            del body['order_status']
            get_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.orders.find(body))]
            return {'list': get_all}
        elif body['order_status'] == -1:
            del body['order_status']
            get_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.closed_orders.find(body))]
            return {'list': get_all}
        elif body['order_status'] == 0:
            del body['order_status']
            closed_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.closed_orders.find(body))]
            open_all = [{k: v for k, v in x.items() if k != '_id'} for x in list(mongo.orders.find(body))]
            get_all = open_all + closed_all
            return {'list': get_all}
    elif request.method == "POST":
        if request.args.get("status") == "new":
            order = mongo_insert(mongo.orders, request.get_json(), 'orders')
            order = mongo.orders.find_one({'_id': order.inserted_id})
            del order['_id']
            return order
        elif request.args.get("status") == "closed":
            body = request.get_json()
            order = mongo.orders.find_one(body)
            if order is not None:
                del order['_id']
                del order['id']
                del order['created_at']
                del order['updated_at']
                totalReward = 0.0
                for itemId in order['items']:
                    item = mongo.items.find_one({'id': itemId})
                    totalReward += float(item['value'])
                order['reward'] = totalReward
                mongo.orders.delete_one(body)
                closed_order = mongo_insert(mongo.closed_orders, order, "closed_orders")
                closed_order = mongo.closed_orders.find_one({'_id': closed_order.inserted_id})
                del closed_order['_id']
                return closed_order
            else:
                return {'status': 'error', 'message': 'Order is not found.'}
    
app.add_url_rule('/id', 'id_detect', id_detect, methods=["POST", "GET"])
app.add_url_rule('/register', 'register', register, methods=["POST", "GET"])
app.add_url_rule('/login', 'login', login, methods=["POST", "GET"])
app.add_url_rule('/user', 'user', user, methods=["GET"])
app.add_url_rule('/user/<u_id>', 'user', user, methods=["GET"])
app.add_url_rule('/item', 'item', item, methods=["POST", "GET"])
app.add_url_rule('/item/<i_id>', 'item', item, methods=["POST", "GET"])     
app.add_url_rule('/challenges', 'challenges', challenges, methods=["POST", "GET"])
app.add_url_rule('/challenges/<c_id>', 'challenges', challenges, methods=["POST", "GET"])
app.add_url_rule('/challenges/assign/<n_id>', 'challenge assign', challenge_assign, methods=["POST", "GET"])
app.add_url_rule('/challenges/assign/<n_id>/<c_id>', 'challenge assign', challenge_assign, methods=["POST", "GET"])
app.add_url_rule('/challenges/unassign/<n_id>/<c_id>', 'challenge un assign', unassign_challenge, methods=["POST"])
app.add_url_rule('/order', 'order', order, methods=["POST", "GET"])

try:
    app.run(host=config.Host, port=config.Port, debug=config.Debug)
except Exception as e:
    logger.critical("Couldn't created webserver.")
    logger.error("ERROR", e)