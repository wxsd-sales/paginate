import json

from datetime import datetime
from pymongo import MongoClient, DESCENDING

from pymongo.errors import DuplicateKeyError

m = MongoClient('mongodb+srv://metrics:JzBA3uIEvXww5U8x15rgYtygbVZ@cluster0.gsunn.mongodb.net/points?retryWrites=true&w=majority')
#m = MongoClient('mongodb+srv://taylortest:2TesB80VVFJR33kn@cluster0.xrjhc.mongodb.net/metrics?retryWrites=true&w=majority')
mdb = m['metrics']
#mdb['metrics'].create_index([("time_stamp", DESCENDING)])


def transfer_metrics():
    lines = []
    with open('/Users/tahanson/Documents/metrics7.csv', 'rb') as f:
        all = f.read()
    lines = all.split(b'\r\n')
    print(len(lines))
    counter = 1
    for line in lines[1:]:
        print(line)
        line = line.decode('latin-1')
        print(line)
        item = line.split(",", 5)
        print(item)
        if len(item) > 1:
            document = {
                "botId": int(item[0].replace('"','')),
                "personEmail": item[1].replace('"',''),
                "domainId": int(item[2].replace('"','')),
                "time_stamp": datetime.strptime(item[3].replace('"',''), '%Y-%m-%d %H:%M:%S'),
                "command": item[4].replace('"',''),
                "query": item[5].replace('"',''),
            }
            print(document)
            mdb['metrics'].insert_one(document)
            print("inserted metric {0}".format(counter))
            counter += 1


def transfer_bots():
    lines = []
    with open('/Users/tahanson/Documents/bots2.json') as f:
        all = f.read()
    lines = json.loads(all)
    print(len(lines))
    counter = 1
    for item in lines:
        print(item)
        document = {}
        for key in item:
            value = item[key]
            if value == "":
                value = None
            document.update({key:value})
        print(document)
        mdb['bots'].insert_one(document)
        print("inserted bot {0}".format(counter))
        counter += 1

def transfer_domains():
    lines = []
    with open('/Users/tahanson/Documents/domains.json') as f:
        all = f.read()
    lines = json.loads(all)
    print(len(lines))
    counter = 1
    for item in lines:
        print(item)
        document = {}
        for key in item:
            value = item[key]
            if value == "":
                value = None
            document.update({key:value})
        print(document)
        mdb['domains'].insert_one(document)
        print("inserted domain {0}".format(counter))
        counter += 1

transfer_bots()
transfer_domains()
transfer_metrics()
