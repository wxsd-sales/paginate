import os

class Settings(object):
    mongo_db = os.environ['PAGINATEBOT_MONGO_DB_URI']
    db_name = os.environ['PAGINATEBOT_MONGO_DB_NAME']
    port = int(os.environ['MY_PAGINATE_PORT'])
    auth_uri = os.environ['MY_AUTH_URI']
    client_id = os.environ['MY_CLIENT_ID']
    client_secret = os.environ['MY_CLIENT_SECRET']
    redirect_uri = os.environ['MY_REDIRECT_URI']
    secret = os.environ['MY_COOKIE_SECRET']
    socket_type = os.environ['MY_WSOCKET_TYPE']
    bot_token = os.environ['MY_BOT_TOKEN']
    #db_hostname = os.environ['MY_DB_HOSTNAME']
    #db_name = os.environ['MY_DB_NAME']
    #db_user = os.environ['MY_DB_USERNAME']
    #db_password = os.environ['MY_DB_PASSWORD']
    #ca_path = os.environ['MY_DB_CA_PATH']
    save_logs = os.environ['SAVE_LOGS_BOOL']
    admins = os.environ['MY_PAGINATE_ADMINS'].split(",")

class Printer(object):
    def __init__(self):
        pass

    def info(self, msg):
        print(msg)

    def debug(self, msg):
        print(msg)

    def error(self, msg):
        print(msg)

    def exception(self, msg):
        print(msg)

    def warning(self, msg):
        print(msg)
