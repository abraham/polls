import os
import tornado
import tornado.web
import pymongo


from app import (
    MainHandler,
    RecentHandler,
    ActiveHandler,
    VintageHandler,
    TopHandler,
    CreateHandler,
    PollsIdHandler,
    PostsHandler,
    PollsIdVotesHandler,
    PollsIdPrevHandler,
    PollsIdNextHandler,
    UsersIdHandler,
    AuthRedirectHandler,
    AuthLogoutHandler,
    AuthCallbackHandler,
    mdHandler,
)


def get_db():
    db_uri = os.environ.get('MONGODB_CONNECTION')
    db_name = os.environ.get('MONGODB_NAME')
    connection = pymongo.MongoClient(db_uri)
    return connection[db_name]
db = get_db()


settings = {
    'debug': os.environ.get('DEBUG') in ('True', 'true', True),
    'cookie_secret': os.environ.get('COOKIE_SECRET'),
    'gzip': True,
}


base_args = {
    'db': db
}


application = tornado.web.Application([
    (r'/', MainHandler, base_args),

    (r'/recent', RecentHandler, base_args),
    (r'/active', ActiveHandler, base_args),
    (r'/vintage', VintageHandler, base_args),
    (r'/top', TopHandler, base_args),

    (r'/polls/([^/]+)', PollsIdHandler, base_args),
    (r'/polls/([^/]+)/votes', PollsIdVotesHandler, base_args),
    (r'/polls/([^/]+)/prev', PollsIdPrevHandler, base_args),
    (r'/polls/([^/]+)/next', PollsIdNextHandler, base_args),

    (r'/users/([^/]+)', UsersIdHandler, base_args),

    (r'/create', CreateHandler, base_args),
    (r'/posts', PostsHandler, base_args),

    (r'/auth/redirect', AuthRedirectHandler),
    (r'/auth/logout', AuthLogoutHandler),
    (r'/auth/callback', AuthCallbackHandler, base_args),

    (r'/terms', mdHandler, base_args),
    (r'/privacy', mdHandler, base_args),

    (r'/favicon.ico', tornado.web.RedirectHandler, {'url': 'https://abrah.am/favicon.ico'}),
    (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': 'adn-polls/static/css'}),
    (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': 'addv-polls/adn-polls/static/img'}),
    (r'/js/(.*)', tornado.web.StaticFileHandler, {'path': 'adn-polls/static/js'}),
    (r'/fonts/(.*)', tornado.web.StaticFileHandler, {'path': 'adn-polls/static/fonts'}),
], **settings)


if __name__ == '__main__':
    port = os.environ.get('PORT', 8080)
    print ''
    print '==============='
    print 'Starting server'
    print '==============='
    print 'DEBUG', settings['debug']
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
