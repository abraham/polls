from tornado.web import UIModule
from tornado import template
import momentpy
from twitter_text import Autolink


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


class PollsIdRepliesIdStars(UIModule):

    def render(self, poll_id, reply_id, user_id, starred_by):
        '''Render a star to star a post'''
        context = {
            'poll_id': poll_id,
            'reply_id': reply_id,
            'is_starred': user_id in starred_by,
        }
        return self.render_string('templates/polls_id_replies_id_stars.html', **context)


class PollsIdRepliesIdReposts(UIModule):

    def render(self, poll_id, reply_id, user_id, reposted_by):
        '''Render a star to star a post'''
        context = {
            'poll_id': poll_id,
            'reply_id': reply_id,
            'is_reposted': user_id in reposted_by,
        }
        return self.render_string('templates/polls_id_replies_id_reposts.html', **context)


class PollsRepost(UIModule):

    def render(self, poll_id, user_id, reposted_by):
        '''Render a repost a poll icon'''
        context = {
            'poll_id': poll_id,
            'is_reposted': user_id in reposted_by,
        }
        return self.render_string('templates/polls_repost.html', **context)


class PollsReplies(UIModule):

    def render(self, poll_id, reply):
        '''Render actions from with templates'''
        context = {
            'reply':    reply,
            'poll_id':  poll_id,
        }
        path = 'templates/polls_replies.html'
        return self.render_string(path, **context)


class RepliesList(UIModule):

    def render(self, poll):
        '''Render actions from with templates'''
        context = {
            'replies': poll.get('post_replies', []),
            'poll_id': poll['_id'],
        }
        path = 'templates/mod_replies_list.html'
        return self.render_string(path, **context)


class RepliesForm(UIModule):

    def render(self, poll, redirect, current_user):
        '''Render actions from with templates'''
        context = {
            'synced_at': poll['synced_at'],
            'poll_id': poll['_id'],
            'post_id': poll['post_id'],
            'user_name': poll['user_name'],
            'redirect': redirect,
            'current_user': current_user,
        }
        path = 'templates/mod_replies_form.html'
        return self.render_string(path, **context)


class VotesFacepile(UIModule):

    def render(self, poll):
        '''Render actions from with templates'''
        context = {
            'total_votes': poll['total_votes'],
            'votes': poll['votes'][:100],
        }
        path = 'templates/mod_votes_facepile.html'
        return self.render_string(path, **context)


class GraphDonut(UIModule):

    def render(self, poll):
        '''Render actions from with templates'''
        context = {
            'poll_id': poll['_id'],
            'options': poll['options_object'],
            'total_votes': poll['total_votes'],
        }
        path = 'templates/mod_graph_donut.html'
        return self.render_string(path, **context)


class ShareDropdown(UIModule):

    def render(self, poll, poll_url):
        '''Render actions from with templates'''
        context = {
            'poll_url': poll_url,
            'question': poll['question'],
        }
        path = 'templates/mod_share_dropdown.html'
        return self.render_string(path, **context)


class VotesComplete(UIModule):

    def render(self, poll, current_user):
        '''Render actions from with templates'''
        context = {
            'poll_id': poll['_id'],
            'poll_user_id': poll['user_id'],
            'user_name': poll['user_name'],
            'post_starred_by': poll['post_starred_by'],
            'post_reposted_by': poll['post_reposted_by'],
            'current_user_id': current_user['_id']
        }
        path = 'templates/mod_votes_complete.html'
        return self.render_string(path, **context)


def moment(self, date):
    return momentpy.from_now(date, from_utc=True)


def link_text(self, text):
    '''Link text'''
    text = text.replace('\n', '<br />')
    tt = Autolink(text)
    options = {
        'username_url_base': 'https://alpha.app.net/',
        'hashtag_url_base': 'https://alpha.app.net/hashtags/',
        'cashtag_url_base': 'https://app.net/search/?type=posts&q=$',
        # 'supress_lists': True,
        # 'url_target': '_blank',
        'url_class': 'external',
        'list_class': 'external',
        'username_class': 'external',
        'cashtag_class': 'external',
        'hashtag_class': 'external',

    }
    return tt.auto_link(options)
