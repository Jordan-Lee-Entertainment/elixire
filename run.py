import logging

from sanic import Sanic
from sanic import response

import config

app = Sanic()
log = logging.getLogger(__name__)


def main():
    # all static files
    app.static('/static', './static')

    # index page
    app.static('/index.html', './static/index.html')
    app.static('/', './static/index.html')

    app.run(host=config.HOST, port=config.PORT)

if __name__ == '__main__':
    main()
