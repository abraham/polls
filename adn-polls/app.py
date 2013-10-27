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


from models import polls, users, actions
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
            self.user = users.find_by_id(db=db, user_id=ObjectId(user_id))


    def prepare(self):
        proto = self.request.headers.get('X-Forwarded-Proto', 'http')
        origin = self.request.headers.get('Origin', None)
        host = self.request.headers.get('Host', None)
        debug = os.environ.get('DEBUG') in ('True', 'true', True)

        if proto.lower() == 'https' :
            self.set_header('Strict-Transport-Security', 'max-age="31536000"; includeSubDomains')
        if proto == 'http' and not debug:
            print 'Redirecting to SSL'
            url = 'https://{}{}'.format(self.request.host, self.request.path)
            self.redirect(url)
            return
        if host is not None and not debug and host != 'polls.abrah.am':
            print 'Redirecting to polls.abrah.am'
            url = 'https://{}{}'.format('polls.abrah.am', self.request.path)
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


class mdHandler(BaseHandler):

    def get(self):
        '''Return the markdown files for terms and privacy policy'''
        import markdown2
        path = 'adn-polls/static/md{}.md'.format(self.request.path)
        html = markdown2.markdown_path(path)
        title = 'Polls for App.net'
        if self.request.path == '/terms':
            title = 'Polls Terms of Service'
        elif self.request.path == '/privacy':
            title = 'Polls Privacy Policy'
        context = {
            'unsafe_html': html,
            'title': title,
        }
        self.render('templates/md.html', **context)


class robotHandler(BaseHandler):

    def get(self):
        '''Return the markdown files for terms and privacy policy'''
        self.render('static/txt/robots.txt')


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
        existing_user = True
        if user is None:
            new_user = {
                'access_token': token['access_token'],
                'adn_id': adn_id,
                'user_name': token['username'],
                'user_avatar': token['token']['user']['avatar_image']['url'],
                'user_cover': token['token']['user']['cover_image']['url'],
            }
            user = users.create(db=db, **new_user)
            existing_user = False
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
        if existing_user == False:
            action = {
                'user_name': user['user_name'],
                'user_avatar': user['user_avatar'],
                'user_id': user['_id'],
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
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        active_polls = polls.find_active(db=db, limit=5, min_vote_count=3)
        for poll in active_polls:
            poll['votes'].reverse()
            random.shuffle(poll['options'])
            poll['options_object'] = polls.build_options_object(poll['options'])
            poll['redirect'] = '/polls/{}'.format(poll['_id'])
            poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)

        context = {
            'header_title': 'Polls for App.net',
            'header_subtitle': 'clean, simple, beautiful',
            'user_is_authed': user_is_authed,
            'active_polls': active_polls,
        }
        self.render('templates/index.html', **context)

        for poll in active_polls:
            polls.inc_views(db=db, poll_id=poll['_id'])


class ActivityHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        recent_actions = actions.find_recent(db=db)
        for action in recent_actions:
            action['created_at_human'] = momentpy.from_now(action['created_at'], fromUTC=True)
        context = {
            'header_title': 'Recent activity',
            'header_subtitle': '',
            'user_is_authed': user_is_authed,
            'recent_actions': recent_actions,
        }
        self.render('templates/actions.html', **context)


class RecentHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        recent_polls = polls.find_recent(db=db)
        for poll in recent_polls:
            poll['votes'].reverse()
            poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)
        context = {
            'header_title': 'New polls',
            'header_subtitle': 'are the latest and (maybe) greatest',
            'user_is_authed': user_is_authed,
            'recent_polls': recent_polls,
        }
        self.render('templates/list.html', **context)


