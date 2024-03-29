import os
import tornado
import tornado.template as template
import json
import tornado.locale
import pymongo.errors
import urllib
import requests
import time
from bson.objectid import ObjectId
import random
import momentpy
import dateutil.parser
import time


from models import polls, users, actions
from decorators import require_auth, require_poll, require_user
import sync


def write_error(self, code, message=None, **kwargs):
    self.set_status(code)
    if code == 404:
        self.render('templates/404.html', message=message)
    elif code in (500, 503):
        self.render('templates/500.html')
    else:
        self.render('templates/500.html')


tornado.web.RequestHandler.write_error = write_error


class BaseHandler(tornado.web.RequestHandler):

    def initialize(self, db=None):
        self.db = db
        self.current_user = None
        self.cookie = None

        cookie = self.get_json_cookie()
        self.cookie = cookie
        user_id = cookie.get('user_id')

        if db is not None and user_id is not None:
            self.current_user = users.find_by_id(db=db, user_id=ObjectId(user_id))
            if self.current_user['status'] in (u'disabled', u'reauth'):
                self.current_user = None


    def prepare(self):
        proto = self.request.headers.get('X-Forwarded-Proto', 'http')
        origin = self.request.headers.get('Origin', None)
        referer = self.request.headers.get('Referer', None)
        host = self.request.headers.get('Host', None)
        debug = os.environ.get('DEBUG') in ('True', 'true', True)

        directives = [
            "default-src 'none'",
            "connect-src 'self'",
            "font-src 'self'",
            "frame-src 'none'",
            "img-src 'self' https:",
            "media-src 'none'",
            "script-src 'self' https://www.google.com https://ajax.googleapis.com https://www.google-analytics.com 'unsafe-eval'",
            "style-src 'self' https://ajax.googleapis.com https://www.google.com",
        ]
        self.set_header('Content-Security-Policy', '; '.join(directives))
        self.set_header('X-XSS-Protection', '1; mode=block')
        self.set_header('X-Content-Type-Options', 'nosniff')
        self.set_header('X-Frame-Options', 'DENY')

        if proto.lower() == 'https' :
            self.set_header('Strict-Transport-Security', 'max-age="31536000"; includeSubDomains')
        if proto == 'http' and not debug:
            print 'Redirecting to SSL', self.request.host, self.request.path, 'from', referer
            url = u'https://{}{}'.format(self.request.host, self.request.path)
            self.redirect(url)
            return
        if host is not None and not debug and host != 'polls.abrah.am':
            print 'Redirecting to polls.abrah.am', self.request.path, 'from', referer
            url = u'https://{}{}'.format('polls.abrah.am', self.request.path)
            self.redirect(url)
            return


    def set_json_cookie(self, args):
        '''write a dict of data to a secure cookie'''
        args['created_at'] = int(time.time())
        args['version'] = '1'
        self.set_secure_cookie('c_is_for_cookie', json.dumps(args))


    def get_json_cookie(self):
        '''Read cookie by name'''
        value = self.get_secure_cookie('c_is_for_cookie')
        if value is None:
            return {}
        else:
            return json.loads(value)


    def _handle_request_exception(self, exception):
        import traceback
        debug = self.application.settings['debug'] in ('True', 'true', True)
        http_error = isinstance(exception, tornado.web.HTTPError)

        if not http_error and not debug:
            try:
                print 'Mailing error email'
                text = "Uncaught exception %s\n\n\n%r\n" % (self._request_summary(), self.request)

                if self.request.method == 'POST':
                    text += "\n\nPOST Request body: %s" % (self.request.body, )

                trace_str = traceback.format_exc()
                text += '\n\n' + trace_str
                send_simple_message(to=['4braham@gmail.com'], subject='Polls uncaught exception', text=text)
            except:
                print "** Failing even to email exception **"
        super(BaseHandler, self)._handle_request_exception(exception)


class mdHandler(BaseHandler):

    def get(self):
        '''Return the markdown files for terms and privacy policy'''
        import markdown2

        db = self.db
        current_user = self.current_user
        path = 'adn-polls/static/md{}.md'.format(self.request.path)
        html = markdown2.markdown_path(path)
        title = 'Polls for App.net'

        if self.request.path == '/terms':
            title = 'Polls Terms of Service'
        elif self.request.path == '/privacy':
            title = 'Polls Privacy Policy'
        
        context = {
            'current_user': current_user,
            'unsafe_html': html,
            'title': title,
        }
        self.render('templates/md.html', **context)


class txtHandler(BaseHandler):

    def get(self):
        '''Return the markdown files for terms and privacy policy'''
        self.set_header('Content-Type', 'text/plain')
        self.render('static/txt{}'.format(self.request.path))


class AuthRedirectHandler(BaseHandler):

    def get(self):
        '''Redirect to ADN to authorize the user'''
        db = self.db
        current_user = self.current_user

        if self.get_argument('redirect', None) is not None:
            args = {
                'redirect': self.get_argument('redirect', None),
            }
            self.set_json_cookie(args)

        args = {
            'client_id': os.environ['ADN_CLIENT_ID'],
            'response_type': 'code',
            'redirect_uri': '{}/auth/callback'.format(os.environ['BASE_WEB_URL']),
            'scope': 'basic write_post public_messages',
        }
        url = 'https://account.app.net/oauth/authenticate?{}'.format(urllib.urlencode(args))
        self.redirect(url)


