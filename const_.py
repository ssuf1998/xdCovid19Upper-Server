#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: const_.py
@time: 2020/8/16 21:43
@desc: xdCovid19Upper server's constants.
"""
TIME_MAPPING = {
    'morning': range(6, 12),
    'afternoon': range(12, 18),
    'evening': range(18, 23),
}


class DEFAULT_CODE:
    SUCCESS = 0
    FAILED = 1
    PARAMS_ERROR = 2


class CHECK:
    NORMAL = 0
    DB_NO_RESPONSE = 1
    ADMIN_ERR = -1


class SIGNUP_CHECK:
    NORMAL = 0
    OUTDATED = 1
    INVALID = 2
    UNKNOWN = 999


class UP_STATUS:
    UNKNOWN = 0
    OK = 1
    NOT_UP = 2
