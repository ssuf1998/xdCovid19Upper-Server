#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: app.py
@time: 2020/8/16 21:23
@desc: xdCovid19Upper server.
"""
import json
import logging
from atexit import register as atexit_reg
from os import mkdir
from os.path import exists
from time import localtime, time

import pymongo
from bson.objectid import ObjectId
from flask import Flask, jsonify, make_response
from flask import request as flask_req
from flask_apscheduler import APScheduler
from flask_cors import CORS
from pymongo.errors import ServerSelectionTimeoutError

import const_
import util
from XCUAutoFiller import XCUAutoFiller

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})
app.secret_key = 'pcUxxkZT9T2Ad7/RVJMdkmb74GtbRveb'

FAKE_LAT = '34.128733'
FAKE_LONG = '108.832142'

db_client = pymongo.MongoClient(serverSelectionTimeoutMS=5000)
data_db = db_client['xcu']
user_col = data_db['user']
invitation_col = data_db['invitation']
sys_col = data_db['sys']

captcha_dict = {}


@app.route('/check', methods=['GET'])
def check():
    try:
        db_client.server_info()

        sys_params = sys_col.find_one({
            '_id': ObjectId('5f4259d3e091c53e98b17847')
        }, {
            'id': False,
            'last_suc_timestamp': False
        })

        if sys_params.get('has_err_info'):
            return make_response(jsonify({
                'code': const_.CHECK.ADMIN_ERR,
                'msg': sys_params.get('err_info').get('msg'),
                'raw': sys_params.get('err_info').get('raw_err'),
            }), 403)

        return jsonify({
            'code': const_.CHECK.NORMAL,
            'msg': '',
            'raw': '',
        })
    except ServerSelectionTimeoutError:
        return make_response(jsonify({
            'code': const_.CHECK.DB_NO_RESPONSE,
            'msg': '',
            'raw': 'Database is not responding.',
        }), 500)


@app.route('/isnewuser', methods=['POST'])
def is_new_user():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    sid = form_data.get('sid')

    if not sid:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'bool': None,
            'msg': '参数错误。'
        }), 400)

    if user_col.count_documents({
        'sid': sid
    }) == 0:
        return jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'bool': True,
            'msg': ''
        })
    else:
        return jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'bool': False,
            'msg': ''
        })


@app.route('/signup', methods=['POST'])
def signup():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    if not util.check_params(
            form_data,
            ('code', 'sid', 'pw')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'valid': const_.SIGNUP_CHECK.UNKNOWN,
            'msg': '参数错误。'
        }), 403)

    client_code = form_data.get('code')
    sid = form_data.get('sid')
    pw = form_data.get('pw')

    if user_col.count_documents({
        'sid': sid
    }) != 0:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'valid': const_.SIGNUP_CHECK.UNKNOWN,
            'msg': '请勿重复注册。'
        }), 403)

    server_code = invitation_col.find_one({
        'code': client_code
    }, {
        'times': True
    })

    if not server_code:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'valid': const_.SIGNUP_CHECK.INVALID,
            'msg': '邀请码无效。'
        }))
    elif server_code['times'] == 0:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'valid': const_.SIGNUP_CHECK.OUTDATED,
            'msg': '邀请码已过期。'
        }))
    else:
        times = server_code['times'] - 1 \
            if server_code['times'] > 0 \
            else server_code['times']

        coords = form_data.get('coords') if form_data.get('coords') else {
            'latitude': FAKE_LAT,
            'longitude': FAKE_LONG
        }

        now_hour = localtime(time()).tm_hour
        now_minute = localtime(time()).tm_min

        new_user = {
            'sid': sid,
            'pw': pw,
            'coords': coords,
            'is_pause': False,
            'is_pw_wrong': False,
            'is_up': {
                'morning': const_.UP_STATUS.UNKNOWN
                if now_hour > 12 or (now_hour == 11 and now_minute > 5)
                else const_.UP_STATUS.NOT_UP,

                'afternoon': const_.UP_STATUS.UNKNOWN
                if now_hour > 18 or (now_hour == 17 and now_minute > 5)
                else const_.UP_STATUS.NOT_UP,

                'evening': const_.UP_STATUS.NOT_UP
            }
        }

        user_col.insert_one(new_user)
        invitation_col.update_one({
            'code': client_code
        }, {
            '$set': {
                'times': times
            }
        })

        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'valid': const_.SIGNUP_CHECK.NORMAL,
            'msg': ''
        }))


@app.route('/login', methods=['POST'])
def login():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    if not util.check_params(
            form_data,
            ('sid', 'pw')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    sid = form_data.get('sid')
    pw = form_data.get('pw')

    if user_col.find_one({
        'sid': sid,
        'pw': pw
    }):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'msg': '登录成功。'
        }))
    else:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'msg': '学号或密码错误，请核对后重试！'
        }), 403)


@app.route('/getuserinfo', methods=['POST'])
def get_user_info():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    if not util.check_params(
            form_data,
            ('sid', 'pw')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    sid = form_data.get('sid')
    pw = form_data.get('pw')

    specific_user = user_col.find_one({
        'sid': sid,
        'pw': pw
    }, {
        '_id': False,
        'sid': False,
        'pw': False,
        'coords': False
    })

    if specific_user:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'user_info': util.bson_to_obj(specific_user),
        }))
    else:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'user_info': None,
        }), 404)


@app.route('/deluser', methods=['POST'])
def del_user():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    if not util.check_params(
            form_data,
            ('sid', 'pw')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    sid = form_data.get('sid')
    pw = form_data.get('pw')

    count = user_col.delete_one({
        'sid': sid,
        'pw': pw
    }).deleted_count

    if count:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'msg': ''
        }))
    else:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'msg': '未知错误，可能数据库正忙。'
        }))


@app.route('/updateuserinfo', methods=['POST'])
def update_user_info():
    form_data = flask_req.form if len(flask_req.form) != 0 else json.loads(flask_req.data)

    if not util.check_params(
            form_data,
            ('sid', 'pw', 'new_user_info')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    sid = form_data.get('sid')
    pw = form_data.get('pw')
    new_user_info = form_data.get('new_user_info')

    if not util.check_params(
            new_user_info,
            ('pw', 'coords', 'is_pause'),
            method='have_one'):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    count = user_col.update_one({
        'sid': sid,
        'pw': pw,
    }, {
        '$set': new_user_info
    }).matched_count

    if count:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.SUCCESS,
            'msg': '参数错误。'
        }))
    else:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'msg': '未知错误，可能数据库正忙。'
        }))


@app.route('/getbasesysinfo', methods=['GET'])
def get_base_sys_info():
    base_sys_info = sys_col.find_one({
        '_id': ObjectId('5f4259d3e091c53e98b17847')
    }, {
        'last_suc_timestamp': True,
        'up_icons': True,
    })

    return make_response(jsonify({
        'code': const_.DEFAULT_CODE.SUCCESS,
        'info': util.bson_to_obj(base_sys_info),
    }))


@app.route('/captcha', methods=['GET'])
def captcha():
    captcha_id = flask_req.args.get('cid')

    if not captcha_id:
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'img': ''
        }), 400)

    captcha_str = util.gene_captcha_str()
    captcha_b64img = util.gene_captcha_b64img(captcha_str)

    captcha_dict[captcha_id] = captcha_str.lower()

    return make_response(jsonify({
        'code': const_.DEFAULT_CODE.SUCCESS,
        'img': captcha_b64img
    }))


@app.route('/checkcaptcha', methods=['GET'])
def check_captcha():
    if not util.check_params(
            flask_req.args,
            ('v', 'cid')):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.PARAMS_ERROR,
            'msg': '参数错误。'
        }), 400)

    client_captcha = flask_req.args.get('v')
    captcha_id = flask_req.args.get('cid')

    if client_captcha.lower() != captcha_dict.get(captcha_id):
        return make_response(jsonify({
            'code': const_.DEFAULT_CODE.FAILED,
            'msg': '验证码错误。'
        }))

    captcha_dict.pop(captcha_id)
    return jsonify({
        'code': const_.DEFAULT_CODE.SUCCESS,
        'msg': ''
    })


def a_user_fill_finished(**kwargs):
    user = kwargs.get('user')
    if user:
        user_col.update_one({
            'sid': user['sid']
        }, {
            '$set': {
                'is_pw_wrong': user['is_pw_wrong'],
                'is_up': user['is_up'],
            }
        })


def run_auto_fill_in(wanna_fill_users):
    try:
        filler = XCUAutoFiller()
        filler.users = wanna_fill_users
        filler.run(a_user_fill_finished)

        with open('./log/auto_filler.log', mode='a') as fp:
            fp.write(filler.log)
        sys_col.update_one({
            '_id': ObjectId('5f4259d3e091c53e98b17847')
        }, {
            '$set': {
                'last_suc_timestamp': filler.this_running_timestamp
            }
        })
    except Exception as auto_fill_e:
        app.logger.error(auto_fill_e)


def timing_auto_fill_in():
    sys_params = sys_col.find_one({
        '_id': ObjectId('5f4259d3e091c53e98b17847')
    }, {
        'has_err_info': True,
        '_id': False
    })
    if not sys_params.get('has_err_info'):
        if localtime(time()).tm_hour == 0:
            user_col.update_many({}, {
                '$set': {
                    'is_up': {
                        'morning': const_.UP_STATUS.NOT_UP,
                        'afternoon': const_.UP_STATUS.NOT_UP,
                        'evening': const_.UP_STATUS.NOT_UP,
                    }
                }
            })
        else:
            run_auto_fill_in(util.bson_to_obj(user_col.find({}, {'_id': False})))


class FlaskConfig(object):
    JOBS = [
        {
            'id': 'timing_auto_fill_in',
            'func': 'app:timing_auto_fill_in',
            'trigger': 'cron',
            'args': [],
            'hour': '8-22,0',
            'minute': '5'
        },
    ]

    SCHEDULER_API_ENABLED = True


app.config.from_object(FlaskConfig)


def init_scheduler_once():
    scheduler = APScheduler()
    fcntl = __import__("fcntl")
    f = open('scheduler.lock', 'wb')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scheduler.init_app(app)
        scheduler.start()
    except Exception as lock_e:
        app.logger.warning(lock_e)

    def unlock():
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

    atexit_reg(unlock)


def close_db():
    db_client.close()


atexit_reg(close_db)

if not exists('./log'):
    mkdir('./log')

if __name__ == '__main__':
    # init_scheduler_once()
    # app.run(host='0.0.0.0', port=5015)
    run_auto_fill_in(util.bson_to_obj(user_col.find({}, {'_id': False})))
else:
    init_scheduler_once()
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
