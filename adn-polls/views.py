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
