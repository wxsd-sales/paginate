import json
import traceback
import urllib.parse

import tornado.gen
import tornado.web

from paginate.src.settings import Settings
from paginate.src.basehandler import BaseHandler
#from common.spark import Spark

from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

class CodeHandler(BaseHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        self.printf('CodeHandler')
        code = self.get_argument('code')
        self.printf('code:{0}'.format(code))
        self.printf(Settings.redirect_uri)
        if code != None:
            url = "https://api.ciscospark.com/v1/access_token"
            payload = "client_id={0}&".format(Settings.client_id)
            payload += "client_secret={0}&".format(Settings.client_secret)
            payload += "grant_type=authorization_code&"
            payload += "code={0}&".format(code)
            payload += "redirect_uri={0}".format(Settings.redirect_uri)
            headers = {
                'cache-control': "no-cache",
                'content-type': "application/x-www-form-urlencoded"
                }
            request = HTTPRequest(url, method="POST", headers=headers, body=payload)
            http_client = AsyncHTTPClient()
            try:
                response = yield http_client.fetch(request)
                message = json.loads(response.body.decode("utf-8"))
                self.printf("Auth Response: {0}".format(message))
                self.set_secure_cookie("paginateSessionId", message['access_token'], expires_days=1, version=2)
                ret_val = {"success":True, "code":response.code, "data":message}
            except HTTPError as he:
                self.printf("AuthHandler HTTPError Code: {0}, {1}".format(he.code, he.message))
                ret_val = {"success":False, "code":he.code, "message":he.message}
                try:
                    self.printf(he.response.body)
                    self.printf(he.response.headers)
                except Exception as ex:
                    pass
            except Exception as e:
                self.printf(e, "exception")
                #traceback.print_exc()
                message = "{0}".format(e)
                ret_val = {"success":False, "code":500, "message":message}
        else:
            ret_val = {"success":False, "code":500, "message":"'code' cannot be null."}
        self.printf("ret_val: {0}".format(ret_val))
        if ret_val['success']:
            self.redirect("/")
        else:
            self.write(json.dumps(ret_val))

class LoginHandler(BaseHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        if not self.get_secure_cookie("paginateSessionId", max_age_days=1, min_version=2):
            self.printf("Not authenticated. Redirecting...")
            self.printf(Settings.auth_uri)
            self.redirect(Settings.auth_uri)
        else:
            self.printf("Already authenticated.")
            self.printf(self.request.full_url())
            self.printf(self.get_argument("next", u"/"))
            self.redirect(self.get_argument("next", u"/"))