class UsersIdHandler(BaseHandler):

    def get(self, user_id):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        try:
            viewed_user = users.find_by_id(db=db, user_id=ObjectId(user_id))
        except pymongo.errors.InvalidId, e:
            self.send_error(404)
            return
        if viewed_user is None:
            self.send_error(404)
            return

        recent_actions = actions.find_recent_by_user_id(db=db, user_id=ObjectId(user_id))
        for action in recent_actions:
            action['created_at_human'] = momentpy.from_now(action['created_at'], fromUTC=True)
        subtitle = u'<a href="https://alpha.app.net/{}" target="_blank"><span class="glyphicon glyphicon-link"></span></a> recent activity'
        context = {
            'header_title': u'@{}'.format(viewed_user['user_name']),
            'header_subtitle': subtitle.format(viewed_user['user_name']),
            'user_is_authed': user_is_authed,
            'recent_actions': recent_actions,
        }
        self.render('templates/actions.html', **context)
        users.inc_views(db=db, user_id=viewed_user['_id'])


class ActiveHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        recent_polls = polls.find_active(db=db, limit=20, min_vote_count=2)
        for poll in recent_polls:
            poll['votes'].reverse()
            poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)
        context = {
            'header_title': 'Trending polls',
            'header_subtitle': 'are movers and shakers',
            'user_is_authed': user_is_authed,
            'recent_polls': recent_polls,
        }
        self.render('templates/list.html', **context)


class VintageHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        vintage_polls = polls.find_vintage(db=db)
        for poll in vintage_polls:
            poll['votes'].reverse()
            poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)
        context = {
            'header_title': 'Vintage polls',
            'header_subtitle': 'have not been voted on in a while',
            'user_is_authed': user_is_authed,
            'recent_polls': vintage_polls,
        }
        self.render('templates/list.html', **context)


class TopHandler(BaseHandler):

    def get(self):
        db = self.db
        user = self.user
        user_is_authed = False
        if user is not None:
            user_is_authed = True

        top_polls = polls.find_top(db=db)
        for poll in top_polls:
            poll['votes'].reverse()
            poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)
        context = {
            'header_title': 'Top polls',
            'header_subtitle': 'have (almost) ALL THE VOTES',
            'user_is_authed': user_is_authed,
            'recent_polls': top_polls,
        }
        self.render('templates/list.html', **context)


class CreateHandler(BaseHandler):

    @require_auth
    def get(self):
        context = {
            'xsrf_input': self.xsrf_form_html(),
        }
        self.render('templates/create.html', **context)


    @require_auth
    def post(self):
        self.check_xsrf_cookie()
        db = self.db
        user = self.user

        poll_id = ObjectId()
        poll_id_str = str(poll_id)
        question = self.get_argument('question')[:150]
        options = []
        for option in self.get_arguments('options'):
            if option != '':
                options.append(option[:100])

        text = u'Q: {}\n\nVote on @polls at {}/polls/{}'.format(question, os.environ['BASE_WEB_URL'], poll_id_str)
        url = 'https://alpha-api.app.net/stream/0/posts'
        headers = {
            'Authorization': 'Bearer {}'.format(user['access_token']),
        }
        args = {
            'text': text,
        }
        response = requests.post(url, data=args, headers=headers)
        if response.status_code != 200:
            print 'create error', response.body
            raise Exception
        post = response.json()

        args = {
            'poll_id': poll_id,
            'poll_type': 'multiplechoice',
            'display_type': 'donut',
            'question': question,
            'options': options,
            'user_id': user['_id'],
            'user_name': user['user_name'],
            'user_avatar': user['user_avatar'],
            'post_id': post['data']['id'],
            'post_url': post['data']['canonical_url'],

        }
        poll = polls.create(db=self.db, **args)
        self.redirect('/polls/{}'.format(poll_id_str))
        action = {
            'user_name': user['user_name'],
            'user_avatar': user['user_avatar'],
            'user_id': user['_id'],
            'question': question,
            'poll_id': poll['_id'],
            'post_url': post['data']['canonical_url'],
        }
        actions.new_poll(db=db, **action)


class PollsIdPrevHandler(BaseHandler):

    def get(self, polls_id):
        db = self.db
        user = self.user
        poll = polls.find_prev(db=db, current_id_str=polls_id)
        if poll is None:
            self.write_error(404)
            return
        url = '/polls/{}'.format(str(poll['_id']))
        self.redirect(url)


