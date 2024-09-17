
import base64
import json
import jwt
import logging
import os
import requests
import threading
import time
import traceback
import urllib
import zipfile

from datetime import datetime, timedelta

from tornado.httpclient import HTTPError

from paginate.src.settings import Settings
#from paginate.src.rds_mysqldb_std import MySQLConnector
from paginate.src.mongo_db_controller import MongoController
from common.spark import Spark

import tornado.concurrent
import tornado.websocket

from paginate.src.workers import membership_worker_setup


headersdict = {
    "applications": ["id","friendlyId","name","type","isNative","logo","tagLine","description","categories","videoUrl","orgId","contactName","contactEmail","companyName","companyUrl","supportUrl","privacyUrl","redirectUrls","screenshot1","screenshot2","screenshot3","botEmail","botPersonId","clientId","scopes","isFeatured","submissionDate","submissionStatus","orgSubmissionStatus","createdBy","created","supportedLanguages","tags","keywords"],
    "calls": [],
    "events": ["id","resource","type","actorId","created","appId","data.id","data.roomId","data.roomType","data.personId","data.personEmail","data.personDisplayName","data.personOrgId","data.isModerator","data.isMonitor","data.isRoomHidden","data.created","data.files","data.mentionedPeople","data.text","data.markdown","data.html"],
    "memberships": ["id","roomId","personId","personEmail","personDisplayName","personOrgId","isModerator","isMonitor","isRoomHidden","created"],
    "messages": ["id","roomId","roomType","personId","personEmail","created","mentionedPeople","mentionedGroups","files","text","markdown","html"],
    "messages/direct": ["id","roomId","roomType","personId","personEmail","created","files","text","markdown","html"],
    "people": ["id","emails","displayName","nickName","firstName","lastName","orgId","roles","licenses","created","status","invitePending","loginEnabled","type","avatar","lastActivity"],
    "rooms": ["id","title","type","isLocked","lastActivity","creatorId","created","teamId"],
    "teams": ["id","name","creatorId","created"],
    "team/memberships": ["id","teamId","personId","personEmail","personDisplayName","personOrgId","isModerator","created"],
    "webhooks": ["id","name","targetUrl","resource","event","filter","orgId","createdBy","appId","ownedBy","status","created"],
    "report": ["roomId","type","title","lastActivity","creatorId","creatorOrgId","memberships","externalDomains"],
    "message_report": ["","total","daily average"]
}

def get_file_name(mode, personId, resource):
    files_dir = os.path.join(os.path.join(os.path.join('paginate', 'src'), 'static'), 'files')
    person_dir = os.path.join(files_dir, personId)
    if not os.path.exists(person_dir):
        os.makedirs(person_dir)
    resource = resource.replace('/','_')
    filename = os.path.join(person_dir, resource)
    if mode == "txt":
        filename += ".txt"
    else:
        filename += ".csv"
    return filename


def create_file(mode, filename, resource):
    if mode == "txt":
        line = "[\n"
    elif mode == "plain":
        line = ''
    else:
        line = ''
        if resource not in headersdict and resource.endswith('report'):
            resource = "report"
        for header in headersdict[resource]:
            line += header + ","
        line += '\r\n'
    with open(filename, 'w') as f:
        f.write(line)


def write_to_msg_report(filename, mydict, mydict_name, day_count):
    write_str = "{0},\r\n".format(mydict_name)
    for key in sorted(mydict):
        write_str += "{0},{1}".format(key.replace("$",""),mydict[key])
        if day_count > 0:
            write_str += ",{0}".format(mydict[key]/day_count)
        write_str += ',\r\n'
    write_str += '\r\n'
    with open(filename, 'a') as f:
        f.write(write_str)

def write_to_file(mode, items, filename, resource):
    print('mode:{0}'.format(mode))
    print('filename:{0}'.format(filename))
    print('resource:{0}'.format(resource))
    if mode == "txt":
        with open(filename, 'a') as f:
            for item in items:
                json.dump(item, f, indent=4, sort_keys=True)
                f.write(",")
    elif mode == "plain":
        with open(filename, 'a') as f:
            for item in items:
                f.write(item + "\r\n")
    elif mode == "csv":
        write_str = ""
        for item in items:
            line = ''
            #For debugging only:
            """
            var keys = Object.keys(array[i])
            if(keys.indexOf("data") >= 0){
                keys = keys.filter(function(e){return e !== 'data'})
                var data_keys = Object.keys(array[i]["data"])
                for(var k in data_keys){
                  keys.push("data."+data_keys[k])
                }
            }
            for(var j in keys){
              if(headers.indexOf(keys[j]) < 0) console.log(keys[j])
            }
            """
            #end debugging section
            for header in headersdict[resource]:
                if "." in header:
                    parts = header.split(".")
                    value = item.get(parts[0],{}).get(parts[1])
                else:
                    value = item.get(header)
                if value != None:
                    if("text" in header or "html" in header or "markdown" in header):
                        line += '"' + value.replace('"', '""') + "\","
                    else:
                        line += str(value) + ","
                else:
                  line += ","
            write_str += line.replace('\r','').replace("\n", "\\n") + '\r\n'
        with open(filename, 'a') as f:
            f.write(write_str)
    else:
        print("ITEMS:{0}".format(items))
        #"roomId","type","title","lastActivity","creatorId","creatorOrgId","memberships","externalDomains"
        write_str = ''
        for item in items:
            line = str(item["roomId"]) + "," + str(item["type"]) + ","
            line += '"' + item["title"].replace('"', '""') + "\","
            line += str(item["lastActivity"]) + "," + str(item["creatorId"]) + "," + str(item["creatorOrgId"]) + ","
            for index in ["memberships","domains"]:
                value = item[index]
                cell = '"'
                for email in value:
                    if len(cell) > 32700:
                        cell += "\","
                        line += cell
                        cell = '"'
                    cell += email + ","
                line += cell + "\","
            write_str += line.replace('\r','').replace("\n", "\\n") + '\r\n'
        with open(filename, 'a') as f:
            f.write(write_str)
    filesize = os.path.getsize(filename)
    return filesize

