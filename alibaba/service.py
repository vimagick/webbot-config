#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import operator
import time
import redis
import pymongo
from collections import defaultdict
from datetime import datetime
from itertools import ifilter, ifilterfalse, islice, tee
from operator import itemgetter, methodcaller
from flask import Flask, abort, request, after_this_request

class WebAPI(object):

    def __init__(self):

        self.rdb = redis.StrictRedis(host='localhost', db=9)
        self.mdb = pymongo.MongoClient(host='localhost')

        self.index_keys = ['mid', 'oid', 'url', 'title', 'cates', 'time']
        self.detail_keys = self.index_keys+['addr', 'buyer', 'buy_list', 'req_list', 'rfq_date', 'exp_date', 'rcv_date']
        self.contact_keys = ['mid', 'phone', 'mobile', 'contact', 'address']
        self.geo_keys = ['mid', 'longitude', 'latitude']
        self.sites = ['alibaba']

    def ok(self, data):
        return self.response(200, data)

    def err(self, code):
        return self.response(code, None)

    @staticmethod
    def json_dumps(obj):

        def default(x):
            if isinstance(x, datetime):
                z = datetime.utcfromtimestamp(0)
                return (x-z).total_seconds()
            else:
                return x

        return json.dumps(obj, indent=2, ensure_ascii=False, default=default)

    def response(self, code, data):

        @after_this_request
        def add_header(response):
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
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
        return self.json_dumps(obj)

    def parse_args(self):
        args = request.args
        sites = [i for i in args.get('sites', ','.join(self.sites)).split(',') if i in self.sites]
        cates = set(args['cates'].split(','))
        mintime = float(args.get('mintime', 0))
        maxtime = float(args.get('maxtime', float('inf')))
        skip = int(args.get('skip', 0))
        limit = int(args.get('limit', 10))
        return sites, cates, mintime, maxtime, skip, limit

    @staticmethod
    def partition(pred, iterable):
        t1, t2 = tee(iterable)
        return ifilterfalse(pred, t1), ifilter(pred, t2)

    def index(self):
        return self.ok(u'阿里求购-数据API')

    def hint(self):
        try:
            sites, cates, mintime, maxtime, _, _ = self.parse_args()
            data = defaultdict(int)
            for cate in cates:
                for site in sites:
                    zkey = '%s:go:cate:%s' % (site, cate)
                    count = self.rdb.zcount(zkey, mintime, maxtime)
                    data[cate] += count
            return self.ok(data)
        except:
            return self.err(400)

    def poll(self):
        try:
            sites, cates, mintime, maxtime, skip, limit = self.parse_args()
            data = []

            for site in sites:

                oids = dict()
                for cate in cates:
                    zkey = '%s:go:cate:%s' % (site, cate)
                    for oid,epoch in self.rdb.zrangebyscore(zkey, mintime, maxtime, withscores=True):
                        oids[oid] = epoch

                oids = oids.items()
                oids.sort(key=itemgetter(1, 0), reverse=True)
                oids = dict(islice(oids, skip, skip+limit)).keys()

                for obj in self.mdb[site].go_detail.find({'oid': {'$in': oids}}):
                    item = dict(zip(self.index_keys, itemgetter(*self.index_keys)(obj)))
                    item['site'] = site
                    data.append(item)

            data.sort(key=itemgetter('time'), reverse=True)
            return self.ok(data)
        except:
            return self.err(400)

    def fetch(self):
        try:
            args = request.args
            site = args['site']
            oid = args['oid']
            return self.fetch2(site, oid)
        except:
            return self.err(400)

    def fetch2(self, site, oid):
        try:
            if site not in self.sites:
                raise Exception()
            obj = self.mdb[site].go_detail.find_one({'oid':oid})
            data = dict(zip(self.detail_keys, operator.itemgetter(*self.detail_keys)(obj)))
            data['site'] = site
            return self.ok(data)
        except:
            return self.err(404)

    def contact(self):
        try:
            args = request.args
            site = args['site']
            mid = args['mid']
            return self.contact2(site, mid)
        except:
            return self.err(400)

    def contact2(self, site, mid):
        try:
            if site not in self.sites:
                raise Exception()
            obj = self.mdb[site].corp_contact.find_one({'mid':mid})
            data = dict(zip(self.contact_keys, operator.itemgetter(*self.contact_keys)(obj)))
            data['site'] = site
            return self.ok(data)
        except:
            return self.err(404)

    def geo(self):
        try:
            args = request.args
            site = args['site']
            mid = args['mid']
            return self.geo2(site, mid)
        except:
            return self.err(400)

    def geo2(self, site, mid):
        try:
            if site not in self.sites:
                raise Exception()
            obj = self.mdb[site].corp_geo.find_one({'mid':mid})
            data = dict(zip(self.geo_keys, operator.itemgetter(*self.geo_keys)(obj)))
            data['site'] = site
            return self.ok(data)
        except:
            return self.err(404)

    def run(self):
        app = Flask(__name__)
        app.route('/')(self.index)
        app.route('/hint.json')(self.hint)
        app.route('/poll.json')(self.poll)
        app.route('/fetch.json')(self.fetch)
        app.route('/fetch/<site>/<oid>')(self.fetch2)
        app.route('/contact.json')(self.contact)
        app.route('/contact/<site>/<mid>')(self.contact2)
        app.route('/geo.json')(self.geo)
        app.route('/geo/<site>/<mid>')(self.geo2)
        app.run(host='0.0.0.0', port=9090, debug=True)

if __name__ == "__main__":
     WebAPI().run()

