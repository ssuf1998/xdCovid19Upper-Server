#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: XCUAutoFiller.py
@time: 2020/8/19 22:14
@desc: XCUAutoFiller
"""

from platform import system as platform_sys
from random import randint
from time import sleep, localtime, time, strftime
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

import const_


class XCUAutoFiller(object):
    def __init__(self, headless=False) -> None:
        self._UP_PAGE_URL = 'https://xxcapp.xidian.edu.cn/site/ncov/xidiandailyup'
        self._LOGIN_URL = f'https://xxcapp.xidian.edu.cn/uc/wap/login?redirect=' \
                          f'{quote(self._UP_PAGE_URL, safe="")}'
        self._TIME_MAPPING = {
            'morning': range(6, 12),
            'afternoon': range(12, 18),
            'evening': range(18, 24),
        }

        self._driver = None
        self._log = ''
        self._users = []
        self._this_running_timestamp = 0

        self._opts = webdriver.ChromeOptions()
        self._opts.add_argument('user-agent=Mozilla/5.0 (Linux; Android 9; '
                                'COR-AL10 Build/HUAWEICOR-AL10; wv) '
                                'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
                                'Chrome/78.0.3904.62 XWEB/2581 MMWEBSDK/200701 Mobile '
                                'Safari/537.36 MMWEBID/259 MicroMessenger/7.0.17.1720(0x27001139) '
                                'Process/toolsmp WeChat/arm64 NetType/WIFI Language/zh_CN ABI/arm64')
        if platform_sys() == 'Linux':
            self._opts.add_argument('--disable-gpu')
            self._opts.add_argument("window-size=1024,768")
            self._opts.add_argument("--no-sandbox")
            self._opts.add_argument('--headless')
        elif platform_sys() == 'Windows':
            if headless:
                self._opts.add_argument('--headless')

    def _time_2_name(self) -> str:
        hour = localtime(time()).tm_hour
        for name, range_ in self._TIME_MAPPING.items():
            if hour in range_:
                return name

    def _write_log(self, sid, msg) -> None:
        self._log += f'[{self._get_formatted_time()}] [{sid}] ' \
                     f'{msg}\n'

    @staticmethod
    def _get_formatted_time():
        return strftime("%Y-%m-%d %H:%M:%S", localtime())

    @property
    def log(self):
        return self._log

    @property
    def users(self):
        return self._users

    @users.setter
    def users(self, val):
        self._users = val

    @property
    def this_running_timestamp(self):
        return self._this_running_timestamp

    def run(self):
        if not self._driver:
            self._driver = webdriver.Chrome(options=self._opts,
                                            executable_path='./chromedriver')

        for user in self._users:
            self._write_log(user['sid'],
                            'Starting auto fill-in...')

            if user['is_up'][self._time_2_name()] == const_.UP_STATUS.OK:
                self._write_log(user['sid'],
                                f'Has already filled in {self._time_2_name()}, skipping...')
                continue

            if user['is_pause']:
                self._write_log(user['sid'],
                                'Auto fill-in is paused, skipping...')
                continue

            self._driver.delete_all_cookies()
            self._driver.get(self._LOGIN_URL)

            pw = user['pw']
            fake_lat = user['coords']['latitude']
            fake_long = user['coords']['longitude']

            try:
                WebDriverWait(self._driver, 5).until(
                    expected_conditions.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input[placeholder="账号"]')
                    ))

                self._driver.find_element_by_css_selector(
                    'input[placeholder="账号"]').send_keys(user['sid'])
                sleep(1)

                self._driver.find_element_by_css_selector(
                    'input[placeholder="密码"]').send_keys(pw)
                sleep(1)

                self._driver.find_element_by_css_selector('.btn').click()

                try:
                    WebDriverWait(self._driver, 5).until(
                        expected_conditions.url_to_be(self._UP_PAGE_URL))
                    if user['is_pw_wrong']:
                        user['is_pw_wrong'] = False

                    try:
                        WebDriverWait(self._driver, 15).until(
                            expected_conditions.invisibility_of_element(
                                (By.CSS_SELECTOR, '#progress_loading')
                            ))

                        self._driver.execute_script(
                            'window.navigator.geolocation.getCurrentPosition=function(success){' +
                            'let position = {"coords" : {"latitude": "%s","longitude": "%s"}};'
                            % (fake_lat, fake_long) +
                            'success(position);}')

                        self._write_log(user['sid'],
                                        'Injecting a fake coordinate succeed.')

                        try:
                            self._driver.find_element_by_css_selector('.form-mask')
                            user['is_up'][self._time_2_name()] = const_.UP_STATUS.OK
                            self._write_log(user['sid'],
                                            f'Updated latest up status for {user["sid"]}.')
                            sleep(3)

                        except NoSuchElementException:
                            radio_css_selector = '.form ul li [name="{name}"] > div' \
                                                 ' div:nth-child({n}) span:first-child'

                            self._driver.find_element_by_css_selector('.form ul li [name="area"]').click()
                            sleep(1)
                            self._driver.find_elements_by_css_selector('.form ul li [name="tw"] > div div')[
                                randint(2, 3)].click()
                            sleep(1)

                            self._driver.find_element_by_css_selector(
                                radio_css_selector.format(name='ymtys', n=1)).click()
                            sleep(1)
                            self._driver.find_element_by_css_selector(
                                radio_css_selector.format(name='sfzx', n=1)).click()
                            sleep(1)
                            self._driver.find_element_by_css_selector(
                                radio_css_selector.format(name='sfcyglq', n=2)).click()
                            sleep(1)
                            self._driver.find_element_by_css_selector(
                                radio_css_selector.format(name='sfyzz', n=2)).click()
                            sleep(1)
                            self._driver.find_element_by_css_selector('.footers a').click()

                            try:
                                WebDriverWait(self._driver, 5).until(
                                    expected_conditions.presence_of_element_located(
                                        (By.CSS_SELECTOR, '#wapcf')
                                    ))
                                self._driver.find_element_by_css_selector('.wapcf-btn.wapcf-btn-ok').click()

                                WebDriverWait(self._driver, 10).until(
                                    expected_conditions.presence_of_element_located(
                                        (By.CSS_SELECTOR, '.hint-show .icon-chenggong')
                                    ))

                                user['is_up'][self._time_2_name()] = const_.UP_STATUS.OK
                                self._write_log(user['sid'],
                                                f'Filling of {user["sid"]} finished...')
                                sleep(3)

                            except TimeoutException:
                                self._write_log(user['sid'],
                                                'Submitting timeout!')

                    except TimeoutException:
                        self._write_log(user['sid'],
                                        'Logging timeout!')

                except TimeoutException:
                    user['is_pw_wrong'] = True
                    self._write_log(user['sid'],
                                    'Login failed.')

            except TimeoutException:
                self._write_log(user['sid'],
                                f'Entering official website failed...')

        self._driver.quit()
        self._driver = None
        self._write_log('_',
                        f'All users are completely filled, closed.\n')
        self._this_running_timestamp = int(time())
