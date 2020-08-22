#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: util.py
@time: 2020/8/19 21:25
@desc: xdCovid19Upper server's util.
"""
from bson import json_util
import json


def bson_to_obj(o):
    return json.loads(json_util.dumps(o))
