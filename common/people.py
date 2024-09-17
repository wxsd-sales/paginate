from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

class People(object):
    def __init__(self, db_uri, db_name):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]

    def find(self, args, coll):
        return self.db[coll].find(args)

    def find_one(self, args):
        return self.db['people'].find_one(args)

    def cxteam(self):
        return self.db['people'].find({})

    def forward_permission(self, person_email):
        return self.db['people'].find_one({"email": person_email}) != None

    """
    def bonus(self):
        return cls.cx_users + ["rtaylorhanson+admin2@gmail.com"]
    """

    """
    def admins(cls):
        return ["judupree@cisco.com", "masewell@cisco.com", "tahanson@cisco.com"]
        #return ["tahanson@blessedorigin.com"]
    """