class AuthCallbackHandler(BaseHandler):

    def get(self):
        '''The user has returned from ADN, hopefully after granting authorization'''
        db = self.db
        current_user = None
        existing_user = True

        redirect = self.cookie.get('redirect', '/')
        code = self.get_argument('code', None)
        if code is None:
            context = {
                'title': 'Access DENIED!?!',
                'header': 'Access DENIED!?!',
                'message': "Polls can't do much if don't authorize access. We promise not to post without your permission.",
            }
            self.render('templates/error.html', **context)
            return
        url = 'https://account.app.net/oauth/access_token'
        args = {
            'client_id': os.environ['ADN_CLIENT_ID'],
            'client_secret': os.environ['ADN_CLIENT_SECRET'],
            'grant_type': 'authorization_code',
            'redirect_uri': '{}/auth/callback'.format(os.environ['BASE_WEB_URL']),
            'code': code,
        }
        response = requests.post(url, data=args)

        if response.status_code != 200:
            if 'code-used' in response.content:
                context = {
                    'title': 'Double Rainbow!!',
                    'header': 'Double Rainbow!!',
                    'message': 'That code was already used, try signing in again.',
                }
                self.render('templates/error.html', **context)
                return
            self.set_status(500)
            self.render('templates/500.html')
            raise Exception(response.content)

        token = response.json()
        adn_id = token['token']['user']['id']
        current_user = users.find_by_adn_id(db=db, adn_id=adn_id)
        if current_user is None:
            new_user = {
                'access_token': token['access_token'],
                'user_type': 'user',
                'adn_id': adn_id,
                'user_name': token['username'],
                'user_avatar': token['token']['user']['avatar_image']['url'],
                'user_avatar_is_default': token['token']['user']['avatar_image']['is_default'],
                'user_cover': token['token']['user']['cover_image']['url'],
                'user_cover_is_default': token['token']['user']['cover_image']['is_default'],
                'user_text': None,
                'user_full_name': token['token']['user'].get('name', token['username']),
            }
            if token['token']['user'].get('description', None) is not None:
                new_user['user_text'] = token['token']['user']['description']['text']
            current_user = users.create(db=db, **new_user)
            existing_user = False
        else:
            if current_user['user_type'] == 'profile':
                existing_user = False

            update = {
                'user_type': 'user',
                'status': current_user['status'],
                'access_token': token['access_token'],
                'user_name': token['username'],
                'user_avatar': token['token']['user']['avatar_image']['url'],
                'user_avatar_is_default': token['token']['user']['avatar_image']['is_default'],
                'user_cover': token['token']['user']['cover_image']['url'],
                'user_cover_is_default': token['token']['user']['cover_image']['is_default'],
                'user_text': None,
                'user_full_name': token['token']['user'].get('name', token['username']),
            }

            if current_user['status'] == 'reauth':
                update['status'] = 'active'

            if token['token']['user'].get('description', None) is not None:
                update['user_text'] = token['token']['user']['description']['text']
            users.update(db=db, user_id=current_user['_id'], **update)

        self.set_json_cookie({'user_id': str(current_user['_id'])})
        if '/auth/callback' not in redirect:
            self.redirect(redirect)
        else:
            self.redirect('/')

        if existing_user == False:
            action = {
                'user_name': current_user['user_name'],
                'user_avatar': current_user['user_avatar'],
                'user_id': current_user['_id'],
            }
            actions.new_user(db=db, **action)


class AuthLogoutHandler(BaseHandler):

    def get(self):
        '''Redirect to ADN to authorize the user'''
        self.clear_all_cookies()
        self.redirect('/')


class IndexHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        active_polls = polls.find_active(db=db, limit=5, min_vote_count=3)
        for poll in active_polls:
            poll['votes'].reverse()
            random.shuffle(poll['options'])
            poll['options_object'] = json.dumps(polls.build_options_object(poll['options'])).replace("'", "&#39;")
            poll['redirect'] = '/polls/{}'.format(poll['_id'])

        context = {
            'current_user': current_user,
            'header_title': 'Polls for App.net',
            'header_subtitle': 'clean, simple, beautiful',
            'active_polls': active_polls,
        }
        self.render('templates/index.html', **context)

        for poll in active_polls:
            polls.inc_views(db=db, poll_id=poll['_id'])


class SearchHandler(BaseHandler):

    def get(self):
        db              = self.db
        current_user    = self.current_user
        query           = self.get_argument('query', None)
        results_polls   = []
        results         = []

        if query is not None:
            if current_user is None:
                access_token = os.environ['ADN_CLIENT_ACCESS_TOKEN']
            else:
                access_token = current_user['access_token']

            url = 'https://alpha-api.app.net/stream/0/posts/search'
            headers = {
                'Authorization': 'Bearer {}'.format(access_token),
                'Content-type': 'application/json',
            }
            args = {
                'query': query,
                'order': 'score',
                'is_crosspost': '1',
                'client_id': 'KgWW36vGe8LQPN696ftSUqdKUvjzuYqF',
                'crosspost_domain': 'polls.abrah.am',
                'include_post_annotations': '1',
            }
            request = requests.get(url, params=args, headers=headers)

            for r in request.json()['data']:
                post = {}
                post['created_at'] = dateutil.parser.parse(r['created_at']).replace(tzinfo=None)
                post['text'] = r['text']
                post['user_name'] = r['user']['username']
                post['user_avatar'] = r['user']['avatar_image']['url']

                for _a in r['annotations']:
                    if _a['type'] == 'net.app.core.crosspost':
                        post['url'] = _a['value']['canonical_url']
                if r['thread_id'] == r['id']:
                    post['type'] = 'poll'
                    results_polls.append(post)
                else:
                    post['type'] = 'reply'
                    results.append(post)

        context = {
            'current_user': current_user,
            'header_title': 'Abracadabra!',
            'header_subtitle': 'Search results',
            'results': results_polls + results,
            'query': query,
        }
        self.render('templates/search.html', **context)


