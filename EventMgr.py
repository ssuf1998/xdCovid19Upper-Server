#!/usr/bin/env python
# encoding: utf-8
"""
@author: ssuf1998
@file: EventMgr.py
@time: 2020/8/28 17:00
@desc: Making a jq-like "on" event register.
"""


class EventMgr(object):
    def __init__(self, listener_names: tuple) -> None:
        self._event_listeners = self._gene_event_listeners(
            listener_names
        )

    @staticmethod
    def _gene_event_listeners(listener_names: tuple) -> dict:
        ret = {}
        for n in listener_names:
            ret[n] = []
        return ret

    def fire(self, listener_name, **kwargs):
        if listener_name in self._event_listeners:
            for f in self._event_listeners.get(listener_name):
                f(recall=kwargs)

    def on(self, listener_name, func) -> bool:
        if listener_name not in self._event_listeners:
            return False

        if isinstance(func, list):
            for f in func:
                self._event_listeners[listener_name].append(f)
            return True
        elif hasattr(func, '__call__'):
            self._event_listeners[listener_name].append(func)
            return True
        else:
            return False

    def remove(self, listener_name, func_name: str = '') -> bool:
        if listener_name not in self._event_listeners:
            return False

        for i, f in enumerate(self._event_listeners.get(listener_name)):
            if f.__name__ == func_name:
                self._event_listeners[listener_name].pop(i)
                return True
        return False

    def remove_all(self, listener_name) -> bool:
        if listener_name not in self._event_listeners:
            return False

        self._event_listeners[listener_name].clear()
