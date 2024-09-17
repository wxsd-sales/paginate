from concurrent.futures import ThreadPoolExecutor


#import gc
import json
import traceback
import threading
import urllib
#import weakref
from multiprocessing import Process, Queue

#import tornado.concurrent
import tornado.gen
import tornado.websocket

from common.spark import Spark
from paginate.src.settings import Printer

from paginate.src.workers import (application_worker_setup, attachment_actions_worker_setup, call_worker_setup, devices_worker_setup,
                                 event_worker_setup, licenses_worker_setup, membership_worker_setup, message_worker_setup, messages_direct_worker_setup,
                                 people_worker_setup, people_me_worker_setup, places_worker_setup, roles_worker_setup, room_worker_setup,
                                 room_meetinginfo_worker_setup, team_worker_setup, team_membership_worker_setup, webhook_worker_setup)
from paginate.src.worker import ReportWorker

#https://api.ciscospark.com/v1/applications?enableMarketplaceCode=true&enableApplicationsV2=true&botEmail=acronyms@sparkbot.io
#is good if you know bot email
#https://api.ciscospark.com/v1/applications?enableMarketplaceCode=true&enableApplicationsV2=true&submissionStatus=approved&max=500
#will get you approved for app hub

class MyWebSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        self.is_open = True
        self.personId = None
        self.personEmail = None
        self.personOrgId = None
        key_dict = {"applications": False,
                    "attachment/actions/id":False,
                    "calls":False,
                    "devices":False,
                    "events":False,
                    "licenses":False,
                    "memberships":False,
                    "messages":False,
                    "messages/direct":False,
                    "people":False,
                    "people/me":False,
                    "places":False,
                    "roles":False,
                    "rooms":False,
                    "rooms/id/meetingInfo":False,
                    "teams":False,
                    "team/memberships":False,
                    "webhooks":False,
                    "guest":False
                    }
        self.cancel = dict(key_dict)
        self.running = dict(key_dict)
        self.cancel_main = False#redundant with self.cancel, but there isn't a current need to allow different types of resource commands at once
        self.running_main = False#redundant with self.running, but there isn't a current need to allow different types of resource commands at once
        self.spark = None
        self.log = self.application.settings["log"]
        self.log.info("WebSocket opened")

    @tornado.gen.coroutine
    def who_am_i(self, spark):
        url = 'https://api.ciscospark.com/v1/people/me'
        result = yield spark.get_with_retries(url)
        self.log.info(result.body.get('displayName'))
        self.log.info(result.body.get('emails',[None])[0])
        self.log.info(result.body.get('orgId'))
        raise tornado.gen.Return((result.body.get('id'), result.body.get('emails',[None])[0], result.body.get('orgId')))

    """
    def who_am_i_std(self, spark):
        url = 'https://api.ciscospark.com/v1/people/me'
        results = [None]
        spark.get_with_retries_std(url, results, 0)
        result = results[0]
        self.log.info(result.body.get('displayName'))
        return result.body.get('id')
    """

    @tornado.gen.coroutine
    def get_from_queue(self, person):
        result = None
        if person.get('queue') is not None:
            if person.get('process') and not person.get('process').is_alive() and person.get('queue').empty():
                person.update({'queue':None})
            else:
                result_list = []
                self.log.info('Getting items from the queue')
                exceptions = 0
                while len(result_list) < 5:
                    try:
                        result_list.append(person.get('queue').get_nowait())
                    except Exception as e:
                        exceptions += 1
                        yield tornado.gen.sleep(0.3)
                        if exceptions > 2:
                            #print("Failed in get_from_queue for get_nowait():{0}".format(e))
                            break
                self.log.info('Got {0} items from the queue'.format(len(result_list)))
                if len(result_list) > 0:
                    result = result_list
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def on_message_coroutine(self, jobj):
        result = None
        if jobj.get('resource') not in [None,""]:
            if jobj.get('token') not in [None,""]:
                self.log.info("Token:{0}".format(jobj.get('token')))
                token = jobj.get('token')
                self.spark = Spark(token)
                if jobj.get('command') == "open":
                    self.personId, self.personEmail, self.personOrgId = yield self.who_am_i(self.spark)
                    person = self.application.settings['resource_workers'].get(self.personId, {})
                    if person.get('process') != None and person.get('process').is_alive():
                        self.running_main = True
                        result = yield self.get_from_queue(person)
                        self.running_main = False
                    if person.get('process') != None and not person.get('process').is_alive():
                        self.log.debug("joining dead proc from new open...")
                        person['process'].join()
                        person.update({"proc":None})
                        self.log.info(self.application.settings['resource_workers'][self.personId])
                elif jobj['resource'] in ['applications', 'attachment/actions/id', 'calls', 'devices', 'events', 'licenses', 'memberships', 'messages', 'messages/direct', 'people', 'people/me', 'places', 'roles', 'rooms', 'rooms/id/meetingInfo', 'teams', 'team/memberships', 'webhooks', 'guest']:
                    person = self.application.settings['resource_workers'].get(self.personId)
                    m_command = None
                    if jobj['command'] == "run":
                        if not self.running[jobj['resource']] and not self.running_main and (person == None or person.get('process') == None or not person['process'].is_alive()):
                            m_command = jobj['resource'] + "_run"
                            self.running.update({jobj['resource']:True})
                            self.running_main = True
                            self.log.info('scheduling and yielding')
                            if jobj['resource'] == "applications":
                                arglist, url_to_add = application_worker_setup(self, jobj)
                            elif jobj['resource'] == "attachment/actions/id":
                                arglist, url_to_add = attachment_actions_worker_setup(jobj)
                            elif jobj['resource'] == "calls":
                                arglist, url_to_add = call_worker_setup(jobj)
                            elif jobj['resource'] == "devices":
                                arglist, url_to_add = devices_worker_setup(jobj)
                            elif jobj['resource'] == "events":
                                arglist, url_to_add = event_worker_setup(jobj)
                            elif jobj['resource'] == "licenses":
                                arglist, url_to_add = licenses_worker_setup(jobj)
                            elif jobj['resource'] == "memberships":
                                arglist, url_to_add = membership_worker_setup(jobj)
                            elif jobj['resource'] == "messages":
                                arglist, url_to_add = message_worker_setup(jobj)
                            elif jobj['resource'] == "messages/direct":
                                arglist, url_to_add = messages_direct_worker_setup(jobj)
                            elif jobj['resource'] == "people":
                                arglist, url_to_add = people_worker_setup(jobj)
                            elif jobj['resource'] == "people/me":
                                arglist, url_to_add = people_me_worker_setup(jobj)
                            elif jobj['resource'] == "places":
                                arglist, url_to_add = places_worker_setup(jobj)
                            elif jobj['resource'] == "roles":
                                arglist, url_to_add = roles_worker_setup(jobj)
                            elif jobj['resource'] == "rooms":
                                arglist, url_to_add = room_worker_setup(jobj)
                            elif jobj['resource'] == "rooms/id/meetingInfo":
                                arglist, url_to_add = room_meetinginfo_worker_setup(jobj)
                            elif jobj['resource'] == "teams":
                                arglist, url_to_add = team_worker_setup(jobj)
                            elif jobj['resource'] == "team/memberships":
                                arglist, url_to_add = team_membership_worker_setup(jobj)
                            elif jobj['resource'] == "webhooks":
                                arglist, url_to_add = webhook_worker_setup(jobj)
                            else:
                                arglist = None
                            if person != None and person.get('process') != None:
                                self.log.debug("joining dead proc from new command...")
                                person['process'].join()
                            q = Queue(10)
                            p = None
                            self.application.settings['resource_workers'].update({self.personId:{"queue":q,"process":p}})
                            rw = ReportWorker(Printer(), self.personId, self.personEmail, self.personOrgId, token)
                            self.log.debug(threading.enumerate())
                            running_report = self.application.settings['reports_db'].has_running_report(self.personId)
                            if running_report != None:
                                self.log.warning("User has existing report running!")
                                self.log.warning(running_report)
                                p = Process(target=rw.report, args=(running_report["jobj"], q))
                                p.daemon = True
                                p.start()
                                msg = "You had a report running previously which failed for an unknown reason. "
                                msg += "We will resume the {0} report from where it left off. ".format(running_report['jobj']['resource'])
                                msg += "To cancel, send the cancel command instead."
                                result = {"resource":running_report['jobj']['resource'], "message":msg}
                            elif jobj.get('method') not in [None, ""]:
                                if jobj['method'] == "GET":
                                    if arglist != None:
                                        p = Process(target=rw.paginate, args=(jobj, arglist, url_to_add, q))
                                        p.daemon = True
                                        p.start()
                                    else:
                                        msg = "HTTP method {0} does not match desired function {1}".format(jobj['method'], jobj['resource'])
                                        result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                                elif jobj['method'] == "DELETE":
                                    p = Process(target=rw.delete, args=(jobj, q))
                                    p.daemon = True
                                    p.start()
                                else:
                                    msg = "Unsupported HTTP method: {0}".format(jobj['method'])
                                    result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                            elif jobj['resource'] == "guest":
                                if jobj.get('function') == "jwt":
                                    p = Process(target=rw.guest, args=(jobj, q))
                                    p.daemon = True
                                    p.start()
                                elif jobj.get('function') == "exchange":
                                    p = Process(target=rw.exchange, args=(jobj, q))
                                    p.daemon = True
                                    p.start()
                                else:
                                    msg = "function for 'guest' resource is invalid."
                                    result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                            else:
                                msg = "HTTP method cannot be empty/null."
                                result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                            #t = threading.Thread(target=report_worker.paginate, args=[jobj, arglist, url_to_add])
                            #t.daemon = True
                            #t.start()
                            if p != None:
                                self.application.settings['resource_workers'][self.personId].update({"process":p})
                            self.log.debug(threading.enumerate())
                            self.running.update({jobj['resource']:False})
                            self.running_main = False
                        else:
                            m_command = jobj['resource'] + "_run_fail"
                            print(self.running[jobj['resource']])
                            print(not self.running[jobj['resource']])
                            print(not self.running_main)
                            print("person:{0}".format(person))
                            if person != None:
                                print("process:{0}".format(person.get('process')))
                                if person.get('process') != None:
                                    print("process is alive:{0}".format(person.get('process').is_alive()))
                                    print(person == None or person.get('process') == None or not person['process'].is_alive())
                            msg = "You will need to wait for the previous command to finish execution before sending another."
                            result = {"resource":jobj['resource'], "message":msg}
                    elif jobj['command'] == "cancel":
                        if not self.running[jobj['resource']] and not self.running_main and (person == None or person.get('process') == None or not person['process'].is_alive()):
                            m_command = jobj['resource'] + "_cancel_fail"
                            msg = "Nothing to cancel"
                            result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                        else:
                            m_command = jobj['resource'] + "_cancel"
                            #resource_worker_obj = self.application.settings['resource_workers'].get(self.personId)
                            if (person != None and person.get('process') != None and person['process'].is_alive()):
                                person['queue'].close()
                                person['process'].terminate()
                                running_report = self.application.settings['reports_db'].has_running_report(self.personId)
                                if running_report != None:
                                    self.application.settings['reports_db'].delete_all_dbs(self.personId)
                                    self.application.settings['reports_db'].delete_running_report(self.personId)
                                self.log.debug("joining dead proc from cancel...")
                                person['process'].join()
                                person.update({"process":None, "queue":None})
                            self.cancel.update({jobj['resource']:True})
                            self.cancel_main = True
                            self.log.info("Cancelled {0} run!".format(jobj['resource']))
                            msg = "Instruction cancelled."
                            result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                            #result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                    else:
                        m_command = jobj['resource'] + "_invalid"
                        msg = "Invalid Command."
                        result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                    if m_command != None and self.personEmail != None:
                        self.application.settings['metrics_db'].insert(self.personEmail, m_command, None)
                else:
                    self.log.info("Unsupported Resource type.")
                    msg = "Unsupported resource type:{0}".format(jobj['resource'])
                    result = {"resource":jobj['resource'], "success":False, "message":msg}
            else:
                msg = "'token' key value must be defined."
                result = {"resource":jobj['resource'], "success":False, "message":msg}
        elif jobj['command'] == "ping":
            #self.log.info("ping received")
            person = self.application.settings['resource_workers'].get(self.personId, {})
            result = yield self.get_from_queue(person)
        else:
            msg = "'resource' key value must be defined."
            result = {"resource":"unknown", "success":False, "message":msg}
        #self.log.info("result:{0}".format(result))
        if result != None:
            #pass
            self.write_message(json.dumps(result))
        #self.log.info('done yielding')
        #raise tornado.gen.Return(None)

    def on_message(self, message):
        self.log.info("WS message in:{}...".format(message[:3000]))
        try:
            jobj = json.loads(message)
            tornado.ioloop.IOLoop.current().spawn_callback(self.on_message_coroutine, jobj)
        except Exception as e:
            #traceback.print_exc()
            self.log.exception(e)
        return None

    def on_close(self):
        self.is_open = False
        self.log.info("WebSocket closed")

    #def on_connection_close(self):
    #    self.is_open = False
    #    self.log.info("WebSocket closed from remote end.")
    #    self.close()

    def check_origin(self, origin):
        self.application.settings['log'].info("origin:{0}".format(origin))
        origin_host = urllib.parse.urlparse(origin)
        if(self.application.settings['my_hostname'] == origin_host.netloc):
            return True
        elif(self.application.settings['my_hostname'] == None):
            #User was already logged in an server restarted:
            return True
        else:
            self.log.info("Origin not valid, denying websocket connection request.")
            return False
