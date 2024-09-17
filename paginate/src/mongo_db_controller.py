import copy
import re
import traceback

from pymongo import MongoClient, ReturnDocument, ASCENDING
from pymongo.errors import DuplicateKeyError, BulkWriteError

from datetime import datetime, timedelta

try:
    from paginate.src.settings import Settings
except Exception as e:
    from settings import Settings


class MongoController(object):
    def __init__(self):
        self.client = MongoClient(Settings.mongo_db)
        self.db = self.client[Settings.db_name]

    def get_db(self):
        client = MongoClient(Settings.mongo_db)
        return client[Settings.db_name]

    def count(self, coll_name, query={}):
        db = self.get_db()
        return db[coll_name].count_documents(query)

    def find(self, args, coll_name):
        return self.db[coll_name].find(args)

    def find_one(self, args, coll_name):
        return self.db[coll_name].find_one(args)


    def delete_all(self, results, index, personId, table="rooms"):
        db = self.get_db()
        deleted_count = 0
        try:
            x = db[table].delete_many({"personId":personId})
            deleted_count = x.deleted_count
            results[index] = True
            return
        except Exception as e:
            traceback.print_exc()
        results[index] = False

    def delete_rooms(self, results, index, personId, rooms, table="rooms"):
        db = self.get_db()
        data = []
        for room in rooms:
            data.append({"personId":personId, "roomId":room["roomId"]})
        if len(data) > 0:
            try:
                x = db[table].delete_many({"$or":data})
                deleted_count = x.deleted_count
                results[index] = True
                return
            except Exception as e:
                traceback.print_exc()
            results[index] = False

    def get_rooms(self, results, index, personId, limit=10, table="rooms"):
        db = self.get_db()
        try:
            r = db[table].find({"personId":personId}, limit=limit)
            results[index] = r
            return
        except Exception as e:
            traceback.print_exc()
        results[index] = []#DB may be down for some reason, no point in continuing

    def get_reports(self, results, index, personId, limit=100, table="reports"):
        db = self.get_db()
        try:
            r = db[table].find({"personId":personId}, limit=limit)
            results[index] = r
            return
        except Exception as e:
            traceback.print_exc()
        results[index] = []#DB may be down for some reason, no point in continuing

    def count_rooms(self, results, index, personId, table="rooms"):
        try:
            r = self.count(table, {"personId":personId})
            results[index] = r
            return
        except Exception as e:
            traceback.print_exc()
        results[index] = -1

    def insert_reports_many(self, current_rooms, results, index, personId, table="reports"):
        """
        {"roomId":roomId,"type":rtype,"title":title,
        "lastActivity":lastActivity, "creatorOrgId":creatorOrgId,
        "memberships":emails_only}
        """
        #TODO, check old rds_mysqldb_std lib for insert/ignore and create indexes?
        db = self.get_db()
        data = []
        for room in current_rooms:
            room.update({"personId":personId})
            data.append(room)
        if len(data) > 0:
            try:
                x = db[table].insert_many(data, ordered=False)
                results[index] = True
                return
            except BulkWriteError as be:
                pass
            except Exception as e:
                traceback.print_exc()
            results[index] = False

    def insert_rooms_many(self, rooms, results, index, personId, table="rooms"):
        db = self.get_db()
        data = []
        for room in rooms:
            data.append({"roomId":room, "personId":personId})
        if len(data) > 0:
            try:
                x = db[table].insert_many(data, ordered=False)
                results[index] = True
                return
            except BulkWriteError as be:
                pass
            except Exception as e:
                traceback.print_exc()
            results[index] = False

    def insert_errors_many(self, error_rooms, results, index, personId):
        db = self.get_db()
        data = []
        for error in error_rooms:
            data.append({"roomId":error[0], "personId":personId, "error":error})
        if len(data) > 0:
            try:
                x = db["error_rooms"].insert_many(data, ordered=False)
                results[index] = True
                return
            except BulkWriteError as be:
                pass
            except Exception as e:
                traceback.print_exc()
            results[index] = False

    def get_running_reports(self):
        db = self.get_db()
        r = []
        try:
            r = db["running_reports"].find({})
        except Exception as e:
            traceback.print_exc()
        return r

    def has_running_report(self, personId):
        db = self.get_db()
        r = None
        try:
            r = db["running_reports"].find_one({"personId":personId})
        except Exception as e:
            traceback.print_exc()
        return r

    def insert_running_report(self, personId, jobj, token, personEmail, personOrgId):
        db = self.get_db()
        result = False
        try:
            x = db["running_reports"].insert_one({"personId":personId, "jobj":jobj, "token":token, "personEmail":personEmail, "personOrgId":personOrgId})
            result = True
        except Exception as e:
            traceback.print_exc()
        return result

    def delete_running_report(self, personId):
        db = self.get_db()
        result = False
        try:
            x = db["running_reports"].delete_one({"personId":personId})
            result = True
        except Exception as e:
            traceback.print_exc()
        return result

    def delete_all_dbs(self, personId):
        db = self.get_db()
        result = False
        try:
            db["error_rooms"].delete_many({"personId":personId})
            db["internal_reports"].delete_many({"personId":personId})
            db["internal_rooms"].delete_many({"personId":personId})
            db["no_rooms"].delete_many({"personId":personId})
            db["reports"].delete_many({"personId":personId})
            db["rooms"].delete_many({"personId":personId})
            result = True
        except Exception as e:
            traceback.print_exc()
        return result


if __name__ == "__main__":
    m = MongoController()
    #m.print_search("drake")
    m.db["internal_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["internal_reports"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["error_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["no_rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["reports"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["rooms"].create_index([("roomId", ASCENDING),("personId", ASCENDING)], unique=True)
    m.db["people"].create_index([("personId", ASCENDING)], unique=True)
    m.db["running_reports"].create_index([("personId", ASCENDING)], unique=True)
    #m.print_search("y u no")
    #print(m.find_one({'room_id': 'Y2lzY29zcGFyazovL3VzL1JPT00vZmQ0NDM3MTAtNjlmZC0xMWVhLTkzMzktMWI2MDQwYjkyZTAz'}, 'recents'))
    #print(m.find_one({'room_id': 'Y2lzY29zcGFyazovL3VzL1JPT00vZmQ0NDM3MTAtNjlmZC0xMWVhLTkzMzktMWI2MDQwYjkyZTAz'}, 'recents'))
