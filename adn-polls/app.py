import os
import tornado
import tornado.template as template
import json
import tornado.locale
import pymongo.errors
import urllib
import requests
import time


from models import polls, users
from decorators import require_auth


def write_error(self, status_code, **kwargs):
    self.set_status(status_code)
    if status_code == 404:
        self.render('templates/404.html')
    elif status_code in (500, 503):
        self.render('templates/500.html')
    else:
        self.render('templates/500.html')


tornado.web.RequestHandler.write_error = write_error


class BaseHandler(tornado.web.RequestHandler):

    def initialize(self, db=None):
        self.db = db
        self.user = None
        self.cookie = None

        cookie = self.get_json_cookie()
        self.cookie = cookie
        user_id = cookie.get('user_id')

        if db is not None and user_id is not None:
            self.user = users.find_by_id(db=db, user_id=user_id)


    def prepare(self):
        proto = self.request.headers.get('X-Forwarded-Proto', 'http')

        if proto.lower() == 'https' :
            self.set_header('Strict-Transport-Security', 'max-age="31536000"; includeSubDomains')
        if proto == 'http' and os.environ.get('DEBUG') not in ('True', 'true', True):
            print 'Redirecting to SSL'
            url = 'https://{}{}'.format(self.request.host, self.request.path)
            self.redirect(url)


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


class AuthRedirectHandler(BaseHandler):

    def get(self):
        '''Redirect to ADN to authorize the user'''
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
        redirect = self.cookie.get('redirect', '/')
        code = self.get_argument('code', None)
        if code is None:
            self.render('templates/500.html', message="Missing code.")
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
            error = response.json()
            message = 'Unable to get access_token from ADN.'
            if error.get('error', None) is not None:
                message = error['error']
            self.render('templates/500.html', message=message)
            return

        token = response.json()
        adn_id = token['token']['user']['id']
        user = users.find_by_adn_id(db=db, adn_id=adn_id)
        if user is None:
            new_user = {
                'access_token': token['access_token'],
                'adn_id': adn_id,
                'user_name': token['username'],
                'user_avatar': token['token']['user']['avatar_image']['url'],
                'user_cover': token['token']['user']['cover_image']['url'],
            }
            user = users.create(db=db, **new_user)
        else:
            update = {
                'user_id': user['_id'],
                'access_token': token['access_token'],
                'user_name': token['username'],
                'user_avatar': token['token']['user']['avatar_image']['url'],
                'user_cover': token['token']['user']['cover_image']['url'],
            }
            users.update(db=db, **update)

        self.set_json_cookie({'user_id': str(user['_id'])})
        self.redirect(redirect)


class AuthLogoutHandler(BaseHandler):

    def get(self):
        '''Redirect to ADN to authorize the user'''
        self.clear_all_cookies()
        self.redirect('/')


class MainHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        recent_polls = polls.find_recent(db=db)
        context = {
            'user_is_authed': user_is_authed,
            'recent_polls': recent_polls,
        }
        self.render('templates/index.html', **context)


class CreateHandler(BaseHandler):

    @require_auth
    def get(self):
        context = {
            'xsrf_input': self.xsrf_form_html(),
        }
        self.render('templates/create.html', **context)


    @require_auth
    def post(self):
        db = self.db
        user = self.user
        self.check_xsrf_cookie()

        question = self.get_argument('question')[:150]
        options = []
        for option in self.get_arguments('options'):
            if option != '':
                options.append(option[:100])
        options.reverse()
        args = {
            'poll_type': 'multiplechoice',
            'display_type': 'donut',
            'question': question,
            'options': options,
            'user_id': user['_id'],
            'user_name': user['user_name'],
            'user_avatar': user['user_avatar'],

        }
        poll = polls.create(db=self.db, **args)
        str_id = str(poll['_id'])
        self.redirect('/polls/{}'.format(str_id))


class PollsIdVotesHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        user = self.user
        option_id = self.get_argument('option_id')
        # TODO: validate option_ids
        # TODO: validate user has not already voted
        args = {
            'poll_id': poll_id,
            'option_id': option_id,
            'user_id': user['_id'],
            'user_name': user['user_name'],
            'user_avatar': user['user_avatar'],

        }
        polls.vote(db=db, **args)


class PostsHandler(BaseHandler):

    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        user = self.user
        text = self.get_argument('text')

        if text in (u'', ''):
            self.write_error(400)
            return
        
        url = 'https://alpha-api.app.net/stream/0/posts'
        args = {
            'text': text,
        }
        headers = {
            'Authorization': 'Bearer {}'.format(user['access_token']),
        }
        response = requests.post(url, data=args, headers=headers)

        if response.status_code != 200:
            self.write_error(500)
            return


class PollsIdHandler(BaseHandler):

    def get(self, poll_id):
        db = self.db
        user = self.user
        user_is_authed = False
        user_has_voted = False

        if user is not None:
            user_is_authed = True

        try:
            poll = polls.find_by_id(db=db, str_id=poll_id)
        except pymongo.errors.InvalidId, e:
            self.send_error(404)
            return
        if poll is None:
            self.send_error(404)
            return

        if user_is_authed and user['_id'] in poll['votes_user_ids']:
            user_has_voted = True
        url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], str(poll['_id']))

        voted_on = ''
        if poll['total_votes'] > 1:
            voted_on = ' has been answered by {} people'.format(poll['total_votes'])
        post_text = '{} by @{}{}\n\n{}'.format(poll['question'], poll['user_name'], voted_on, url)

        context = {
            'xsrf_input': self.xsrf_form_html(),
            'redirect': '/polls/{}'.format(poll['_id']),
            'user_is_authed': user_is_authed,
            'user_has_voted': user_has_voted,
            'owner_username': poll['user_name'],
            'question': poll['question'],
            'options_array': polls.build_options_array(poll['options']),
            'options': poll['options'],
            'total_votes': poll['total_votes'],
            'poll_id': poll['_id'],
            'title': poll['question'],
            'post_text': post_text,
        }
        html = self.render('templates/polls.html', **context)
