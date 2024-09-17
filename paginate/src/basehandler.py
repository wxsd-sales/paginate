import tornado.web

class BaseHandler(tornado.web.RequestHandler):
    def printf(self, line, error_level=None):
        log = self.application.settings.get('log')
        if log != None:
            if error_level == None:
                log.info(line)
            elif error_level == "debug":
                log.debug(line)
            elif error_level == "exception":
                log.exception(line)
        else:
            print(line)