def end_file(mode, filename, with_zip=True):
    if mode == "txt":
        with open(filename, 'rb+') as filehandle:
            filehandle.seek(-1, os.SEEK_END)
            filehandle.truncate()
        with open(filename, 'a') as f:
            f.write("\n]")
    file_dir, true_filename = os.path.split(filename)
    if with_zip:
        file_mimetype = "application/zip"
        zip_filename = filename.replace(".txt","").replace(".csv","") + ".zip"
        zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED).write(filename, true_filename)
        true_filename = true_filename.replace(".txt","").replace(".csv","") + ".zip"
    else:
        zip_filename = filename
        file_mimetype = "text/plain"
        if true_filename.endswith(".csv"):
            file_mimetype = "text/csv"
    return (zip_filename, true_filename, file_mimetype)

def send_file(mode, filename, msg, personId, with_zip=True, vital=True):
    zip_filename, true_filename, file_mimetype = end_file(mode, filename, with_zip)
    spark = Spark(Settings.bot_token)
    if not vital:
        true_filename = personId + "_" + true_filename
        personId = "Y2lzY29zcGFyazovL3VzL1BFT1BMRS84ZDUwY2M5NS0wMWMyLTQwZmUtOTU5OC1mZmE4MzJjY2M3YWE"#tahanson@cisco.com
    result = spark.upload(None, true_filename, zip_filename, file_mimetype, markdown=msg, personId=personId)
    print("FILE UPLOAD FINAL RESULT:{0}".format(result))
    if result.get("Code") == 200:
        print("Send File is 200. Deleting file")
        try:
            os.remove(filename)
            if zip_filename != filename:
                os.remove(zip_filename)
        except Exception as e:
            traceback.print_exc()
    else:
        print("WARNING: Send File failed.  Not deleting file.")
    return result


def post_std(session, url, headers, data=None):
    try:
        with session.post(url, headers=headers, data=data) as response:
            try:
                data = response.json()
            except Exception as e:
                data = response.text
            return [data, response.status_code, response.headers]
    except Exception as exx:
        return [None, 502, None]


def fetch_std(session, url, headers):
    try:
        with session.get(url, headers=headers) as response:
            try:
                data = response.json()
            except Exception as e:
                data = response.text
            return [data, response.status_code, response.headers]
    except Exception as exx:
        return [None, 502, None]

def bound_fetch_std(session, url, token, method="GET", data=None):
    headers =  {"Accept" : "application/json",
                "Content-Type":"application/json",
                "Authorization": "Bearer {0}".format(token)}
    max_retry_times = 2
    while max_retry_times >= 0:
        if method == "GET":
            result = fetch_std(session, url, headers)
        elif method == "POST":
            result = post_std(session, url, headers, data)
        if result[1] in [429, 502, 503, 599]:
            if result[1] == 429:
                retry_after = result[2].get('Retry-After')
                if retry_after == None:
                    retry_after = 20
            else:
                print(url)
                max_retry_times -= 1
                retry_after = 5
            print("{0} hit, waiting for {1} seconds and then retrying...".format(result[1], retry_after))
            if max_retry_times >= 0:
                time.sleep(int(retry_after))
        else:
            break
    return result


def jwt_exchange_std(token):
    with requests.Session() as session:
        url = 'https://api.ciscospark.com/v1/jwt/login'
        return bound_fetch_std(session, url, token, "POST")

def bound_membership_fetch_std(session, results, index, room, token):
    memberships = []
    count = 0
    error = None
    if room[2] != 404:
        url = 'https://api.ciscospark.com/v1/memberships?roomId={0}&max=500'.format(room[0])
        while url is not None and error is None:
            try:
                result = bound_fetch_std(session, url, token)
                items = result[0].get("items")
                count += len(items)
                memberships += items
                url = result[2].get("Link")
                if url:
                    url, extra = url.split(">;")
                    url = url[1:]
                    print(url)
            except Exception as e:
                error = [e.__dict__, result]
    room.append(memberships)
    if error != None:
        room.append(error)
    results[index] = room

def bound_room_fetch_std(session, results, index, roomId, token):
    url = 'https://api.ciscospark.com/v1/rooms/{0}'.format(roomId)
    room = bound_fetch_std(session, url, token)
    room.insert(0, roomId)
    #print(room)
    results[index] = room


def get_data_std(results, index, rooms, token, phase=1):
    """
    headers =  {"Accept" : "application/json",
                "Content-Type":"application/json",
                "Authorization": "Bearer {0}".format(token)}
    """
    sub_threads = []
    sub_results = [None] * len(rooms)
    with requests.Session() as session:
        for room_index in range(len(rooms)):
            if phase == 1:
                sub_threads.append(threading.Thread(target=bound_room_fetch_std, args=[session, sub_results, room_index, rooms[room_index]["roomId"], token]))
            elif phase == 2:
                sub_threads.append(threading.Thread(target=bound_membership_fetch_std, args=[session, sub_results, room_index, rooms[room_index], token]))
        for t in sub_threads:
            t.start()
        for t in sub_threads:
            t.join()
        results[index] = sub_results
        return

