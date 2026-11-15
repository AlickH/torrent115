import app as appmod

appmod.start_runtime()
application = appmod.app

PREFIX = "/app/torrent115"


class PrefixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == PREFIX or path.startswith(PREFIX + "/"):
            environ["SCRIPT_NAME"] = PREFIX
            environ["PATH_INFO"] = path[len(PREFIX):] or "/"
        return self.wsgi_app(environ, start_response)


application = PrefixMiddleware(application)
