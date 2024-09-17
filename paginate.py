# -*- coding: utf-8 -*-
#!/usr/bin/env python
#from paginate.src.workers import (application_worker_setup, call_worker_setup, event_worker_setup, membership_worker_setup,
#                                 message_worker_setup, people_worker_setup, room_worker_setup, team_worker_setup,
#                                 team_membership_worker_setup, webhook_worker_setup)
#from paginate.src.worker import ReportWorker

import gc
from collections import Counter
import linecache
import os
import tracemalloc

def display_top(snapshot, key_type='lineno', limit=3):
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        print("#%s: %s:%s: %.1f KiB"
              % (index, filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))

import json
import time
import resource
import threading
#import traceback

import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web

import logging.handlers

from pymongo import ASCENDING

from paginate.src.login import CodeHandler, LoginHandler
#from paginate.src.rds_mysqldb_std import MySQLConnector
from paginate.src.mongo_db_controller import MongoController
from paginate.src.settings import Settings, Printer
from paginate.src.websocket import MyWebSocketHandler
from paginate.src.worker import ReportWorker

from common.alive import AliveHandler
from common.memberships import MembershipsHandler
#from common.rds_mysql_metrics import MetricsDB
from common.mongo_db_metrics import MetricsDB
from common.spark import Spark

from tornado.options import define, options, parse_command_line
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from multiprocessing import Process, Queue

define("port", default=Settings.port, help="run on the given port", type=int)
define("debug", default=False, help="run in debug mode")

class MyFileHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, path=None, include_body=True):
        print(self.request.headers)
        print(path)
        dir = os.path.join(os.path.join('paginate', 'src'), os.path.join(os.path.dirname(__file__), "static"))
        nofich = os.path.join(dir, path)
        authenticated = True
        if nofich:
            if path.startswith('files'):
                print("adding application/zip header to file download")
                self.add_header("Content-Type","application/zip")
                #print(self.get_secure_cookie("paginateSessionId"))
                spark = Spark(self.get_secure_cookie("paginateSessionId").decode('utf-8'))
                person = yield spark.get_with_retries_v2('https://api.ciscospark.com/v1/people/me')
                print(person.body.get('emails',[None]))
                if person.body.get('emails',[None])[0] in Settings.admins:
                    print("File Puller is Admin")
                else:
                    print("File Puller is not Admin")
                    authenticated = False
            if authenticated:
                with open(nofich, "rb") as f:
                    self.write(f.read())
            else:
                self.set_status(401)
                print("Writing not authorized.")
                self.write("401 Not Authorized.")
                self.finish()


class MainHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        self.application.settings['log'].info('MainHandler')
        if not self.get_secure_cookie("paginateSessionId", max_age_days=1, min_version=2):
            self.application.settings['log'].info("redirecting to login")
            self.redirect('/login')
        else:
            self.application.settings['log'].info("rendering paginate.html")
            self.application.settings['my_hostname'] = self.request.host
            self.render('paginate.html', token=self.get_secure_cookie("paginateSessionId"), socket_type=Settings.socket_type)

