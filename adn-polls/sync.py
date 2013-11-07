'''
Sync data from ADN
'''

import os
import json
import pymongo.errors
import urllib
import requests
import time
from bson.objectid import ObjectId
import dateutil.parser
import datetime

from models import polls, users, actions


def thread(db, poll, user):
    '''take a poll and sync replies from ADN'''
    if os.environ['ADN_SYNC_ENABLED'] not in (True, 'True', 'true'):
        print 'WARNING: syncing with ADN is disabled'
        return

    now = datetime.datetime.utcnow()
    delta = now - poll['synced_at']
    if delta < datetime.timedelta(minutes=15):
        print 'INFO: sync has not expired'
        return

    new_replies = {}
    existing_replies = {}
    new_adn_users = {}
    existing_users = {}

    args = {
        'count': 200,
    }
    url = 'https://alpha-api.app.net/stream/0/posts/{}/replies?{}'.format(poll['post_id'], urllib.urlencode(args))
    headers = {
        'Authorization': 'Bearer {}'.format(user['access_token']),
    }
    request = requests.get(url, data=args, headers=headers)
    if request.status_code != 200:
        raise Exception(request.content)
    response = request.json()

    if len(response['data']) <= 1:
        print 'sync.thread: no replies found'
        polls.set(db=db, poll_id=poll['_id'], field='synced_at', value=now)
        return

    existing_replies = existing_replies_obj(poll['post_replies'])
    existing_replies['adn_ids'].append(poll['post_id'])
    new_replies = new_replies_obj(response['data'], existing_replies)

    if len(new_replies['adn_ids']) == 0:
        print 'sync.thread: no new replies found'
        polls.set(db=db, poll_id=poll['_id'], field='synced_at', value=now)
        return

    replies_adn_users = replies_adn_user_ids_obj(new_replies)
    existing_users = users.find_by_adn_ids(db=db, adn_ids=replies_adn_users['adn_ids'])

    new_ids = set(replies_adn_users['adn_ids']).difference(existing_users['adn_ids'])
    for adn_id in new_ids:
        if adn_id not in existing_users['adn_ids']:
            adn = replies_adn_users[adn_id]
            new_user = {
                'access_token': None,
                'user_type': 'profile',
                'adn_id': adn_id,
                'user_name': adn['username'],
                'user_avatar': adn['avatar_image']['url'],
                'user_avatar_is_default': adn['avatar_image']['is_default'],
                'user_cover': adn['cover_image']['url'],
                'user_cover_is_default': adn['cover_image']['is_default'],
                'user_text': None,
                'user_full_name': adn['name'],
            }
            if adn.get('description', None) is not None:
                new_user['user_text'] = adn['description']['text']
            saved_user = users.create(db=db, **new_user)
            print 'new user', saved_user['_id'], saved_user['adn_id']
            existing_users[saved_user['adn_id']] = saved_user

    for post_id in new_replies['adn_ids']:
        post = new_replies[post_id]
        user = existing_users[post['user']['id']]

        if post.get('is_deleted', False) == True:
            print 'INFO: skipping deleted post'
            continue

        reply = {
            'reply_type': 'polls_reply',
            'user_id': user['_id'],
            'user_name': user['user_name'],
            'user_avatar': user['user_avatar'],
            'post_id': post['id'],
            'post_url': post['canonical_url'],
            'post_text': post['text'],
            'post_client_id': post['source']['client_id'],
            'post_reply_to': post['reply_to'],
            'post_thread_id': post['thread_id'],
            'created_at': dateutil.parser.parse(post['created_at']),
        }
        reply = polls.add_reply(db=db, poll_id=poll['_id'], **reply)

    polls.set(db=db, poll_id=poll['_id'], field='synced_at', value=now)
    print 'INFO: completed polls sync'

def existing_replies_obj(replies):
    '''Turn a list of replies into an object with list of ids'''
    obj = {
        'adn_ids': [],
        '_ids': [],
    }
    for reply in replies:
        obj['adn_ids'].append(reply['post_id'])
        obj['_ids'].append(reply['_id'])
        obj[reply['_id']] = reply
    obj['adn_ids'] = list(set(obj['adn_ids']))
    obj['_ids'] = list(set(obj['_ids']))
    return obj


def replies_adn_user_ids_obj(posts):
    adn_users = {
        'adn_ids': []
    }
    for post_id in posts['adn_ids']:
        adn_users[posts[post_id]['user']['id']] = posts[post_id]['user']
        adn_users['adn_ids'].append(posts[post_id]['user']['id'])
    adn_users['adn_ids'] = list(set(adn_users['adn_ids']))
    return adn_users


def new_replies_obj(replies, existing_replies):
    obj = {
        'adn_ids': [],
    }
    for post in replies:
        if post['id'] not in existing_replies['adn_ids']:
            obj['adn_ids'].append(post['id'])
            obj[post['id']] = post
    obj['_ids'] = list(set(obj['adn_ids']))
    return obj