class PollsIdNextHandler(BaseHandler):

    def get(self, polls_id):
        db = self.db
        user = self.user
        poll = polls.find_next(db=db, current_id_str=polls_id)
        if poll is None:
            self.write_error(404)
            return
        url = '/polls/{}'.format(str(poll['_id']))
        self.redirect(url)


class PollsIdActionsHandler(BaseHandler):

    @require_auth
    def post(self, poll_id):
        self.check_xsrf_cookie()
        db = self.db
        user = self.user
        poll = polls.find_by_id(db=db, str_id=poll_id)
        action_id = self.get_argument('actionId')
        if poll is None:
            self.write_error(404)
            return

        url = 'https://alpha-api.app.net/stream/0/posts/{}/{}'.format(poll['post_id'], action_id)
        headers = {
            'Authorization': 'Bearer {}'.format(user['access_token'])
        }
        result = requests.post(url, headers=headers)
        response = result.json()

        if result.status_code == 200:
            self.write('success')
            if action_id == 'star':
                polls.add_to_set(db=db, poll_id=poll['_id'], field='post_starred_by', value=user['_id'])
            elif action_id == 'repost':
                polls.add_to_set(db=db, poll_id=poll['_id'], field='post_reposted_by', value=user['_id'])
            return
        else:
            if result.status_code == 400:
                self.set_status(400)
                self.write(response['meta']['error_message'])
                return

            print 'error taking action', result.content
            raise Exception(result.content)


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

        poll = polls.find_by_id(db=db, str_id=poll_id)
        if poll is not None:
            post_url = None
            option = ''
            for o in poll['options']:
                if ObjectId(option_id) == o['_id']:
                    option = o['display_text']
                    continue

            if poll['post_id'] is not None:
                text = '@{} {}'.format(poll['user_name'], option,)
                url = 'https://alpha-api.app.net/stream/0/posts'
                headers = {
                    'Authorization': 'Bearer {}'.format(user['access_token']),
                }
                args = {
                    'text': text,
                    'reply_to': poll['post_id'],
                }
                response = requests.post(url, data=args, headers=headers)
                if response.status_code != 200:
                    print 'create error', response.content
                    raise Exception(response.content)
                post = response.json()
                post_url = post['data']['canonical_url']

            action = {
                'user_name': user['user_name'],
                'user_avatar': user['user_avatar'],
                'user_id': user['_id'],
                'question': poll['question'],
                'poll_id': poll['_id'],
                'option': option,
                'post_url': post_url,
            }
            actions.new_vote(db=db, **action)


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
        user_has_starred_post = False
        user_has_reposted_post = False

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
        if user_is_authed and user['_id'] in poll['post_starred_by']:
            user_has_starred_post = True
        if user_is_authed and user['_id'] in poll['post_reposted_by']:
            user_has_reposted_post = True

        url = '{}/polls/{}'.format(os.environ['BASE_WEB_URL'], str(poll['_id']))

        voted_on = ''
        if poll['total_votes'] > 1:
            voted_on = ' has been answered by {} people. Do you agree with them?'.format(poll['total_votes'])
        post_text = u'{} by @{}{}\n\n{}'.format(poll['question'], poll['user_name'], voted_on, url)
        poll['votes'].reverse()
        random.shuffle(poll['options'])
        poll['created_at_human'] = momentpy.from_now(poll['created_at'], fromUTC=True)

        context = {
            'xsrf_token': self.xsrf_token,
            'xsrf_input': self.xsrf_form_html(),
            'redirect': '/polls/{}'.format(poll['_id']),
            'user_is_authed': user_is_authed,
            'user_has_voted': user_has_voted,
            'user_has_starred_post': user_has_starred_post,
            'user_has_reposted_post': user_has_reposted_post,
            'poll': poll,
            'options_object': polls.build_options_object(poll['options']),
            'post_text': post_text,
        }
        self.render('templates/polls.html', **context)

        polls.inc_views(db=db, poll_id=poll['_id'])