"""
class MessageHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    def who_am_i(self, spark):
        url = 'https://api.ciscospark.com/v1/people/me'
        result = yield spark.get_with_retries(url)
        self.application.settings['log'].info(result.body.get('displayName'))
        raise tornado.gen.Return(result.body.get('id'))

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        self.application.settings['log'].info('MessageHandler')
        if not self.get_secure_cookie("paginateSessionId"):
            self.application.settings['log'].info("401 paginateSessionId Not authorized")
            self.set_status(401)
            msg = "Not authorized"
            result = {"resource":"auth", "success":False, "message":msg}
        else:
            self.application.settings['log'].info("Authorized.")
            jobj = json.loads(self.request.body)
            token = self.get_secure_cookie("paginateSessionId").decode('utf-8')
            spark = Spark(token)
            if not self.get_secure_cookie("paginatePersonId"):
                self.application.settings['log'].info("PersonId not yet set.")
                personId = yield self.who_am_i(spark)
                self.set_secure_cookie("paginatePersonId", personId)
            else:
                self.application.settings['log'].info("PersonId previously set.")
                personId = self.get_secure_cookie("paginatePersonId").decode('utf-8')
            print(personId)
            if personId == 'Y2lzY29zcGFyazovL3VzL1BFT1BMRS9lNjAwY2ZlYS01NTczLTQwMDYtOTk1MC0yM2YzODY2Mjc1OGU':#rtaylorhanson+admin2@gmail.com
                personId = 'Y2lzY29zcGFyazovL3VzL1BFT1BMRS8zNWM0OTZiOC0zZjYyLTQ3ZTAtODliMS1lZmE3M2Q0YzVhZTQ'#Janelle
                spark = Spark('MWU2NjE3OWQtYzRmMy00OWIwLWJiZjctZjBjOTgyZWEzNWU1OWYxMTM5MDYtNGVk_PF84_602d7d50-4ed5-40fc-a8ad-63646501cd00')#Janelle
            person = self.application.settings['resource_workers'].get(personId)
            if person == None:
                self.application.settings['resource_workers'].update({personId:{}})
                person = self.application.settings['resource_workers'].get(personId)
            #print("PERSON:{0}".format(person))
            result = None
            self.application.settings["log"].info(jobj)
            if jobj.get('command') == "ping":
                result = person.get('update')
                result = "hey"
            elif jobj.get('command') == "cancel":
                if person.get('thread') == None or not person['thread'].isAlive():
                    msg = "Nothing to cancel"
                    result = {"resource":jobj.get('resource'), "command":jobj['command'], "success":False, "message":msg}
                elif person['thread'].isAlive():
                    person.update({"cancel":True})
                    self.application.settings["log"].debug("joining dead thread from cancel...")
                    while person['thread'].isAlive():
                        yield tornado.gen.sleep(3)
                    person['thread'].join()
                    self.application.settings["log"].info("Cancelled {0} run!".format(jobj.get('resource')))
                    #result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
            elif jobj.get('resource') not in [None,""]:
                self.application.settings["log"].info(self.application.settings['resource_workers'])
                if person.get('thread') != None and not person.get('thread').isAlive():
                    self.application.settings["log"].debug("joining dead thread from new open...")
                    person['thread'].join()
                    person.update({"thread":None, "cancel":False})
                    self.application.settings["log"].info(person)
                if person.get('thread') != None and person.get('thread').isAlive():
                    pass
                    #result = person.get('update')
                    #TODO: You must wait for previous command to finish
                    #msg = "You will need to wait for the previous command to finish execution before sending another."
                    #result = {"resource":jobj['resource'], "message":msg}
                elif jobj['resource'] in ['applications', 'calls', 'events', 'memberships', 'messages', 'people', 'rooms', 'teams', 'team/memberships', 'webhooks', 'bot_report', 'user_report']:
                    if jobj['command'] == "run":
                        self.application.settings["log"].info('scheduling and yielding')
                        if jobj['resource'] == "applications":
                            arglist, url_to_add = application_worker_setup(self, jobj)
                        elif jobj['resource'] == "calls":
                            arglist, url_to_add = call_worker_setup(jobj)
                        elif jobj['resource'] == "events":
                            arglist, url_to_add = event_worker_setup(jobj)
                        elif jobj['resource'] == "memberships":
                            arglist, url_to_add = membership_worker_setup(jobj)
                        elif jobj['resource'] == "messages":
                            arglist, url_to_add = message_worker_setup(jobj)
                        elif jobj['resource'] == "people":
                            arglist, url_to_add = people_worker_setup(jobj)
                        elif jobj['resource'] == "rooms":
                            arglist, url_to_add = room_worker_setup(jobj)
                        elif jobj['resource'] == "teams":
                            arglist, url_to_add = team_worker_setup(jobj)
                        elif jobj['resource'] == "team/memberships":
                            arglist, url_to_add = team_membership_worker_setup(jobj)
                        elif jobj['resource'] == "webhooks":
                            arglist, url_to_add = webhook_worker_setup(jobj)
                        person.update({"thread":None,"update":None,"cancel":False})
                        report_worker = ReportWorker(self.application.settings["log"], personId, person, spark)
                        self.application.settings["log"].debug(threading.enumerate())
                        t = threading.Thread(target=report_worker.paginate, args=[jobj, arglist, url_to_add])
                        t.start()
                        person.update({"thread":t})
                        self.application.settings["log"].debug(threading.enumerate())
                    else:
                        msg = "Invalid Command."
                        result = {"resource":jobj['resource'], "command":jobj.get('command'), "success":False, "message":msg}
                else:
                    self.application.settings["log"].info("Unsupported Resource type.")
                    msg = "Unsupported resource type:{0}".format(jobj['resource'])
                    result = {"resource":jobj['resource'], "success":False, "message":msg}
            else:
                msg = "'resource' key value must be defined."
                result = {"resource":"unknown", "success":False, "message":msg}
        if result != None:
            self.application.settings["log"].info("result:{0}".format(result))
            self.write(json.dumps(result))
        self.application.settings["log"].info('done yielding')
        self.finish()
"""
class RestartManager(object):
    def __init__(self, resource_workers, reports_db, log):
        self.workers = resource_workers
        self.reports_db = reports_db
        self.log = log
        self.starttime = time.time()
        self.max_peak = 150000

    def dump_garbage(self):
        """
        show us what's the garbage about
        """

        # force collection
        print("\nGARBAGE:")
        gc.collect()

        print("\nGARBAGE OBJECTS:")
        for x in gc.garbage:
            s = str(x)
            if len(s) > 80:
                s = s[:80]
            print("{0}\n  {1}".format(type(x), s))

    def dump_garbage2(self):
        snapshot = tracemalloc.take_snapshot()
        display_top(snapshot)

    def manage(self):
        running_reports_count = self.reports_db.count("running_reports", {})
        self.log.info("Running Reports: {0}".format(running_reports_count))
        if running_reports_count > 0:
            self.log.debug("Restarting Reports")
            self.restart_reports(self.reports_db.get_running_reports())
        self.log.debug("Starttime:{0}".format(self.starttime))
        #self.log.debug("RESOURCE_WORKERS:{0}".format(self.workers))
        peak_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        self.log.debug("PEAK USAGE:{0}".format(peak_usage))
        # show the dirt ;-)
        #self.dump_garbage2()
        if len(self.workers) == 0:
            self.log.debug("NO WORKERS, passing...")
        else:
            running = False
            for worker_key in self.workers:
                if self.workers[worker_key].get('process') != None and self.workers[worker_key].get('process').is_alive():
                    running = True
                    break
            self.log.debug("CURRENT RUNNING STATUS:{0}".format(running))
            current_time = time.time()
            current_hour = time.gmtime().tm_hour
            if not running and peak_usage > self.max_peak and current_time > self.starttime + (60 * 60 * 8):
                if current_hour < 7 and current_hour > 6:
                    self.log.debug("killing myself")
                    os.system('kill %d' % os.getpid())

    def restart_reports(self, running_reports):
        for running_report in running_reports:
            q = Queue(10)
            personId = running_report["personId"]
            self.log.warning(running_report)
            worker = self.workers.get(personId)
            self.log.debug('{0} worker:{1}'.format(personId, worker))
            if worker == None or worker.get('process') == None or not worker.get('process').is_alive():
                self.log.debug('restarting process for worker!')
                self.workers.update({personId:{"queue":q,"process":None}})
                rw = ReportWorker(Printer(), personId, running_report["personEmail"], running_report["personOrgId"], running_report["token"])
                self.log.debug(threading.enumerate())
                p = Process(target=rw.report, args=(running_report["jobj"], q))
                p.daemon = True
                p.start()
                self.workers[personId].update({"process":p})