class RandomHandler(BaseHandler):

    def get(self):
        db              = self.db
        current_user    = self.current_user
        poll            = polls.find_random(db=db)

        while (current_user is not None and poll['user_id'] == current_user['_id']) \
            or poll['status'] != 'active':
            poll = polls.find_random(db=db)

        self.redirect('/polls/{}'.format(poll['_id']))


class ActivityHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        recent_actions = actions.find_recent(db=db)
        context = {
            'title': 'Recent activity on Polls',
            'current_user': current_user,
            'header_title': 'Recent activity',
            'header_subtitle': '',
            'recent_actions': recent_actions,
        }
        self.render('templates/actions.html', **context)


class RecentHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        recent_polls = polls.find_recent(db=db)
        for poll in recent_polls:
            poll['votes'].reverse()
        context = {
            'current_user': current_user,
            'header_title': 'New polls',
            'header_subtitle': 'are the latest and (maybe) greatest',
            'recent_polls': recent_polls,
            'show_views': False,
        }
        self.render('templates/list.html', **context)


class UsersGridHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        all_users = users.find_recent(db=db)
        context = {
            'current_user': current_user,
            'header_title': 'Users',
            'header_subtitle': 'Little boxes on the hillside',
            'users': all_users,
        }
        self.render('templates/grid.html', **context)


class UsernameRedirectHandler(BaseHandler):

    def get(self, username):
        '''Redirect to Polls profile if in db, else to ADN'''
        user = users.find_by_username(db=self.db, username=username)

        if user is not None:
            self.redirect('/users/{}'.format(user['_id']))
        else:
            self.redirect(u'https://alpha.app.net/{}'.format(username))


class UsersIdHandler(BaseHandler):

    def get(self, user_id):
        db = self.db
        current_user = self.current_user

        try:
            viewed_user = users.find_by_id(db=db, user_id=ObjectId(user_id))
        except pymongo.errors.InvalidId, e:
            self.send_error(404)
            return
        if viewed_user is None:
            self.send_error(404)
            return

        recent_actions = actions.find_recent_by_user_id(db=db, user_id=ObjectId(user_id))

        subtitle = u'<a href="https://alpha.app.net/{}" class="external" title="View on ADN" rel="me"><span class="glyphicon glyphicon-new-window"></span></a> '.format(viewed_user['user_name'])
        subtitle += u'<a href="https://omega.app.net/new-message?to={}" class="external" title="Message on Omega"><span class="glyphicon glyphicon-envelope"></span></a> '.format(viewed_user['adn_id'])
        subtitle += u'&nbsp;<a href="/users/{}/polls" title="View polls by user">{} polls</a> &middot; '.format(viewed_user['_id'], viewed_user['polls_count'])
        subtitle += u'{} votes &middot; '.format(viewed_user['votes_count'])
        subtitle += u'{} views'.format(viewed_user['views'])

        context = {
            'title': u'{} on Polls for App.net'.format(viewed_user['user_name']),
            'current_user': current_user,
            'header_title': u'{}'.format(viewed_user['user_name']),
            'header_subtitle': subtitle,
            'recent_actions': recent_actions,
        }
        self.render('templates/actions.html', **context)
        users.inc_views(db=db, user_id=viewed_user['_id'])


class UsersIdPollsHandler(BaseHandler):

    @require_user
    def get(self, user_id):
        db = self.db
        current_user = self.current_user
        viewed_user = self.viewed_user
        viewed_user_id = self.viewed_user_id

        recent_polls = polls.find_recent_by_user_id(db=db, user_id=viewed_user_id)

        context = {
            'current_user': current_user,
            'title': u'{} on Polls for App.net'.format(viewed_user['user_name']),
            'current_user': current_user,
            'header_title': u'Polls by {}'.format(viewed_user['user_name']),
            'header_subtitle': '',
            'recent_polls': recent_polls,
            'show_views': False,
        }

        self.render('templates/list.html', **context)
        users.inc_views(db=db, user_id=viewed_user_id)


class ActiveHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        recent_polls = polls.find_active(db=db, limit=20, min_vote_count=2)

        for poll in recent_polls:
            poll['votes'].reverse()

        context = {
            'current_user': current_user,
            'header_title': 'Trending polls',
            'header_subtitle': 'are movers and shakers',
            'recent_polls': recent_polls,
            'show_views': False,
        }
        self.render('templates/list.html', **context)


class VintageHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        vintage_polls = polls.find_vintage(db=db)

        for poll in vintage_polls:
            poll['votes'].reverse()

        context = {
            'current_user': current_user,
            'header_title': 'Vintage polls',
            'header_subtitle': 'have not been voted on in a while',
            'recent_polls': vintage_polls,
            'show_views': False,
        }
        self.render('templates/list.html', **context)


class TopHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        top_polls = polls.find_top(db=db)

        for poll in top_polls:
            poll['votes'].reverse()

        context = {
            'current_user': current_user,
            'header_title': 'Top polls',
            'header_subtitle': 'have (almost) ALL THE VOTES',
            'recent_polls': top_polls,
            'show_views': False,
        }
        self.render('templates/list.html', **context)