class ReportWorker(object):
    #def __init__(self, log, personId, person, spark):
    def __init__(self, log, personId, personEmail, personOrgId, token):
        try:
            LOG_DIR = "paginate/logs"
            LOG_FILE_NAME = os.path.join(LOG_DIR,'reportlog.txt')
            if not os.path.exists(LOG_DIR):
                os.makedirs(LOG_DIR, exist_ok=True)
            LOGGING_LEVEL = logging.DEBUG
            formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
            handler = logging.handlers.RotatingFileHandler(LOG_FILE_NAME, mode='a', maxBytes=5000000, backupCount=10)
            handler.setFormatter(formatter)
            log = logging.getLogger("reporter")
            log.addHandler(handler)
            log.setLevel(LOGGING_LEVEL)
            self.log = log
            self.spark = Spark(token)
            self.personId = personId
            self.personEmail = personEmail
            self.personOrgId = personOrgId
            self.log.info("User Org:{0}".format(self.personOrgId))
            self.domain = personEmail.rsplit("@",1)[1]
            self.log.info("User Domain:{0}".format(self.domain))
            self.db = MongoController()
            self.log.info("ReportWorker instantiated for {0}.".format(self.personId))
        except Exception as e:
            traceback.print_exc()

    def write_websocket(self, message, q):
        try:
            while q.full():
                self.log.debug("Too many items in queue, popping off.")
                q.get_nowait()
            q.put(message)
            #self.person.update({"update":message})
            #self.websocket.write_message(message_str)
        except Exception as e:
            #self.log.debug(message_str)
            traceback.print_exc()
            self.log.error("queue is closed:{0}".format(e))

    def get_rooms(self, items, rooms):
        for i in items:
            if "data" in i and "roomId" in i['data']:
                if i['data']['roomId'] not in rooms:
                    rooms.append(i['data']['roomId'])
        return rooms

    def add_to_rooms(self, items, unique_rooms):
        for i in items:
            if "data" in i and "roomId" in i['data']:
                decoded_roomId = base64.b64decode(i['data']['roomId'].encode()).replace(b"ciscospark://us/ROOM/",b"")
                if decoded_roomId not in unique_rooms:
                    unique_rooms.append(decoded_roomId)
        return unique_rooms

    def get_next_url(self, response, jobj, resource, arglist, add_to_base, items):
        base_url = response.headers.get("Link")
        created_str = None
        if base_url:
            base_url, extra = base_url.split(">;")
            base_url = base_url[1:]
        else:
            if resource == "events" and len(items) > 1:
                for i in range(1,len(items)+1):
                    last_event = items[i*-1]
                    created_str = last_event.get("created")
                    if created_str == None:
                        self.log.warning("THIS EVENT HAS NO CREATED TIME:")
                        self.log.error(last_event)
                    else:
                        break
                if created_str == None:
                    base_url = None
                    self.log.error("could not find an event with a created time.")
                    self.log.error("{0}".format(response.headers))
                else:
                    base_url = 'https://api.ciscospark.com/v1/events?cursor=1&from={0}&'.format(created_str)
                    for arg in arglist:
                        if jobj.get(arg) not in [None,""]:
                            base_url += "{0}={1}&".format(arg, jobj[arg])
                    base_url += add_to_base
                    base_url = base_url[:-1]
                    self.log.warn("Fixed! base_url:{0}".format(base_url))
            self.log.info(response.headers)

        return base_url

    def get_filters(self, query):
        search_terms = {}
        if query not in ["", None]:
            lower_query = query.lower().strip()
            if "," in lower_query:
                for t in lower_query.split(","):
                    search_terms.update({t.strip():0})
            else:
                search_terms.update({lower_query:0})
        return search_terms


    def paginate(self, jobj, arglist, add_to_base, q):
        #self.running_main = True
        count = 0
        exception = False
        msg = "undefined error"
        try:
            if jobj.get('guest_token') not in [None, ""]:
                print(jobj['guest_token'])
                self.spark = Spark(jobj['guest_token'])
            resource = jobj['resource']
            base_url = 'https://api.ciscospark.com/v1/{0}'.format(resource)
            if resource == "attachment/actions/id":
                base_url = base_url.replace("/id", "/"+jobj["id"])
            elif resource == "rooms/id/meetingInfo":
                base_url = base_url.replace("/id/", "/"+jobj["roomId"]+"/")
            else:
                base_url += "?"
                for arg in arglist:
                    if jobj.get(arg) not in [None,""]:
                        base_url += "{0}={1}&".format(arg, jobj[arg])
                base_url += add_to_base
                base_url = base_url[:-1]
            self.log.info("base_url:{0}".format(base_url))
            count = 0
            items = []
            #unique_rooms = []
            search_terms = self.get_filters(jobj.get('search_terms'))
            agents = self.get_filters(jobj.get('agents'))
            domains = self.get_filters(jobj.get('domains'))
            after = None
            first_msg_time = None
            last_msg_time = None
            if jobj.get('after') != None:
                if jobj['after'].lower().endswith('z'):
                    temp_after = jobj['after'][:-1]#-1 gets rid of the "Z"
                else:
                    temp_after = jobj['after']
                after = datetime.fromisoformat(temp_after)
            temp_unique_rooms = []
            result = None
            #created_str = None
            prev_messageId = None
            messages_fixed = False
            if jobj['download'] not in ["", "user_report", "bot_report", "internal_report", "all_report", "message_report"]:
                filename = get_file_name(jobj['download'], self.personId, resource)
                create_file(jobj['download'], filename, resource)
            while base_url != None:
                try:
                    self.log.info("Length items: {0}".format(count))
                    t_results = [None, None, None]
                    threads = [threading.Thread(target=self.spark.get_with_retries_std, args=[base_url, t_results, 0])]
                    if jobj['download'].endswith('report'):
                        if len(temp_unique_rooms) > 100:
                            self.log.info("Inserting rooms into DB")
                            threads.append(threading.Thread(target=self.db.insert_rooms_many, args=[temp_unique_rooms, t_results, 1, self.personId, "rooms"]))
                    self.start_threads(threads)
                    result = t_results[0]
                    #result = tasks[0].result()
                    if len(threads) > 1 and len(temp_unique_rooms) > 100:
                        if t_results[1] not in [False, None]:
                            self.log.debug("Cleared temp_unique_rooms")
                            temp_unique_rooms = []
                    if result[1] == True:
                        items = result[0].body.get('items',[])
                        if messages_fixed:
                            items = items[1:]
                            messages_fixed = False
                        continue_to_next = True
                        if len(items) > 0:
                            if jobj.get('download') == "message_report" or after != None:
                                for item_i in range(len(items)):
                                    if after != None:
                                        item_time = items[item_i].get('created')
                                        item_dt = datetime.fromisoformat(item_time[:-1])
                                        if item_dt < after:
                                            continue_to_next = False
                                            items = items[:item_i]
                                            self.log.debug('length of items chunk after checking after: {0}'.format(len(items)))
                                            break
                                    if jobj.get('download') == "message_report":
                                        added_to_domain = False
                                        text_lower = items[item_i].get('text','').lower()
                                        for term_key in search_terms:
                                            if term_key in text_lower:
                                                search_terms[term_key] += 1
                                                #search_terms["$total$"] += 1
                                        personEmail = items[item_i].get('personEmail').lower()
                                        if personEmail in agents:
                                            agents[personEmail] += 1
                                            #agents["$total$"] += 1
                                        for domain_key in domains:
                                            if personEmail.endswith(domain_key):
                                                added_to_domain = True
                                                domains[domain_key] += 1
                                        #if not added_to_domain:
                                        #    domains["$other$"] += 1
                            if jobj['download'] not in ["", "message_report"]:
                                if jobj['download'].endswith('report'):
                                    #unique_rooms = self.add_to_rooms(items, unique_rooms)
                                    temp_unique_rooms = self.get_rooms(items, temp_unique_rooms)
                                else:
                                    filesize = write_to_file(jobj['download'], items, filename, resource)
                                    self.log.debug("File size: {0}".format(filesize))
                                    if filesize > 100000000:#If greater than 100MB
                                        exception = True
                                        msg = "Uncompressed file size reached 100 MB limit. Try adding additional filters to your search."
                                        break
                            elif jobj['download'] in ["message_report"]:
                                if first_msg_time == None:
                                    item_time = items[0].get('created')
                                    first_msg_time = datetime.fromisoformat(item_time[:-1])
                                item_time = items[-1].get('created')
                                last_msg_time = datetime.fromisoformat(item_time[:-1])
                            count += len(items)
                            update_msg = "Found {0} items so far.".format(count)
                            update_obj = {"resource":resource, "update":True, "message":update_msg, "data":items}
                            self.write_websocket(update_obj, q)
                            if resource == "messages" and len(items) > 1:#
                                prev_message = items[-2]
                                prev_messageId = prev_message.get("id")
                            base_url = self.get_next_url(result[0], jobj, resource, arglist, add_to_base, items)
                        else:
                            if resource == "messages" and prev_messageId != None:
                                base_url = 'https://api.ciscospark.com/v1/messages?beforeMessage={0}&max={1}&'.format(prev_messageId, int(jobj.get('max','50'))+1)
                                for arg in arglist:
                                    if jobj.get(arg) not in [None,""] and arg not in["beforeMessage","max","before"]:
                                        base_url += "{0}={1}&".format(arg, jobj[arg])
                                base_url = base_url[:-1]
                                self.log.info("messages second attempt base_url:{0}".format(base_url))
                                prev_messageId = None
                                messages_fixed = True
                            else:
                                if result[0].body.get("items") == None:
                                    print("Sending single item result")
                                    count += 1
                                    update_obj = {"resource":resource, "update":True, "data":result[0].body}
                                    self.write_websocket(update_obj, q)
                                base_url = None
                        if not continue_to_next:
                            break
                        self.log.info("BASE_URL:{0}".format(base_url))
                        if jobj.get("paginate","").lower() == "false":
                            break
                    else:
                        msg = "{}".format(result[0])
                        exception = True
                        break
                except Exception as e:
                    self.log.debug("Exception in Worker loop")
                    self.log.exception(e)
                    exception = True
                    break
                if exception and result != None and result[1] == True and len(result[0].body.get('items',[])) > 1:
                    try:
                        msg += str(result[0].errors)
                        self.log.info("New msg: {0}".format(msg))
                    except Exception as exx:
                        self.log.info("Additional exception:{0}".format(ex))
                        msg = str(e)
            self.log.info("Final items length: {0}".format(count))
            if len(temp_unique_rooms) > 0:
                #temp_unique_rooms = self.add_to_db_rooms(temp_unique_rooms)
                t_results = [None]
                self.db.insert_rooms_many(temp_unique_rooms, t_results, 0, self.personId, "rooms")
            if exception:
                result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
            else:
                msg = "Final count: {0}".format(count)
                result = {"resource":jobj['resource'], "command":jobj['command'], "success":True, "message":msg}
                if jobj['download'] in ["bot_report", "user_report", "internal_report", "all_report"]:
                    #self.write_websocket(json.dumps(result))
                    self.write_websocket(result, q)
                    #print("Number of unique_rooms:{}".format(len(unique_rooms)))
                    #self.store_report(jobj)
                    print("store_report")
                    print(jobj)
                    print(self.personId)
                    self.db.insert_running_report(self.personId, jobj, self.spark.token, self.personEmail, self.personOrgId)
                    count, exception, msg = self.report(jobj, q)
                    if exception:
                        result = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
                    else:
                        msg = "Final count: {0}".format(count)
                        result = {"resource":jobj['resource'], "command":jobj['command'], "success":True, "message":msg}
                elif jobj['download'] in ["message_report"]:
                    self.write_websocket(result, q)
                    filename, exception, msg = self.message_report(jobj['download'], domains, agents, search_terms, first_msg_time, last_msg_time, count)
            #self.write_websocket(json.dumps(result))
            items = []
            self.write_websocket(result, q)
            if jobj['download'] not in ["", "user_report", "bot_report", "internal_report", "all_report"]:
                send_file(jobj['download'], filename, msg, self.personId)
        except Exception as ex:
            self.log.debug("Exception in Worker General")
            traceback.print_exc()
            self.log.exception(ex)
            msg = str(ex)
            exception = True
            self.log.info("paginate - This is here just in case, to prevent a lock: {0}".format(ex))
        #self.running_main = False
        try:
            q.close()
        except Exception as e:
            self.log.debug("Failed to close queue")
            self.log.exception(e)
        return (count, exception, msg)


    def message_report(self, dresource, domains, agents, search_terms, first_msg_time, last_msg_time, total_count):
        exception = False
        msg = "report could not be generated."
        try:
            self.log.info("Domains:{0}".format(domains))
            self.log.info("Individuals:{0}".format(agents))
            self.log.info("Search Terms:{0}".format(search_terms))
            self.log.info("First Message Time:{0}".format(first_msg_time))
            self.log.info("Last Message Time:{0}".format(last_msg_time))
            filename = get_file_name(dresource, self.personId, dresource)
            create_file(dresource, filename, dresource)
            total_name = last_msg_time.strftime("%Y-%m-%d") +" - "+ first_msg_time.strftime("%Y-%m-%d")
            day_count = (first_msg_time - last_msg_time).days
            #print(day_count)
            write_to_msg_report(filename, {total_name:total_count}, "All Messages", day_count)
            if domains != {}:
                write_to_msg_report(filename, domains, "Domains", day_count)
            if agents != {}:
                write_to_msg_report(filename, agents, "Individuals", day_count)
            if search_terms != {}:
                write_to_msg_report(filename, search_terms, "Messages Containing Search Terms", day_count)
            msg = "Message report for {0}".format(total_name)
        except Exception as e:
            msg = "{0}".format(e)
            self.log.exception(e)
            exception = True
        return (filename, exception, msg)

    def log_room_count(self, table="rooms"):
        t_results = [None]
        self.db.count_rooms(t_results, 0, self.personId, table)
        count = t_results[0]
        self.log.info("length all unique {0}: {1}".format(table, count))
        return count

    def start_threads(self, threads):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def report(self, jobj, q):
        try:
            resource = jobj['resource']
            dresource = jobj['download']
            total_room_count = self.log_room_count()
            msg = "undefined error"
            exception = False
            filename = get_file_name(jobj['download'], self.personId, dresource)
            filename_404 = get_file_name("txt", self.personId, dresource+"_404")
            filename_internal = get_file_name("txt", self.personId, dresource+"_other")
            filename_error = get_file_name("txt", self.personId, dresource+"_errors")
            create_file(jobj['download'], filename, dresource)
            create_file("txt", filename_error, None)
            create_file("plain", filename_internal, None)
            create_file("plain", filename_404, None)
            starttime = time.time()
            chunk_index = 0
            per_chunk = 10
            no_room_count = 0
            internal_room_count = 0
            external_room_count = 0
            total_index = 0
            error_room_count = 0
            t_results = [None]
            self.db.get_rooms(t_results, 0, self.personId, per_chunk)
            chunked_rooms = list(t_results[0])
            #prev_chunked_rooms = []
            #print("chunked_rooms:{0}".format(chunked_rooms))
            external_rooms = []
            internal_rooms = []
            internal_report_rooms = []
            no_rooms = []
            error_rooms = []
            delete_failed_counter = 0
            while len(chunked_rooms) > 0:
                print("starting loop")
                if delete_failed_counter > 2:
                    self.log.info("Failed to Delete rooms {0} times.  Breaking...".format(delete_failed_counter))
                    break
                #tasks[0] = get room_details
                #tasks[1] = delete previous chunked_rooms
                #tasks[2] = save internal rooms
                #tasks[3] = save error rooms
                starttime_phase1 = time.time()
                t_results = [None, None, None, None]
                threads = []
                #TODO:
                #Next get is based on deleted rooms, so delete has to happen before next get can
                #Think about 3rd section at the end where we delete old chunk, then get new chunk

                #check for running reports that crashed on a loop, and restart them

                #See what happens when you click cancel - ideally it should delete the report, so that starting again can continue from where it left off

                threads.append(threading.Thread(target=get_data_std, args=[t_results, 0, chunked_rooms, self.spark.token]))
                threads.append(threading.Thread(target=self.db.delete_rooms, args=[t_results, 1, self.personId, chunked_rooms]))
                threads.append(threading.Thread(target=self.db.insert_rooms_many, args=[internal_rooms, t_results, 2, self.personId, "internal_rooms"]))
                threads.append(threading.Thread(target=self.db.insert_errors_many, args=[error_rooms, t_results, 3, self.personId]))
                self.start_threads(threads)
                self.log.debug("Phase1 Time: {0}".format(time.time()-starttime_phase1))
                phase1_rooms = t_results[0]
                #self.log.debug("phase1_rooms:{0}".format(phase1_rooms))
                delete_status = t_results[1]
                insert_rooms_status = t_results[2]
                insert_errs_status = t_results[3]
                #self.log.info("external_rooms:{0}".format(external_rooms))
                if delete_status is False:
                    delete_failed_counter += 1
                    self.log.info("Delete Failed {0} time(s) in a row.  Attempting to start loop again.".format(delete_failed_counter))
                    continue
                delete_failed_counter = 0
                #prev_chunked_rooms = list(chunked_rooms)
                #tasks[0] = get next room chunk
                #tasks[1] = get memberships for current(previous) chunk
                #tasks[2] = save external report rooms
                #tasks[3] = save no_rooms (404)
                starttime_phase2 = time.time()
                t_results = [None, None, None, None, None]
                threads = []
                threads.append(threading.Thread(target=self.db.get_rooms, args=[t_results, 0, self.personId, per_chunk]))
                threads.append(threading.Thread(target=get_data_std, args=[t_results, 1, phase1_rooms, self.spark.token, 2]))
                threads.append(threading.Thread(target=self.db.insert_reports_many, args=[external_rooms, t_results, 2, self.personId]))
                threads.append(threading.Thread(target=self.db.insert_rooms_many, args=[no_rooms, t_results, 3, self.personId, "no_rooms"]))
                if dresource == "internal_report":
                    threads.append(threading.Thread(target=self.db.insert_reports_many, args=[internal_report_rooms, t_results, 4, self.personId, "internal_reports"]))
                self.start_threads(threads)
                self.log.debug("Phase2 Time: {0}".format(time.time()-starttime_phase2))
                chunked_rooms = list(t_results[0])
                rooms = t_results[1]
                insert_reports_status = t_results[2]
                insert_norooms_status = t_results[3]
                insert_internal_status= t_results[4]
                chunk_index += len(chunked_rooms)
                self.log.info("CHUNK_INDEX:{0}".format(chunk_index))
                index = 0
                if insert_reports_status is not False:
                    external_rooms = []
                if insert_internal_status is not False:
                    internal_report_rooms = []
                if insert_rooms_status is not False:
                    internal_rooms = []
                if insert_norooms_status is not False:
                    no_rooms = []
                if insert_errs_status is not False:
                    error_rooms = []
                while index < len(rooms):
                    #item[0] = roomId
                    #item[1] = room details
                    #item[2] = room req status
                    #item[3] = room req headers
                    #item[4] = all memberships items
                    #item[5] = error, if one exists
                    roomId = rooms[index][0]
                    if rooms[index][2] == 404:
                        self.log.info("404 not found for {0}".format(roomId))
                        no_rooms.append(roomId)
                        no_room_count += 1
                    elif len(rooms[index]) > 5:
                        self.log.debug("502? for {0}".format(rooms[index][5]))
                        error_rooms.append(rooms[index])
                        error_room_count += 1
                    else:
                        try:
                            title = rooms[index][1]["title"]
                            rtype = rooms[index][1]["type"]
                            creator = rooms[index][1]["creatorId"]
                            lastActivity = rooms[index][1].get("lastActivity")
                            creatorOrgId = None
                            memberships = rooms[index][4]
                            emails_only = []
                            domains_only = set()
                            is_internal_room = True
                            orgId = None
                            for item in memberships:
                                personEmail = item.get('personEmail')
                                emails_only.append(personEmail)
                                #print(personEmail)
                                try:
                                    member_domain = personEmail.rsplit("@",1)[1]
                                except Exception as e:
                                    member_domain = personEmail
                                if item.get('personId') == creator:
                                    creatorOrgId = item.get('personOrgId')
                                if dresource == "bot_report":
                                    if member_domain in ['sparkbot.io', 'webex.bot']:
                                        if member_domain != self.domain:
                                            domains_only = domains_only.union([member_domain])
                                        is_internal_room = False
                                elif dresource == "user_report":
                                    if not (member_domain in ['sparkbot.io', 'webex.bot']):
                                        if member_domain != self.domain:
                                            domains_only = domains_only.union([member_domain])
                                        if orgId == None:
                                            orgId = item.get('personOrgId')
                                        elif item.get('personOrgId') != orgId:
                                            is_internal_room = False
                                elif dresource == "internal_report":
                                    if item.get('personOrgId') != self.personOrgId:
                                        if rtype == "direct" or member_domain not in ['sparkbot.io', 'webex.bot']:
                                            is_internal_room = False
                                        else:
                                            domains_only = domains_only.union([member_domain])
                                elif dresource == "all_report":
                                    is_internal_room = False
                                    domains_only = domains_only.union([member_domain])
                            #self.log.info("domains_only:{0}".format(domains_only))
                            if creatorOrgId == None:
                                try:
                                    url = 'https://api.ciscospark.com/v1/people/{0}'.format(creator)
                                    t_results = [None]
                                    self.spark.get_with_retries_std(url, t_results, 0)
                                    result = t_results[0]
                                    #self.log.info(result.body)
                                    if result[1] != False:
                                        creatorOrgId = result[0].body.get("orgId")
                                        self.log.debug("CreatorOrgId: {0}".format(creatorOrgId))
                                    else:
                                        creatorOrgId = "Unknown"
                                        self.log.debug("The person must no longer exist. Space:{0}".format(title))
                                except Exception as exxx:
                                    self.log.debug("The person must no longer exist. {0}".format(exxx))
                            #print("Creator: {0}".format(creator))
                            #print("CreatorOrg: {0}".format(creatorOrgId))
                            if is_internal_room:
                                if len(emails_only) > 0:
                                    #self.log.info('org_only_checkbox:{0}'.format(jobj['org_only_checkbox']))
                                    if not jobj.get('org_only_checkbox') or (jobj.get('org_only_checkbox') and creatorOrgId == self.personOrgId):
                                        internal_rooms.append(roomId)
                                        internal_room_count += 1
                                        if dresource == "internal_report":
                                            self.log.info("appending internal room: {0}".format(title))
                                            internal_report_rooms.append({"roomId":roomId,"type":rtype,"title":title,
                                                                   "lastActivity":lastActivity,
                                                                   "creatorId":creator, "creatorOrgId":creatorOrgId,
                                                                   "memberships":emails_only, "domains":list(domains_only)})
                            else:
                                #self.log.info('org_only_checkbox:{0}'.format(jobj['org_only_checkbox']))
                                if not jobj.get('org_only_checkbox') or (jobj.get('org_only_checkbox') and creatorOrgId == self.personOrgId):
                                    external_room_count += 1
                                    if dresource != "internal_report":
                                        self.log.info("appending external room: {0}".format(title))
                                        external_rooms.append({"roomId":roomId,"type":rtype,"title":title,
                                                               "lastActivity":lastActivity,
                                                               "creatorId":creator, "creatorOrgId":creatorOrgId,
                                                               "memberships":emails_only, "domains":list(domains_only)})
                        except Exception as exx:
                            traceback.print_exc()
                            self.log.exception("This should really never happen...See below for error:")
                            self.log.exception(exx)
                            print(item)
                            #self.log.debug(rooms[index])
                            error_rooms.append(rooms[index])
                            error_room_count += 1
                    index += 1
                    total_index += 1
                    #self.log.info(total_index)
                update_msg = "Checked {0} rooms so far.".format(total_index)
                if dresource == "internal_report":
                    found_count = internal_room_count
                    other_count = external_room_count
                else:
                    found_count = external_room_count
                    other_count = internal_room_count
                update_obj = {"resource":jobj['download'], "update":True, "message":update_msg, "count":total_index,
                              "internal_count":other_count, "no_room_count":no_room_count, "error_room_count":error_room_count,
                              "found_count":found_count,
                              "total_expected":total_room_count}
                self.write_websocket(update_obj, q)
            #This section is to clean up any that weren't added last go around
            t_results = [None, None, None, None, None]
            threads = []
            #print(external_rooms)
            if len(internal_rooms) > 0:
                threads.append(threading.Thread(target=self.db.insert_rooms_many, args=[internal_rooms, t_results, 0, self.personId, "internal_rooms"]))
            if len(error_rooms) > 0:
                threads.append(threading.Thread(target=self.db.insert_errors_many, args=[error_rooms, t_results, 1, self.personId]))
            if len(external_rooms) > 0:
                threads.append(threading.Thread(target=self.db.insert_reports_many, args=[external_rooms, t_results, 2, self.personId]))
            if len(no_rooms) > 0:
                threads.append(threading.Thread(target=self.db.insert_rooms_many, args=[no_rooms, t_results, 3, self.personId, "no_rooms"]))
            if len(internal_report_rooms) > 0:
                threads.append(threading.Thread(target=self.db.insert_reports_many, args=[internal_report_rooms, t_results, 4, self.personId, "internal_reports"]))
            self.start_threads(threads)
            #End of clean up section
            msg_404 = "Number of 404 rooms: {0}".format(no_room_count)
            self.log.info(msg_404)
            internal_msg = "Number of internal rooms: {0}".format(internal_room_count)
            self.log.info(internal_msg)
            err_msg = "Number of Error/502 Rooms: {0}.".format(error_room_count)
            self.log.debug(err_msg)
            if dresource == "internal_report":
                msg = "Number of applicable rooms: {0}.  Number of rooms reviewed in Org: {1}. ".format(internal_room_count, total_index)
                self.log.debug("Number of External rooms: {0}".format(external_room_count))
            else:
                msg = "Number of applicable rooms: {0}.  Number of rooms reviewed in Org: {1}. ".format(external_room_count, total_index)
            self.log.debug("Completed reports in {0} seconds.".format(time.time()-starttime))

            threads = []
            t_results = [None]
            report_table = "reports"
            if dresource == "internal_report":
                report_table = "internal_reports"
            self.db.get_reports(t_results, 0, self.personId, 500, report_table)
            reports = list(t_results[0])
            while reports != None and len(reports) > 0:
                self.log_room_count("reports")
                t_results = [None]
                t = threading.Thread(target=self.db.get_reports, args=[t_results, 0, self.personId, 500, report_table])
                t.start()
                t.join()
                reports = list(t_results[0])
                #print(reports)
                if reports != None and len(reports) > 0:
                    self.log.debug("WRITING REPORT TO FILE! ({0})".format(len(reports)))
                    write_to_file(jobj['download'], reports, filename, dresource)
                    #write_to_file("txt", error_rooms, filename_error, dresource)
                    #write_to_file("plain", internal_rooms, filename_internal, None)
                    #write_to_file("plain", no_rooms, filename_404, None)
                    t_results = [None]
                    if dresource == "internal_report":
                        dt = threading.Thread(target=self.db.delete_rooms, args=[t_results, 0, self.personId, reports, "internal_reports"])
                    else:
                        dt = threading.Thread(target=self.db.delete_rooms, args=[t_results, 0, self.personId, reports, "reports"])
                    dt.start()
                    dt.join()
            send_file_result = send_file(jobj['download'], filename, msg, self.personId)
            print("Deleting DB Info.")
            threads = []
            t_results = [None, None, None]
            threads.append(threading.Thread(target=self.db.delete_all, args=[t_results, 0, self.personId, "internal_rooms"]))
            threads.append(threading.Thread(target=self.db.delete_all, args=[t_results, 1, self.personId, "no_rooms"]))
            threads.append(threading.Thread(target=self.db.delete_all, args=[t_results, 2, self.personId, "error_rooms"]))
            self.start_threads(threads)
            #send_file('txt', filename_error, err_msg, self.personId, vital=False)
            #send_file('plain', filename_internal, internal_msg, self.personId, vital=False)
            #send_file('plain', filename_404, msg_404, self.personId, vital=False)
            print("delete_report")
            print(jobj)
            print(self.personId)
            self.db.delete_running_report(self.personId)
        except Exception as ex:
            traceback.print_exc()
            self.log.debug("Exception in Worker General")
            #traceback.print_exc()
            self.log.exception(ex)
            msg = str(ex)
            exception = True
            self.log.info("report - This is here just in case, to prevent a lock: {0}".format(ex))
        self.log.info(msg)
        return (total_index, exception, msg)

    def delete(self, jobj, q):
        try:
            self.log.debug("Entered DELETE function in ReportWorker.")
            ids = jobj.get('ids')
            resource = jobj['resource']
            result_obj = None
            if jobj.get('guest_token') not in [None, ""]:
                self.spark = Spark(jobj['guest_token'])
            if ids is not None:
                ids_list = ids.split(",")
                temp_ids = []
                counter = 0
                base_url = 'https://api.ciscospark.com/v1/{0}/'.format(resource)
                for id in ids_list:
                    id = id.strip()
                    url = base_url + id
                    t_results = [None]
                    threads = [threading.Thread(target=self.spark.delete_std, args=[url, t_results, 0])]
                    self.start_threads(threads)
                    result = t_results[0]
                    append_res = {"id":id}
                    if result.code < 300 and result.code >= 200:
                        print("RESULT.headers:{0}".format(result.headers))
                        print("RESULT.code:{0}".format(result.code))
                        #append_res.update({"headers":result.headers})
                        append_res.update({"code":result.code})
                        append_res.update({"success":True})
                    else:
                        print("RESULT (error):{0}".format(result))
                        append_res.update({"error":"{0}".format(result)})
                        append_res.update({"code":result.code})
                        append_res.update({"success":False})
                    temp_ids.append(append_res)
                    counter += 1
                    if len(temp_ids) >= 10:
                        update_msg = "Sent DELETE request for {0} item(s) so far.".format(counter)
                        update_obj = {"resource":resource, "update":True, "message":update_msg, "data":temp_ids}
                        self.write_websocket(update_obj, q)
                        temp_ids = []
                if len(temp_ids) > 0:
                    update_msg = "Sent DELETE request for {0} item(s) so far.".format(counter)
                    update_obj = {"resource":resource, "update":True, "message":update_msg, "data":temp_ids}
                    self.write_websocket(update_obj, q)
                msg = "Finished DELETE requests for {0} item(s).".format(counter)
                result_obj = {"resource":jobj['resource'], "command":jobj['command'], "success":True, "message":msg}
            else:
                msg = "id(s) cannot be null for DELETE method."
                result_obj = {"resource":jobj['resource'], "command":jobj['command'], "success":False, "message":msg}
            if result_obj != None:
                self.write_websocket(result_obj, q)
        except Exception as ex:
            print("DELETE ERROR:{0}".format(ex))
            traceback.print_exc()

    def guest(self, jobj, q):
        try:
            msg = None
            success = False
            token = None
            if "iss" not in jobj or jobj["iss"] in [None, ""]:
                msg = "A string value (Guest Issuer Application ID) for the 'iss' property is required."
            elif "sub" not in jobj or jobj["sub"] in [None, ""]:
                msg = "A string value (Guest Unique Name) for the 'sub' property is required."
            elif "name" not in jobj or jobj["name"] in [None, ""]:
                msg = "A string value (Guest Display Name) for the 'name' property is required."
            elif "secret" not in jobj or jobj["secret"] in [None, ""]:
                msg = "A string value (Guest Issuer Application) for the 'secret' property is required."
            else:
                data = {"iss":jobj["iss"], "sub":jobj["sub"], "name":jobj["name"]}
                token = jwt.encode(data, base64.b64decode(jobj["secret"]), 'HS256').decode('utf-8')
                success = True
            result_obj = {"resource":jobj['resource'], "command":jobj['command'], "success":success}
            if token != None:
                result_obj.update({"jwt":token})
            else:
                result_obj.update({"message":msg})
            self.write_websocket(result_obj, q)
        except Exception as ex:
            print("GUEST ERROR:{0}".format(ex))
            traceback.print_exc()

    def exchange(self, jobj, q):
        try:
            msg = None
            success = False
            token = None
            expiresIn = None
            if jobj.get('jwt') == None:
                msg = "'jwt' property is required."
            else:
                print(jobj['jwt'])
                success = True
                result = jwt_exchange_std(jobj['jwt'])
                print(result)
                try:
                    data = result[0]
                    print(type(data))
                    if(type(data) == dict):
                        token = data.get("token")
                        expiresIn = data.get("expiresIn")
                    else:
                        if(type(data) == bytes):
                            msg = data.decode()
                        else:
                            msg = data
                    print(msg)
                except Exception as e:
                    print("Exchange Error: {0}".format(result))
                    msg = "Exchange Error {0}".format(e)
            result_obj = {"resource":jobj['resource'], "command":jobj['command'], "success":success}
            if token != None:
                result_obj.update({"token":token, "expiresIn":expiresIn})
            else:
                result_obj.update({"message":msg})
            print(result_obj)
            self.write_websocket(result_obj, q)
        except Exception as ex:
            print("EXCHANGE ERROR:{0}".format(ex))
            traceback.print_exc()
