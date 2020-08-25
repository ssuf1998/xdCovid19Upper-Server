#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: xcu_server_keeper.py
@time: 2020/8/23 20:59
@desc: xcu's server keeper.
"""
import re
from os import mkdir
from os import popen
from os.path import exists
from platform import system as platform_sys
from time import time, localtime, strftime

import pymongo
from apscheduler.schedulers.blocking import BlockingScheduler
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError

db_client = pymongo.MongoClient(serverSelectionTimeoutMS=5000)
data_db = db_client['xcu']
sys_col = data_db['sys']


def do_keep():
    sys_params = sys_col.find_one({
        '_id': ObjectId('5f4259d3e091c53e98b17847')
    }, {
        'has_err_info': True,
        'last_suc_timestamp': True,
        '_id': False
    })

    if not sys_params.get('has_err_info'):
        if localtime(time()).tm_hour in range(8, 23):
            try:
                last_suc_timestamp = int(sys_params.get('last_suc_timestamp'))

                if int(time()) - last_suc_timestamp > 60 * 40:
                    xcus_status_raw = popen('systemctl status xcu_server').read()
                    xcus_status = re.search('(?<=Active: )(.*)(?= since)', xcus_status_raw)
                    if xcus_status:
                        xcus_status = xcus_status.group(0)
                        with open('./log/xcu_server_keeper.log', mode='a') as fp:
                            if xcus_status.find('active') != -1:
                                popen('systemctl restart xcu_server')
                                fp.write(f'[{strftime("%Y-%m-%d %H:%M:%S", localtime())}] restarted.\n')
                            else:
                                popen('systemctl start xcu_server')
                                fp.write(f'[{strftime("%Y-%m-%d %H:%M:%S", localtime())}] started.\n')

            except ServerSelectionTimeoutError:
                pass


if not exists('./log'):
    mkdir('./log')

if platform_sys() == 'Linux':
    scheduler = BlockingScheduler()
    scheduler.add_job(do_keep, 'cron', minute='45')
    scheduler.start()