class TopViewedHandler(BaseHandler):

    def get(self):
        db = self.db
        current_user = self.current_user

        top_polls = polls.find_top_viewed(db=db)

        for poll in top_polls:
            poll['votes'].reverse()

        context = {
            'current_user': current_user,
            'header_title': 'Most viewed polls',
            'header_subtitle': 'have (almost) ALL THE VIEWS',
            'recent_polls': top_polls,
            'show_views': True,
        }
        self.render('templates/list.html', **context)


class CreateHandler(BaseHandler):

    @require_auth
    def get(self):
        db = self.db
        current_user = self.current_user
        error_type = False

        query_error = self.get_argument('error', False)

        if query_error == 'missing-required-fields':
            error_type = 'missing-required-fields'

        context = {
            'error_type': error_type,
            'current_user': current_user,
            'xsrf_input': self.xsrf_form_html(),
        }
        self.render('templates/create.html', **context)


    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user

        poll_id = ObjectId()
        poll_id_str = str(poll_id)
        question = self.get_argument('question')[:150]
        options = []
        for option in self.get_arguments('options'):
            if option != '':
                options.append(option[:100])

        if len(question) == 0 or len(options) < 2:
            self.redirect('/create?error=missing-required-fields')
            return

        poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)
        text = u'Q: {}\n\nVote on @polls at {}'.format(question, poll_url)
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            },
            {
                "type": "net.app.core.fallback_url",
                "value": {
                    "url": poll_url,
                },
            }],
        }
        request = requests.post(url, data=json.dumps(args), headers=headers)

        if request.status_code != 200:
            if request.status_code == 401:
                response = request.json()

                if response['meta']['error_slug'] in (u'requires-reauth', u'not-authorized'):
                    print 'WARNING: user requires reauth', current_user['_id']
                    users.require_requth(db=db, user_id=current_user['_id'])

                    context = {
                        'title': 'Expired authentication',
                        'header': 'Expired Authentication',
                        'message': "You have to <a href='/auth/redirect?redirect=/create'>reauthorize access</a> to App.net before you can create a poll.",
                    }
                    self.render('templates/error.html', **context)
                    return

            raise Exception(request.content)

        post = request.json()

        args = {
            'poll_id': poll_id,
            'poll_type': 'multiplechoice',
            'display_type': 'donut',
            'results_type': 'public',
            'question': question,
            'options': options,
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'post_id': post['data']['id'],
            'post_url': post['data']['canonical_url'],

        }
        poll = polls.create(db=self.db, **args)

        self.redirect('/polls/{}'.format(poll_id_str))

        action = {
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'user_id': current_user['_id'],
            'question': question,
            'poll_id': poll['_id'],
            'post_url': post['data']['canonical_url'],
        }
        actions.new_poll(db=db, **action)

        subject = u'{} by @{}'.format(question, current_user['user_name'])
        channel_id = os.environ.get('ADN_CHANNEL_ID')
        polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_polls_count(db=db, user_id=current_user['_id'])


class CreateAnonymouseHandler(BaseHandler):

    @require_auth
    def get(self):
        db = self.db
        current_user = self.current_user
        error_type = False

        query_error = self.get_argument('error', False)

        if query_error == 'missing-required-fields':
            error_type = 'missing-required-fields'

        context = {
            'error_type': error_type,
            'current_user': current_user,
            'xsrf_input': self.xsrf_form_html(),
        }
        self.render('templates/create_anonymous.html', **context)


    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user

        poll_id = ObjectId()
        poll_id_str = str(poll_id)
        question = self.get_argument('question')[:150]
        options = []
        for option in self.get_arguments('options'):
            if option != '':
                options.append(option[:100])

        if len(question) == 0 or len(options) < 2:
            self.redirect('/create?error=missing-required-fields')
            return

        poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)
        text = u'Q: {}\n\nVote anonymously on @polls at {}'.format(question, poll_url)
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            },
            {
                "type": "net.app.core.fallback_url",
                "value": {
                    "url": poll_url,
                },
            }],
        }
        request = requests.post(url, data=json.dumps(args), headers=headers)

        if request.status_code != 200:
            if request.status_code == 401:
                response = request.json()

                if response['meta']['error_slug'] in (u'requires-reauth', u'not-authorized'):
                    print 'WARNING: user requires reauth', current_user['_id']
                    users.require_requth(db=db, user_id=current_user['_id'])

                    context = {
                        'title': 'Expired authentication',
                        'header': 'Expired Authentication',
                        'message': "You have to <a href='/auth/redirect?redirect=/create'>reauthorize access</a> to App.net before you can create a poll.",
                    }
                    self.render('templates/error.html', **context)
                    return

            raise Exception(request.content)

        post = request.json()

        args = {
            'poll_id':      poll_id,
            'poll_type':    'multiplechoice',
            'display_type': 'donut',
            'results_type': 'anonymous',
            'question':     question,
            'options':      options,
            'user_id':      current_user['_id'],
            'user_name':    current_user['user_name'],
            'user_avatar':  current_user['user_avatar'],
            'post_id':      post['data']['id'],
            'post_url':     post['data']['canonical_url'],

        }
        poll = polls.create(db=self.db, **args)

        self.redirect('/polls/{}'.format(poll_id_str))

        action = {
            'user_name':    current_user['user_name'],
            'user_avatar':  current_user['user_avatar'],
            'user_id':      current_user['_id'],
            'question':     question,
            'poll_id':      poll['_id'],
            'post_url':     post['data']['canonical_url'],
        }
        actions.new_poll(db=db, **action)

        subject = u'{} by @{}'.format(question, current_user['user_name'])
        channel_id = os.environ.get('ADN_CHANNEL_ID')
        polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_polls_count(db=db, user_id=current_user['_id'])


