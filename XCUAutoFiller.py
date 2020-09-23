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
from time import sleep, localtime, strftime
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

import const_
import util
from EventMgr import EventMgr


class XCUAutoFiller(EventMgr):
    def __init__(self, headless=False, thread_name='') -> None:
        super().__init__((
            'one_finished',
            'one_started',
        ))

        self._UP_PAGE_URL = 'https://xxcapp.xidian.edu.cn/site/ncov/xidiandailyup'
        self._LOGIN_URL = f'https://xxcapp.xidian.edu.cn/uc/wap/login?redirect=' \
                          f'{quote(self._UP_PAGE_URL, safe="")}'

        self._log = ''
        self._users = []
        self._retry_users = []

        self._opts = webdriver.ChromeOptions()
        self._opts.add_argument(f'user-agent={self._get_rand_ua()}')
        self._opts.add_experimental_option('prefs', {
            'profile.managed_default_content_settings.images': 2,
            'permissions.default.stylesheet': 2
        })
        if platform_sys() == 'Linux':
            self._opts.add_argument('--disable-gpu')
            self._opts.add_argument("window-size=1024,768")
            self._opts.add_argument("--no-sandbox")
            self._opts.add_argument('--headless')
        elif platform_sys() == 'Windows':
            if headless:
                self._opts.add_argument('--headless')

        self._driver = webdriver.Chrome(options=self._opts,
                                        executable_path='./chromedriver')

        self._thread_name = thread_name

    def _write_log(self, sid, msg) -> None:
        self._log += f'[{self._thread_name}] [{self._get_formatted_time()}] [{sid}] ' \
                     f'{msg}\n'

    @staticmethod
    def _get_rand_ua():
        with open('ua_list.txt', mode='r') as fp:
            uas = fp.readlines()
            return uas[randint(0, len(uas) - 1)]

    @staticmethod
    def _get_formatted_time():
        return strftime('%Y-%m-%d %H:%M:%S', localtime())

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
    def retry_users(self):
        return self._retry_users

    @property
    def thread_name(self):
        return self._thread_name

    def run(self):
        time_name = util.time_2_name()
        self._retry_users.clear()
        for user in self._users:
            self._write_log(user['sid'],
                            'Starting auto fill-in...')

            # 填报暂停走这里
            if user['is_pause']:
                self._write_log(user['sid'],
                                'Auto fill-in is paused, skipping...')
                continue

            # 正式开填，先把Cookies清了
            self._driver.delete_all_cookies()
            self._driver.get(self._LOGIN_URL)

            pw = user['pw']
            fake_lat = user['coords']['latitude']
            fake_long = user['coords']['longitude']

            try:
                # 判断页面进去没，没进去的话日志出“进入失败”
                WebDriverWait(self._driver, 5).until(
                    expected_conditions.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input[placeholder="账号"]')
                    ))

                # 拿账号、密码元素
                self._driver.find_element_by_css_selector(
                    'input[placeholder="账号"]').send_keys(user['sid'])
                sleep(1)

                self._driver.find_element_by_css_selector(
                    'input[placeholder="密码"]').send_keys(pw)
                sleep(1)

                # 点登录
                self._driver.find_element_by_css_selector('.btn').click()

                try:
                    # 等进入填报界面，如果进不去，就是密码错了
                    WebDriverWait(self._driver, 5).until(
                        expected_conditions.url_to_be(self._UP_PAGE_URL))
                    user['is_pw_wrong'] = False

                    try:
                        # 成功进入填报界面，等界面加载下
                        WebDriverWait(self._driver, 15).until(
                            expected_conditions.visibility_of_element_located(
                                (By.CSS_SELECTOR, '.form ul li [name="area"]')
                            ))

                        # 注入假的地理位置
                        self._driver.execute_script(
                            'window.navigator.geolocation.getCurrentPosition=function(success){' +
                            'let position = {"coords" : {"latitude": "%s","longitude": "%s"}};'
                            % (fake_lat, fake_long) +
                            'success(position);}')

                        self._write_log(user['sid'],
                                        'Injecting a fake coordinate succeed.')

                        try:
                            # 如果是出现了遮罩，那就是数据库里没有更新上“已经填报”的这个状态
                            self._driver.find_element_by_css_selector('.form-mask')
                            user['is_up'][time_name] = const_.UP_STATUS.OK
                            self._write_log(user['sid'],
                                            f'Updated latest up status for {user["sid"]}.')
                            sleep(3)
                            self.fire('one_finished', user=user)

                        except NoSuchElementException:
                            # 拿底下几个单选框的选择器模板
                            radio_css_selector = '.form ul li [name="{name}"] > div' \
                                                 ' div:nth-child({n}) span:first-child'

                            # 点一下获取地理位置
                            self._driver.find_element_by_css_selector('.form ul li [name="area"]').click()

                            try:
                                # 这里等地理位置获取一会儿，超时了就说明拿不到地理位置，输出给日志
                                WebDriverWait(self._driver, 10).until(
                                    expected_conditions.invisibility_of_element(
                                        (By.CSS_SELECTOR, '#page-loading-container')
                                    ))

                                # 体温单选框，随机在36.5-37.3这两个选项里选
                                self._driver.find_elements_by_css_selector('.form ul li [name="tw"] > div div')[
                                    randint(2, 3)].click()
                                sleep(1)

                                # 一码通颜色单选框，当然是选择绿码第一个咯
                                self._driver.find_element_by_css_selector(
                                    radio_css_selector.format(name='ymtys', n=1)).click()
                                sleep(1)

                                # 是否在校，填是
                                self._driver.find_element_by_css_selector(
                                    radio_css_selector.format(name='sfzx', n=1)).click()
                                sleep(1)

                                # 是否处于隔离期，填否
                                self._driver.find_element_by_css_selector(
                                    radio_css_selector.format(name='sfcyglq', n=2)).click()
                                sleep(1)

                                # 是否有症状，填否
                                self._driver.find_element_by_css_selector(
                                    radio_css_selector.format(name='sfyzz', n=2)).click()
                                sleep(1)

                                # 其他情况那个textarea，保留不管
                                # 点提交按钮，会出一个是否确定的对话框
                                self._driver.find_element_by_css_selector('.footers a').click()

                                try:
                                    # 等提交按钮出来，没出来出日志，submitting failed
                                    WebDriverWait(self._driver, 5).until(
                                        expected_conditions.presence_of_element_located(
                                            (By.CSS_SELECTOR, '#wapcf')
                                        ))
                                    # 点确定提交对话框里的确定按钮
                                    self._driver.find_element_by_css_selector('.wapcf-btn.wapcf-btn-ok').click()

                                    # 提交成功的回显，如果没出来依旧是出日志，submitting failed
                                    WebDriverWait(self._driver, 10).until(
                                        expected_conditions.presence_of_element_located(
                                            (By.CSS_SELECTOR, '.hint-show .icon-chenggong')
                                        ))

                                    # 更新数据库咯
                                    user['is_up'][time_name] = const_.UP_STATUS.OK
                                    self._write_log(user['sid'],
                                                    f'Filling of {user["sid"]} finished...')
                                    sleep(3)
                                    self.fire('one_finished', user=user)

                                except TimeoutException:
                                    self._write_log(user['sid'],
                                                    'Submitting timeout!')
                                    self._retry_users.append(user)

                            except TimeoutException:
                                self._write_log(user['sid'],
                                                'Getting position timeout!')
                                self._retry_users.append(user)

                    except TimeoutException:
                        self._write_log(user['sid'],
                                        'Logging timeout!')
                        self._retry_users.append(user)

                except TimeoutException:
                    user['is_pw_wrong'] = True
                    self._write_log(user['sid'],
                                    'Login failed.')
                    self.fire('one_finished', user=user)

            except TimeoutException:
                self._write_log(user['sid'],
                                f'Entering official website failed...')
                self._retry_users.append(user)

        # 退出无头浏览器，清掉它释放内存（虽然好像没必要……）
        # 更新下运行成功时间
        self._driver.quit()
        self._driver = None
        self._write_log('_',
                        f'All users are completely filled, closed.')
