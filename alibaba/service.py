#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import operator
import time
import redis
import pymongo
from flask import Flask, abort, request, after_this_request

class WebAPI(object):

    def __init__(self):
        self.rdb = redis.StrictRedis(host='localhost', db=9)
        self.mdb = pymongo.MongoClient(host='localhost').alibaba

    def ok(self, data):
        return self.response(200, data)

    def err(self, code):
        return self.response(code, None)

    def response(self, code, data):

        @after_this_request
        def add_header(response):
            response.headers['Content-Type'] = 'application/json'
            return response

        if 200<=code<300:
            msg = 'OK'
        elif 400<=code<500:
            msg = 'Client Error'
        elif 500<=code<600:
            msg = 'Server Error'
        else:
            msg = 'Unknown Error'

        obj = dict(code=code, msg=msg, time=time.time(), data=data)
        return json.dumps(obj)

    def parse_args(self):
        args = request.args
        cates = args['cates'].split(',')
        mintime = float(args.get('mintime', 0))
        maxtime = float(args.get('maxtime', float('inf')))
        return cates, mintime, maxtime

    def index(self):
        return self.ok(u'欢迎使用')

    def hint(self):
        try:
            cates, mintime, maxtime = self.parse_args()
            data = {}
            for cate in cates:
                zkey = 'alibaba:go:cate:%s'%cate
                count = self.rdb.zcount(zkey, mintime, maxtime)
                data[cate] = count

            return self.ok(data)
        except:
            return self.err(400)

    def poll(self):
        try:
            cates, mintime, maxtime = self.parse_args()
            data = {}
            for cate in cates:
                zkey = 'alibaba:go:cate:%s'%cate
                oids = self.rdb.zrangebyscore(zkey, mintime, maxtime)
                for item in self.mdb.go_detail.find({'oid': {'$in', oids}}):
                    print '>>>', item
            return self.ok(data)
        except:
            raise
            return self.err(400)

    def fetch(self, site, oid):
        try:
            obj = self.mdb.go_detail.find_one({'oid':oid})
            keys = ['oid', 'title', 'cates', 'time']
            data = dict(zip(keys, operator.itemgetter(*keys)(obj)))
            return self.ok(data)
        except:
            return self.err(404)

    def run(self):
        app = Flask(__name__)
        app.route('/')(self.index)
        app.route('/hint.json')(self.hint)
        app.route('/poll.json')(self.poll)
        app.route('/fetch/<site>/<oid>')(self.fetch)
        app.run(host='0.0.0.0', port=9090, debug=True)

if __name__ == "__main__":
     WebAPI().run()

