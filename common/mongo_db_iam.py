import base64
import os

from Crypto.Util.Padding import pad, unpad
from Crypto.Cipher import AES
from pymongo import MongoClient, ReturnDocument

try:
    from common.iam_settings import IAMSettings
except Exception as e:
    from iam_settings import IAMSettings

class IAMKeysMongoController(object):
    def __init__(self, key_name):
        self.db_client = MongoClient(IAMSettings.mongo_db)
        self.db = self.db_client[IAMSettings.db_name]
        self.keys = self.db["keys"]
        self.key = None
        self.secret = None
        self.set_key(key_name)

    def decrypt(self, encrypted_value):
        encrypted_value = base64.b64decode(encrypted_value)
        aes_obj = AES.new(IAMSettings.crypto_key, AES.MODE_CBC, IAMSettings.crypto_iv)
        result = aes_obj.decrypt(encrypted_value)
        unpadded_result = unpad(result, AES.block_size, style='pkcs7').decode('utf-8')
        return unpadded_result

    def encrypt(self, value):
        aes_obj = AES.new(IAMSettings.crypto_key, AES.MODE_CBC, IAMSettings.crypto_iv)
        padded_data = pad(value.encode('utf-8'), AES.block_size, style='pkcs7')
        result = aes_obj.encrypt(padded_data)
        result = base64.b64encode(result)
        return result

    def set_key(self, key_name):
        mykey = self.find_one({"name":key_name})
        key = mykey.get('key')
        secret = mykey.get('secret')
        if key != None:
            key = self.decrypt(key)
            print(key)
            os.environ["AWS_ACCESS_KEY_ID"] = key
            self.key = key
        else:
            print('Key not found in DB, based on preloaded env variable.')
            self.key = os.environ["AWS_ACCESS_KEY_ID"]
        if secret != None:
            secret = self.decrypt(secret)
            print(secret)
            os.environ["AWS_SECRET_ACCESS_KEY"] = secret
            self.secret = secret
        else:
            print('Secret not found in DB, based on preloaded env variable.')
            self.secret = os.environ["AWS_SECRET_ACCESS_KEY"]
        print("IAMKeysMongoController.set_key AWS CLI KEY/SECRET SET")
        return key, secret

    def find_all(self):
        ret_dict = {}
        for i in self.keys.find({}):
            ret_dict.update({i['name']:i})
        return ret_dict

    def find_one(self, args):
        return self.keys.find_one(args)

    def update_key(self, name, key, secret):
        query = {"name":name}
        update = {"$set" : { "key" : self.encrypt(key),
                             "secret" : self.encrypt(secret)} }
        result = self.keys.find_one_and_update(query, update, return_document=ReturnDocument.AFTER)
        return result
