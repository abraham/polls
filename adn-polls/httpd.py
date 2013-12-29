import os
import tornado
import tornado.web
import pymongo


import views


from app import (
    IndexHandler,

    ActivityHandler,
    RecentHandler,
    ActiveHandler,
    VintageHandler,
    TopHandler,
    TopViewedHandler,

    CreateHandler,
    CreateFreeformHandler,
    PostsHandler,

    PollsIdHandler,
    PollsIdVotesHandler,
    PollsIdPrevHandler,
    PollsIdNextHandler,
    PollsIdRepostsHandler,
    PollsIdRepliesHandler,
    PollsIdStarsHandler,

    UsersIdHandler,
    UsersGridHandler,

    AuthRedirectHandler,
    AuthLogoutHandler,
    AuthCallbackHandler,

    mdHandler,
    txtHandler,
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
    'ui_modules': views,
    'ui_methods': views,
}


base_args = {
    'db': db
}


application = tornado.web.Application([
    (r'/', IndexHandler, base_args),

    (r'/activity', ActivityHandler, base_args),
    (r'/recent', RecentHandler, base_args),
    (r'/active', ActiveHandler, base_args),
    (r'/vintage', VintageHandler, base_args),
    (r'/top', TopHandler, base_args),
    (r'/topviewed', TopViewedHandler, base_args),

    (r'/polls/([^/]+)', PollsIdHandler, base_args),
    (r'/polls/([^/]+)/votes', PollsIdVotesHandler, base_args),
    (r'/polls/([^/]+)/prev', PollsIdPrevHandler, base_args),
    (r'/polls/([^/]+)/next', PollsIdNextHandler, base_args),
    (r'/polls/([^/]+)/reposts', PollsIdRepostsHandler, base_args),
    (r'/polls/([^/]+)/stars', PollsIdStarsHandler, base_args),
    (r'/polls/([^/]+)/replies', PollsIdRepliesHandler, base_args),

    (r'/users-grid', UsersGridHandler, base_args),
    (r'/users/([^/]+)', UsersIdHandler, base_args),

    (r'/create', CreateHandler, base_args),
    (r'/create/freeform', CreateFreeformHandler, base_args),
    (r'/posts', PostsHandler, base_args),

    (r'/auth/redirect', AuthRedirectHandler),
    (r'/auth/logout', AuthLogoutHandler),
    (r'/auth/callback', AuthCallbackHandler, base_args),

    (r'/terms', mdHandler, base_args),
    (r'/privacy', mdHandler, base_args),
    (r'/robots.txt', txtHandler, base_args),
    (r'/humans.txt', txtHandler, base_args),

    (r'/favicon.ico', tornado.web.RedirectHandler, {'url': '/img/favicon.png'}),
    (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': 'adn-polls/static/css'}),
    (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': 'adn-polls/static/img'}),
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
