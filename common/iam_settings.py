import os

class IAMSettings(object):
    mongo_db = os.environ.get('MY_IAM_KEYS_MONGO_URI')
    db_name = os.environ.get('MY_IAM_KEYS_MONGO_DB')
    crypto_key = os.environ["MY_IAM_CRYPTO_KEY"].encode('utf-8')
    crypto_iv = os.environ["MY_IAM_CRYPTO_IV"].encode('utf-8')