class CreateFreeformHandler(BaseHandler):

    @require_auth
    def get(self):
        db = self.db
        current_user = self.current_user
        error_type = False

        query_error = self.get_argument('error', False)

        if query_error == 'missing-required-fields':
            error_type = 'missing-required-fields'

        context = {
            'error_type': error_type,
            'current_user': current_user,
            'xsrf_input': self.xsrf_form_html(),
        }
        self.render('templates/create_freeform.html', **context)


    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user

        poll_id = ObjectId()
        poll_id_str = str(poll_id)
        question = self.get_argument('question')[:150]

        if len(question) == 0:
            self.redirect('/create?error=missing-required-fields')
            return

        poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)
        text = u'Q: {}\n\nVote on @polls at {}'.format(question, poll_url)
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            },
            {
                "type": "net.app.core.fallback_url",
                "value": {
                    "url": poll_url,
                },
            }],
        }
        request = requests.post(url, data=json.dumps(args), headers=headers)

        if request.status_code != 200:
            if request.status_code == 401:
                response = request.json()

                if response['meta']['error_slug'] in (u'requires-reauth', u'not-authorized'):
                    print 'WARNING: user requires reauth', current_user['_id']
                    users.require_requth(db=db, user_id=current_user['_id'])

                    context = {
                        'title': 'Expired authentication',
                        'header': 'Expired Authentication',
                        'message': "You have to <a href='/auth/redirect?redirect=/create'>reauthorize access</a> to App.net before you can create a poll.",
                    }
                    self.render('templates/error.html', **context)
                    return

            raise Exception(request.content)

        post = request.json()

        args = {
            'poll_id': poll_id,
            'poll_type': 'freeform',
            'display_type': 'list',
            'results_type': 'public',
            'question': question,
            'options': ['freeform'],
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'post_id': post['data']['id'],
            'post_url': post['data']['canonical_url'],

        }
        poll = polls.create(db=self.db, **args)

        self.redirect('/polls/{}'.format(poll_id_str))

        action = {
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'user_id': current_user['_id'],
            'question': question,
            'poll_id': poll['_id'],
            'post_url': post['data']['canonical_url'],
        }
        actions.new_poll(db=db, **action)

        subject = u'{} by @{}'.format(question, current_user['user_name'])
        channel_id = os.environ.get('ADN_CHANNEL_ID')
        polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_polls_count(db=db, user_id=current_user['_id'])


class PollsIdPrevHandler(BaseHandler):

    def get(self, poll_id):
        db = self.db
        current_user = self.current_user
        poll_id = object_id(poll_id)
        if poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_prev(db=db, current_id=poll_id)
        if poll is None:
            message = "No more previous polls found, <a href='/'>go home</a>, you're drunk."
            self.write_error(code=404, message=message)
            return

        url = '/polls/{}'.format(str(poll['_id']))
        self.redirect(url)


class PollsIdNextHandler(BaseHandler):

    def get(self, poll_id):
        db = self.db
        current_user = self.current_user
        poll_id = object_id(poll_id)
        if poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_next(db=db, current_id=poll_id)
        if poll is None:
            message = "Th-Th-Th-Th-Th-... That's all, folks. No more polls found, <a href='/'>go home</a>."
            self.write_error(code=404, message=message)
            return

        url = '/polls/{}'.format(str(poll['_id']))
        self.redirect(url)


class PollsIdRepostsHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        new_action = True

        poll_id = object_id(poll_id)
        if poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_by_id(db=db, poll_id=poll_id)
        if poll is None:
            self.write_error(404)
            return

        if current_user['_id'] in poll['post_reposted_by']:
            new_action = False

        url = 'https://alpha-api.app.net/stream/0/posts/{}/repost'.format(poll['post_id'])
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token'])
        }
        result = requests.post(url, headers=headers)
        response = result.json()

        if result.status_code == 200:
            self.write('success')
            polls.add_to_set(db=db, poll_id=poll['_id'], field='post_reposted_by', value=current_user['_id'])
            if new_action:
                action = {
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                    'user_id': current_user['_id'],
                    'poll_id': poll['_id'],
                    'question': poll['question'],
                    'post_url': poll['post_url'],
                    'post_id': poll['post_id'],
                }
                actions.new_poll_repost(db=db, **action)
            return
        else:
            if result.status_code == 400:
                self.set_status(400)
                self.write(response['meta']['error_message'])
                return

            raise Exception(result.content)


class PollsIdStarsHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        new_action = True

        poll_id = object_id(poll_id)
        if poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_by_id(db=db, poll_id=poll_id)
        if poll is None:
            self.write_error(404)
            return

        if current_user['_id'] in poll.get('post_starred_by', []):
            new_action = False

        url = 'https://alpha-api.app.net/stream/0/posts/{}/star'.format(poll['post_id'])
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token'])
        }
        result = requests.post(url, headers=headers)
        response = result.json()

        if result.status_code == 200:
            self.write('success')
            polls.add_to_set(db=db, poll_id=poll['_id'], field='post_starred_by', value=current_user['_id'])
            if new_action:
                action = {
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                    'user_id': current_user['_id'],
                    'poll_id': poll['_id'],
                    'question': poll['question'],
                    'post_url': poll['post_url'],
                    'post_id': poll['post_id'],
                }
                actions.new_poll_star(db=db, **action)
            return
        else:
            if result.status_code == 400:
                self.set_status(400)
                self.write(response['meta']['error_message'])
                return

            self.set_status(500)
            raise Exception(result.content)


class PollsIdVotesHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        current_option = None
        custom_reply = False

        text = self.get_argument('text', None)
        option_id = object_id(self.get_argument('optionId'))
        poll_id = object_id(poll_id)
        if option_id is None or poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_by_id(db=db, poll_id=poll_id)
        if poll is None:
            self.write_error(404)
            return

        if current_user['_id'] in poll['votes_user_ids']:
            self.write_error(400)
            return

        for option in poll['options']:
            if option_id == option['_id']:
                current_option = option
                continue

        if current_option is None:
            self.write_error(400)
            return

        args = {
            'option_id': option_id,
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
        }
        polls.vote(db=db, poll_id=poll_id, **args)

        if text is None or text in (u'', ''):
            text = u'@{} {}'.format(poll['user_name'], current_option['display_text'])
        else:
            custom_reply = True

        reply_id = ObjectId()
        poll_url = '{}/polls/{}#{}'.format(os.environ['BASE_WEB_URL'], str(poll_id), str(reply_id))
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'reply_to': poll['post_id'],
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            }],
        }
        response = requests.post(url, data=json.dumps(args), headers=headers)
        if response.status_code != 200:
            raise Exception(response.content)

        post = response.json()['data']
        post_url = post['canonical_url']
        post_id = post['id']

        if custom_reply:
            reply_type = 'polls_vote_custom'
        else:
            reply_type = 'polls_vote'

        reply = {
            '_id': reply_id,
            'reply_type': reply_type,
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'post_id': post['id'],
            'post_url': post['canonical_url'],
            'post_text': post['text'],
            'post_client_id': post['source']['client_id'],
            'post_reply_to': post['reply_to'],
            'post_thread_id': post['thread_id'],
            'poll_id': poll_id,
        }
        reply = polls.add_reply(db=db, **reply)

        html = self.render_string('templates/polls_replies.html', poll_id=poll_id, **{ 'reply': reply})
        self.set_header('Content-Type', 'text/html')
        self.write(html)

        action = {
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'user_id': current_user['_id'],
            'question': poll['question'],
            'poll_id': poll['_id'],
            'option': text,
            'post_url': post_url,
            'post_id': post_id,
        }
        actions.new_vote(db=db, **action)
        # TODO: update existing vote with post details
        # TODO: add post details to replies

        if poll['total_votes'] == 4: # Current vote is not yet tallied
            poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id)
            subject = u'{} by @{}'.format(poll['question'], poll['user_name'])
            channel_id = os.environ.get('ADN_CHANNEL_ID_2')
            polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_votes_count(db=db, user_id=current_user['_id'])

        nub = {
            'html': html,
            'action': 'new_vote',
            'optionId': str(option_id),
            'replyId': post['id'],
            'pollId': str(poll_id),
            'views': poll['views'],
        }
        push(channel=str(poll_id), message=nub)


class PollsIdVotesAnonymousHandler(BaseHandler):

    @require_auth
    @require_poll
    def post(self, poll_id_str):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        current_poll = self.current_poll
        current_poll_id = self.current_poll_id
        current_option = None

        option_id = object_id(self.get_argument('optionId'))
        if option_id is None:
            self.write_error(404)
            return

        if current_user['_id'] in current_poll['votes_user_ids']:
            self.write_error(400)
            return

        for option in current_poll['options']:
            if option_id == option['_id']:
                current_option = option
                continue

        if current_option is None:
            self.write_error(400)
            return

        args = {
            'option_id': option_id,
            'user_id': current_user['_id'],
        }
        polls.vote_anonymous(db=db, poll_id=current_poll_id, **args)

        self.set_header('Content-Type', 'text/html')
        self.write('')

        action = {
            'user_name': 'Anonymous',
            'user_avatar': 'https://polls.abrah.am/img/incognito.png',
            'user_id': None,
            'question': current_poll['question'],
            'poll_id': current_poll_id,
            'option': current_option['display_text'],
            'post_url': None,
            'post_id': None,
        }
        actions.new_vote(db=db, **action)

        if current_poll['total_votes'] == 4: # Current vote is not yet tallied
            poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)
            subject = u'{} by @{}'.format(current_poll['question'], current_poll['user_name'])
            channel_id = os.environ.get('ADN_CHANNEL_ID_2')
            polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_votes_count(db=db, user_id=current_user['_id'])

        nub = {
            'html': '',
            'action': 'new_vote',
            'optionId': str(option_id),
            'replyId': None,
            'pollId': poll_id_str,
            'views': current_poll['views'],
        }
        push(channel=poll_id_str, message=nub)


