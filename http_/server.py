"""HTTP server module
"""

from importlib import import_module
from functools import partial

from urllib.parse import urlparse
from http.server import ThreadingHTTPServer
from http.server import BaseHTTPRequestHandler

from db.sqlite_db_handler import SQLiteDBHandler

class RequestHandler(BaseHTTPRequestHandler):
    """Class for handling request
    """

    MODULES_PATH = __package__ + '.modules'
    MODULES_PATH_ = MODULES_PATH + '.'

    def __init__(self, db: SQLiteDBHandler, *args, **kwargs):
        self.__db = db
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle the HTTP GET request
        """

        path = urlparse(self.path).path
        print(self.path)
        try:
            module = import_module(RequestHandler.MODULES_PATH + path.replace('/', '.'))
            module.Module(self, self.__db)
        except ModuleNotFoundError as exception:
            print(exception)
            self.send_response_only(404)
            self.end_headers()

class HTTPServer:
    """Main HTTP server class
    """

    def __init__(self, db, port=8080):
        self.__port = port
        self.__db = db
        self.__is_serving = False

    def get_port(self):
        """return the port used by the HTTP server
        """

        return self.__port

    def is_serving(self):
        """return true if the HTTP server is running
        """

        return self.__is_serving

    def serve_forever(self):
        """ start serving
        """

        self.__is_serving = True
        handler = partial(RequestHandler, self.__db)
        httpd = ThreadingHTTPServer(('', self.__port), handler)
        httpd.serve_forever()
        self.__is_serving = False