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


# 用于检查服务器是否正常运行，数据库还好着不
@app.route('/check', methods=['GET'])
def check():
    try:
        db_client.server_info()

        sys_params = sys_col.find_one({
            '_id': ObjectId('5f4259d3e091c53e98b17847')
        }, {
            'has_err_info': True,
            'err_info': True,
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


# 看是不是新用户
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


# 注册
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


# 登录
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


# 获取用户信息，包括填报状态啊等
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


# 注销用户
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


# 更新用户信息，改密码、暂停等功能
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


# 获取基本的系统信息，比如最近成功运行时间
# 还提供了自定义三次填报状态前的emoji的功能
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


# 验证码生成，发给前端一个base64
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


# 验证码检验
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


# 当filler在填完一个用户后，会回调这个函数
def one_user_fill_finished(**kwargs):
    user = kwargs.get('recall').get('user')
    if user:
        user_col.update_one({
            'sid': user['sid']
        }, {
            '$set': {
                'is_pw_wrong': user['is_pw_wrong'],
                'is_up': user['is_up'],
            }
        })


# 自动填报核心！
def run_auto_fill_in(wanna_fill_users):
    try:
        filler = XCUAutoFiller()
        filler.on('one_finished', one_user_fill_finished)
        filler.users = wanna_fill_users
        filler.run()

        with open('./log/auto_filler.log', mode='a') as fp:
            fp.write(filler.log)
    except Exception as auto_fill_e:
        app.logger.error(auto_fill_e)


# APSCHEDULE的定时任务
# 8-22点是正常检查填报
# 0点是全部还原为“暂未填报”状态
# 其他时间休息~
def timing_auto_fill_in():
    sys_params = sys_col.find_one({
        '_id': ObjectId('5f4259d3e091c53e98b17847')
    }, {
        'has_err_info': True,
        '_id': False
    })
    if not sys_params.get('has_err_info'):
        if localtime(time()).tm_hour == 0 and localtime(time()).tm_min == 5:
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
            filler_ = {
                f'is_up.{util.time_2_name()}': const_.UP_STATUS.NOT_UP,
                'is_pw_wrong': True
            }

            if localtime(time()).tm_min != 5:
                filler_.pop('is_pw_wrong')

            fill_users = user_col.find(
                filler_, {
                    '_id': False
                }
            )

            if not fill_users:
                run_auto_fill_in(util.bson_to_obj(fill_users))

        sys_col.update_one({
            '_id': ObjectId('5f4259d3e091c53e98b17847')
        }, {
            '$set': {
                'last_suc_timestamp': int(time())
            }
        })


# 定时填报任务定义
class FlaskConfig(object):
    JOBS = [
        {
            'id': 'timing_auto_fill_in',
            'func': 'app:timing_auto_fill_in',
            'trigger': 'cron',
            'args': [],
            'hour': '8-22,0',
            'minute': '5,25,45'
        },
    ]

    SCHEDULER_API_ENABLED = True


app.config.from_object(FlaskConfig)


# 为了防止在gunicorn里一开，n个worker整的定时任务搞出n个来
# 上个文件锁，就不会惹
# 思路 https://blog.csdn.net/qq_22034353/article/details/89362959
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
    timing_auto_fill_in()
else:
    init_scheduler_once()
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
