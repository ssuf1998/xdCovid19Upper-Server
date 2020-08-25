#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: util.py
@time: 2020/8/19 21:25
@desc: xdCovid19Upper server's util.
"""
import base64
import json
from io import BytesIO
from random import sample

from bson import json_util
from captcha.image import ImageCaptcha


def bson_to_obj(o):
    return json.loads(json_util.dumps(o))


def check_params(params_dict: dict, keys: tuple, method='all'):
    if method == 'all':
        for key in keys:
            if key not in params_dict.keys():
                return False
        return True
    elif method == 'have_one':
        for key in keys:
            if key in params_dict.keys():
                return True
        return False
    else:
        return False


def gene_captcha_str():
    base_char = 'qwertyuiopasdfghjklzxcvbnm' \
                'QWERTYUIOPASDFGHJKLZXCVBNM' \
                '12345678901234567890' \
                '12345678901234567890'
    return ''.join(sample(base_char, 4))


def gene_captcha_b64img(captcha_str):
    img = ImageCaptcha().generate_image(captcha_str)
    img_buffer = BytesIO()
    img.save(img_buffer, 'png')
    res = img_buffer.getvalue()
    img_buffer.close()

    return f'data:image/png;base64,{base64.b64encode(res).decode("utf-8")}'