@tornado.gen.coroutine
def main(log):
    try:
        #gc.enable()
        #gc.set_debug(gc.DEBUG_LEAK)
        parse_command_line()
        log.info(os.path.join(os.path.join(os.path.join(os.path.dirname(__file__), "paginate"),"src"),"static"))
        app = tornado.web.Application(
            [
                (r"/", MainHandler),
                (r"/alive", AliveHandler),
                (r"/ready", AliveHandler),
                (r"/login", LoginHandler),
                #(r"/memberships", MembershipsHandler),
                (r"/code", CodeHandler),
                (r"/websocket", MyWebSocketHandler),
                (r'/static/(.*)', MyFileHandler),
                #(r"/message", MessageHandler),
            ],
            template_path=os.path.join(os.path.join(os.path.join(os.path.dirname(__file__), "paginate"),"src"),"www"),
            #static_path=os.path.join(os.path.join(os.path.join(os.path.dirname(__file__), "paginate"),"src"),"static"),
            login_url="/login",
            cookie_secret=Settings.secret,
            xsrf_cookies=False,
            debug=options.debug,
            )
        app.settings['my_hostname'] = None #Don't touch. applications.py needs this.
        app.settings['log'] = log #Don't touch. applications.py needs this.
        app.settings['settings'] = Settings
        app.settings['resource_workers'] = {}
        app.settings['metrics_db'] = MetricsDB()
        reports_db = MongoController()
        app.settings['reports_db'] = reports_db
        print(reports_db.db)
        print(dir(reports_db.db))
        reports_db.db["internal_rooms"].find_one({})
        reports_db.db["internal_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["internal_reports"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["error_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["no_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["reports"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
        reports_db.db["people"].create_index([("personId", ASCENDING)], unique=True)
        reports_db.db["running_reports"].create_index([("personId", ASCENDING)], unique=True)
        server = tornado.httpserver.HTTPServer(app)
        server.bind(options.port)  # port
        log.info("Serving... on port {0}".format(Settings.port))
        server.start()

        rm = RestartManager(app.settings['resource_workers'], app.settings['reports_db'], log)
        ioloop = tornado.ioloop.IOLoop.instance()
        restart_manager_task = tornado.ioloop.PeriodicCallback(
            rm.manage,
            90 * 1000
        )
        restart_manager_task.start()
        ioloop.start()
        log.info('Done')
    except Exception as e:
        #traceback.print_exc()
        log.exception(e)

if __name__ == "__main__":
    tracemalloc.start()
    if Settings.save_logs == "true":
        LOG_DIR = "paginate/logs"
        LOG_FILE_NAME = os.path.join(LOG_DIR,'paginationlog.txt')
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR, exist_ok=True)
        LOGGING_LEVEL = logging.DEBUG
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        handler = logging.handlers.RotatingFileHandler(LOG_FILE_NAME, mode='a', maxBytes=5000000, backupCount=5)
        handler.setFormatter(formatter)
        log = logging.getLogger("pagination")
        log.addHandler(handler)
        log.setLevel(LOGGING_LEVEL)
    else:
        log = Printer()

    main(log)
