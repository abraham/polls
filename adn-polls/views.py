from tornado.web import UIModule
from tornado import template


class NavbarUser(UIModule):

    def render(self, current_user):
        '''Render the "@username" dropdown for the navbar'''
        if current_user is None:
            return '<li><a href="/auth/redirect?redirect={}">Sign in with App.net</a></li>'.format(self.request.path)
        else:
            context = {
                'current_user': current_user,
            }
            return self.render_string('templates/navbar_user.html', **context)


class Actions(UIModule):

    def render(self, action):
        '''Render actions from with templates'''
        context = {
            'action': action,
        }
        path = 'templates/actions_{}.html'.format(action['type'])
        return self.render_string(path, **context)


class PollsStar(UIModule):

    def render(self, poll_id, user_id, starred_by):
        '''Render a star to star a post'''
        context = {
            'poll_id': poll_id,
            'is_starred': user_id in starred_by,
        }
        return self.render_string('templates/polls_star.html', **context)


class PollsRepost(UIModule):

    def render(self, poll_id, user_id, reposted_by):
        '''Render a repost a poll icon'''
        context = {
            'poll_id': poll_id,
            'is_reposted': user_id in reposted_by,
        }
        return self.render_string('templates/polls_repost.html', **context)
