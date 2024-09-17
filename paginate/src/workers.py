from concurrent.futures import Future

import traceback
import urllib

import tornado.concurrent


def application_worker_setup(websocket, jobj):
    arglist = ["botEmail", "createdBy", "orgId", "type", "max",
               "submissionStatus", "orgSubmissionStatus"]
    url_to_add = "enableMarketplaceCode=true&enableApplicationsV2=true&"
    if jobj.get("createdByEmail") not in [None,""]:
        websocket.log.info(jobj["createdByEmail"])
        person_url = 'https://api.ciscospark.com/v1/people?email={0}'.format(urllib.parse.quote(jobj["createdByEmail"]))
        future = Future()
        tornado.ioloop.IOLoop.instance().add_callback(
            lambda: tornado.concurrent.chain_future(websocket.spark.get(person_url), future)
        )
        response = future.result()
        websocket.log.info(response.body)
        person = response.body.get('items',[None])[0]
        websocket.log.info("person:{0}".format(person))
        url_to_add += "createdBy={0}&".format(person["id"])
    #https://api.ciscospark.com/v1/applications?enableMarketplaceCode=true&enableApplicationsV2=true&max=10000
    #https://api.ciscospark.com/v1/applications?max=10&enableMarketplaceCode=true&enableApplicationsV2=true
    return arglist, url_to_add

def attachment_actions_worker_setup(jobj):
    arglist = ["id"]
    url_to_add = ""
    return arglist, url_to_add

def call_worker_setup(jobj):
    arglist = ["status", "roomId", "isHost", "to", "from", "max"]
    url_to_add = ""
    return arglist, url_to_add

def devices_worker_setup(jobj):
    arglist = ["personId", "placeId", "orgId", "product", "tag", "connectionStatus", "serial", "software", "upgradeChannel", "errorCode", "capability", "permission", "start", "max"]
    url_to_add = ""
    return arglist, url_to_add

def event_worker_setup(jobj):
    arglist = ["type", "actorId", "to", "from", "max"]
    url_to_add = ""
    if jobj.get("events_resource") not in [None,""]:
        url_to_add += "resource={0}&".format(jobj["events_resource"])
    return arglist, url_to_add

def licenses_worker_setup(jobj):
    arglist = ["orgId"]
    url_to_add = ""
    return arglist, url_to_add

def membership_worker_setup(jobj):
    arglist = ["roomId", "personId", "personEmail", "max"]
    url_to_add = ""
    return arglist, url_to_add

def message_worker_setup(jobj):
    arglist = ["roomId", "mentionedPeople", "before", "beforeMessage", "max"]
    url_to_add = ""
    return arglist, url_to_add

def messages_direct_worker_setup(jobj):
    arglist = ["personId", "personEmail"]
    url_to_add = ""
    return arglist, url_to_add

def people_worker_setup(jobj):
    arglist = ["email", "displayName", "orgId", "max"]
    url_to_add = ""
    return arglist, url_to_add

def people_me_worker_setup(jobj):
    arglist = []
    url_to_add = ""
    return arglist, url_to_add

def places_worker_setup(jobj):
    arglist = ["displayName", "orgId", "max"]
    url_to_add = ""
    return arglist, url_to_add

def roles_worker_setup(jobj):
    arglist = []
    url_to_add = ""
    return arglist, url_to_add

def room_worker_setup(jobj):
    arglist = ["teamId", "type", "sortBy", "max"]
    url_to_add = ""
    return arglist, url_to_add


def room_meetinginfo_worker_setup(jobj):
    arglist = ["roomId"]
    url_to_add = ""
    return arglist, url_to_add

def team_worker_setup(jobj):
    arglist = ["max"]
    url_to_add = ""
    return arglist, url_to_add

def team_membership_worker_setup(jobj):
    arglist = ["teamId", "max"]
    url_to_add = ""
    return arglist, url_to_add

def webhook_worker_setup(jobj):
    arglist = ["max"]
    url_to_add = ""
    return arglist, url_to_add