class PollsIdVotesFreeformHandler(BaseHandler):

    @require_auth
    @require_poll
    def post(self, poll_id_str):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        current_poll = self.current_poll
        current_poll_id = self.current_poll_id

        text = self.get_argument('text')
        option_id = object_id(self.get_argument('optionId'))
        if text is None or text == '':
            self.write_error(404)
            return

        if current_user['_id'] in current_poll['votes_user_ids']:
            self.write_error(400)
            return

        args = {
            'option_id': option_id,
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
        }
        polls.vote(db=db, poll_id=current_poll_id, **args)

        reply_id = ObjectId()
        poll_url = '{}/polls/{}#{}'.format(os.environ['BASE_WEB_URL'], poll_id_str, str(reply_id))
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'reply_to': current_poll['post_id'],
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            }],
        }
        response = requests.post(url, data=json.dumps(args), headers=headers)
        if response.status_code != 200:
            raise Exception(response.content)

        post = response.json()['data']
        post_url = post['canonical_url']
        post_id = post['id']

        reply = {
            '_id': reply_id,
            'reply_type': 'polls_vote_freeform',
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'post_id': post['id'],
            'post_url': post['canonical_url'],
            'post_text': post['text'],
            'post_client_id': post['source']['client_id'],
            'post_reply_to': post['reply_to'],
            'post_thread_id': post['thread_id'],
        }
        reply = polls.add_reply(db=db, poll_id=current_poll_id, **reply)

        html = self.render_string('templates/polls_replies.html', poll_id=current_poll_id, **{ 'reply': reply})
        self.set_header('Content-Type', 'text/html')
        self.write(html)

        action = {
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'user_id': current_user['_id'],
            'question': current_poll['question'],
            'poll_id': current_poll_id,
            'option': text,
            'post_url': post_url,
            'post_id': post_id,
        }
        actions.new_vote(db=db, **action)
        # TODO: update existing vote with post details
        # TODO: add post details to replies

        if current_poll['total_votes'] == 4: # Current vote is not yet tallied
            poll_url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)
            subject = u'{} by @{}'.format(current_poll['question'], current_poll['user_name'])
            channel_id = os.environ.get('ADN_CHANNEL_ID_2')
            polls.send_alert(channel_id=channel_id, subject=subject, poll_url=poll_url)

        users.inc_votes_count(db=db, user_id=current_user['_id'])

        nub = {
            'html': html,
            'action': 'new_reply',
            'replyId': post['id'],
            'pollId': poll_id_str,
            'views': current_poll['views'],
        }
        push(channel=poll_id_str, message=nub)


class PostsHandler(BaseHandler):

    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        text = self.get_argument('text')

        if text in (u'', ''):
            self.write_error(400)
            return
        
        url = 'https://alpha-api.app.net/stream/0/posts'
        args = {
            'text': text,
        }
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
        }
        response = requests.post(url, data=args, headers=headers)

        if response.status_code != 200:
            self.write_error(500)
            return


class PollsIdRepliesIdStarsHandler(BaseHandler):

    @require_auth
    @require_poll
    def post(self, poll_id_str, reply_id_str):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        current_poll = self.current_poll
        current_poll_id = self.current_poll_id
        reply_id = object_id(reply_id_str)
        reply = None

        if reply_id is None:
            self.write_error(404)
            return

        for n in current_poll['post_replies']:
            if n['_id'] == reply_id:
                reply = n
                continue

        if reply is None:
            self.write_error(404)
            return

        url = 'https://alpha-api.app.net/stream/0/posts/{}/star'.format(reply['post_id'])
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token'])
        }
        result = requests.post(url, headers=headers)
        response = result.json()

        if result.status_code == 200:
            self.write('success')
            self.finish()

            if current_user['_id'] not in reply.get('starred_by', []):
                activity = {
                    'user_id': current_user['_id'],
                    'type': 'star',
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                }

                polls.add_reply_star(db=db, poll_id=current_poll_id, reply_id=reply_id, user_id=current_user['_id'])
                polls.add_reply_activity(db=db, poll_id=current_poll_id, reply_id=reply_id, activity=activity)

                action = {
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                    'user_id': current_user['_id'],
                    'poll_id': current_poll_id,
                    'reply_id': reply['_id'],
                    'text': reply['post_text'],
                    'post_url': reply['post_url'],
                    'post_id': reply['post_id'],
                    'reply_user_name': reply['user_name'],
                    'reply_user_id': reply['user_id'],
                }
                actions.new_reply_star(db=db, **action)

        else:
            if result.status_code == 400:
                self.set_status(400)
                self.write(response['meta']['error_message'])
                return

            self.set_status(500)
            raise Exception(result.content)


class PollsIdRepliesIdRepostsHandler(BaseHandler):

    @require_auth
    @require_poll
    def post(self, poll_id_str, reply_id_str):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        current_poll = self.current_poll
        current_poll_id = self.current_poll_id
        reply_id = object_id(reply_id_str)
        reply = None

        if reply_id is None:
            self.write_error(404)
            return

        for n in current_poll['post_replies']:
            if n['_id'] == reply_id:
                reply = n
                continue

        if reply is None:
            self.write_error(404)
            return

        url = 'https://alpha-api.app.net/stream/0/posts/{}/repost'.format(reply['post_id'])
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token'])
        }
        result = requests.post(url, headers=headers)
        response = result.json()

        if result.status_code == 200:
            self.write('success')
            self.finish()

            if current_user['_id'] not in reply.get('reposted_by', []):
                activity = {
                    'user_id': current_user['_id'],
                    'type': 'repost',
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                }

                polls.add_reply_repost(db=db, poll_id=current_poll_id, reply_id=reply_id, user_id=current_user['_id'])
                polls.add_reply_activity(db=db, poll_id=current_poll_id, reply_id=reply_id, activity=activity)

                action = {
                    'user_name': current_user['user_name'],
                    'user_avatar': current_user['user_avatar'],
                    'user_id': current_user['_id'],
                    'poll_id': current_poll_id,
                    'reply_id': reply['_id'],
                    'text': reply['post_text'],
                    'post_url': reply['post_url'],
                    'post_id': reply['post_id'],
                    'reply_user_name': reply['user_name'],
                    'reply_user_id': reply['user_id'],
                }
                actions.new_reply_repost(db=db, **action)

        else:
            if result.status_code == 400:
                self.set_status(400)
                self.write(response['meta']['error_message'])
                return

            self.set_status(500)
            raise Exception(result.content)


class PollsIdRepliesHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        current_user = self.current_user
        text = self.get_argument('text')
        poll_id = object_id(poll_id)

        if poll_id is None:
            self.write_error(404)
            return
        if text in (u'', ''):
            self.write_error(400)
            return
        if len(text) > 256:
            self.write_error(400)
            return

        poll = polls.find_by_id(db=db, poll_id=poll_id)
        if poll is None:
            self.send_error(404)
            return

        reply_id = ObjectId()
        poll_url = '{}/polls/{}#{}'.format(os.environ['BASE_WEB_URL'], str(poll_id), str(reply_id))
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(current_user['access_token']),
            'Content-type': 'application/json',
        }
        args = {
            'text': text,
            'reply_to': poll['post_id'],
            'annotations': [{
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                },
            }],
        }
        result = requests.post(url, data=json.dumps(args), headers=headers)

        if result.status_code != 200:
            self.write_error(500)
            raise Exception(result.content)

        response = result.json()
        post = response['data']
        reply = {
            '_id': reply_id,
            'reply_type': 'polls_reply',
            'user_id': current_user['_id'],
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'post_id': post['id'],
            'post_url': post['canonical_url'],
            'post_text': post['text'],
            'post_client_id': post['source']['client_id'],
            'post_reply_to': post['reply_to'],
            'post_thread_id': post['thread_id'],
        }
        reply = polls.add_reply(db=db, poll_id=poll_id, **reply)
        html = self.render_string('templates/polls_replies.html', poll_id=poll_id, **{ 'reply': reply})
        self.set_header('Content-Type', 'text/html')
        self.write(html)

        action = {
            'user_name': current_user['user_name'],
            'user_avatar': current_user['user_avatar'],
            'user_id': current_user['_id'],

            'question': poll['question'],
            'post_text': post['text'],
            'poll_id': poll_id,
            'post_url': post['canonical_url'],
        }
        actions.new_reply(db=db, **action)
        
        nub = {
            'html': html,
            'action': 'new_reply',
            'replyId': post['id'],
            'pollId': str(poll_id),
            'views': poll['views'],
        }
        push(channel=str(poll_id), message=nub)


class PollsIdHandler(BaseHandler):

    @require_poll
    def get(self, poll_id_str):
        db = self.db
        current_user = self.current_user
        current_poll = self.current_poll
        current_poll_id = self.current_poll_id

        # TODO: refactor
        user_has_voted = False
        user_has_starred_post = False
        user_has_reposted_post = False

        # TODO: refactor
        if current_user and current_user['_id'] in current_poll['votes_user_ids']:
            user_has_voted = True
        if current_user and current_user['_id'] in current_poll['post_starred_by']:
            user_has_starred_post = True
        if current_user and current_user['_id'] in current_poll['post_reposted_by']:
            user_has_reposted_post = True

        url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], poll_id_str)

        voted_on = ''
        if current_poll['total_votes'] > 1:
            voted_on = ' has been answered by {} people. Do you agree with them?'.format(current_poll['total_votes'])
        post_text = u'{} by @{}{}\n\n{}'.format(current_poll['question'], current_poll['user_name'], voted_on, url)
        current_poll['votes'].reverse()
        random.shuffle(current_poll['options'])
        current_poll['options_object'] = json.dumps(polls.build_options_object(current_poll['options'])).replace("'", "&#39;")

        current_poll['post_replies'] = sorted(current_poll['post_replies'], key=lambda k: k['created_at'])
        context = {
            'current_user': current_user,
            'xsrf_token': self.xsrf_token,
            'xsrf_input': self.xsrf_form_html(),
            'redirect': '/polls/{}'.format(poll_id_str),
            'user_has_voted': user_has_voted,
            'user_has_starred_post': user_has_starred_post,
            'user_has_reposted_post': user_has_reposted_post,
            'poll': current_poll,
            'poll_url': url,
            'post_text': post_text,
        }
        if current_poll.get('results_type', 'public') == 'public':
            self.render('templates/polls_{}.html'.format(current_poll['poll_type']), **context)
        else:
            self.render('templates/polls_anonymous.html', **context)

        polls.inc_views(db=db, poll_id=current_poll_id)

        if current_user is not None: # TODO and sync time is older than 15 min
            sync.thread(db=db, poll=current_poll, user=current_user)


def send_simple_message(to, subject, text):
    '''Send a text email'''
    url = "https://api.mailgun.net/v2/abrahamwilliams.mailgun.org/messages"
    auth = ("api", os.environ.get('MAILGUN_API_KEY'))
    data = {
        "from": "Polls for App.net <polls@abrahamwilliams.mailgun.org>",
        "to": to,
        "subject": subject,
        "text": text,
    }
    return requests.post(url, auth=auth, data=data)


def push(channel, message):
    '''Publish message through channels'''
    pass


def object_id(id):
    '''convert an id to an ObjectId or return None'''
    try:
        return ObjectId(id)
    except pymongo.errors.InvalidId:
        return None
