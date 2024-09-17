#from concurrent.futures import Future

#import json
#import traceback
#import urllib

#import tornado.concurrent
#import tornado.websocket

def event_worker_setup(jobj):
    arglist = ["type", "actorId", "to", "from", "max"]
    url_to_add = ""
    if jobj.get("events_resource") not in [None,""]:
        url_to_add += "resource={0}&".format(jobj["events_resource"])
    return arglist, url_to_add

"""
def event_worker(websocket, jobj):
    msg = "undefined error"
    base_url = 'https://api.ciscospark.com/v1/events'
    count = 0
    exception = False
    try:
        if jobj.get('id') not in [None,""]:
            base_url += "/" + jobj.get('id')
            future = Future()
            tornado.ioloop.IOLoop.instance().add_callback(
                lambda: tornado.concurrent.chain_future(websocket.spark.get(base_url), future)
            )
            event = future.result()
            items = [event.body]
            count = len(items)
            update_msg = "Found {0} items so far.".format(count)
            update_obj = {"resource":"events", "update":True, "message":update_msg, "data":items}
            websocket.write_message(json.dumps(update_obj))
            print(items)
        else:
            base_url += '?'
            if jobj.get("events_resource") not in [None,""]:
                base_url += "resource={0}&".format(jobj["events_resource"])
            if jobj.get("type") not in [None,""]:
                base_url += "type={0}&".format(jobj["type"])
            if jobj.get("actorId") not in [None,""] and type(jobj["actorId"]) == str:
                base_url += "actorId={0}&".format(jobj["actorId"])
            if jobj.get("to") not in [None,""] and type(jobj["to"]) == str:
                base_url += "to={0}&".format(jobj["to"])
            if jobj.get("from") not in [None,""] and type(jobj["from"]) == str:
                base_url += "from={0}&".format(jobj["from"])
            if jobj.get("max") not in [None,""] and type(jobj["max"]) == str:
                base_url += "max={0}&".format(jobj["max"])
            base_url = base_url[:-1]
            print("base_url:{0}".format(base_url))
            count = 0
            items = []
            result = None
            while base_url != None and not websocket.events_cancel:
                try:
                    print("Length items: {0}".format(count))
                    future = Future()
                    tornado.ioloop.IOLoop.instance().add_callback(
                        lambda: tornado.concurrent.chain_future(websocket.spark.get(base_url), future)
                    )
                    result = future.result()
                    items = result.body.get('items',[])
                    count += len(items)
                    update_msg = "Found {0} items so far.".format(count)
                    update_obj = {"resource":"events", "update":True, "message":update_msg, "data":items}
                    websocket.write_message(json.dumps(update_obj))
                    base_url = result.headers.get("Link")
                    if base_url:
                        base_url, extra = base_url.split(">;")
                        base_url = base_url[1:]
                    print(base_url)
                    if jobj.get("paginate","").lower() == "false":
                        break
                except Exception as e:
                    traceback.print_exc()
                    if result != None and len(result) > 1:
                        try:
                            msg = str(result.errors)
                            print("New msg: {0}".format(msg))
                        except Exception as exx:
                            print("Additional exception:{0}".format(ex))
                            msg = str(e)
                    exception = True
                    break
            if websocket.events_cancel:
                msg = "Instruction cancelled."
                exception = True
            websocket.events_cancel = False
    except Exception as ex:
        traceback.print_exc()
        msg = str(ex)
        exception = True
        print("This is here just in case, to prevent a lock: {0}".format(ex))
    print("Final items length: {0}".format(count))
    return (count, exception, msg)
"""
