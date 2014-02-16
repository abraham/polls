import datetime
from bson.objectid import ObjectId
import os
import requests
import json
import random


def create(db, poll_id, poll_type, display_type, results_type, question, options, user_name, user_avatar, user_id, post_id, post_url):
    timestamp = datetime.datetime.utcnow()
    new_poll = {
        '_id': poll_id,
        'poll_type': poll_type,
        'display_type': display_type,
        'results_type': results_type,
        'question': question,
        'options': [],
        'votes': [],
        'total_votes': 0,
        'votes_user_ids': [],

        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_cover': None,
        'user_id': user_id,

        'created_at': timestamp,
        'updated_at': timestamp,
        'active_at': timestamp,
        'synced_at': timestamp,
        'views': 1,
        'status': 'active',

        'post_id': post_id,
        'post_url': post_url,
        'post_starred_by': [],
        'post_reposted_by': [],
        'post_replies': [],
    }

    for option in options:
        new_poll['options'].append({
            '_id': ObjectId(),
            'display_text': option,
            'votes': 0,
        })

    db.polls.insert(new_poll)
    return new_poll


def vote(db, poll_id, option_id, user_id, user_name, user_avatar, post_id=None, post_url=None):
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': poll_id,
        'votes_user_ids': {'$ne': user_id},
        'options._id': option_id,
    }
    mutation = {
        '$set': {
            'active_at': timestamp,
            'updated_at': timestamp,
        },
        '$inc' : {
            'total_votes' : 1,
            'options.$.votes': 1,
        },
        '$push': {
            'votes': {
                '_id': ObjectId(),
                'user_id': user_id,
                'user_name': user_name,
                'option_id': option_id,
                'user_avatar': user_avatar,
                'created_at': timestamp,
                'post_id': post_id,
                'post_url': post_url,
            }
        },
        '$addToSet': {
            'votes_user_ids': user_id,
        }
    }
    db.polls.update(query, mutation)


def vote_anonymous(db, poll_id, option_id, user_id):
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': poll_id,
        'votes_user_ids': {'$ne': user_id},
        'options._id': option_id,
    }
    mutation = {
        '$set': {
            'active_at': timestamp,
            'updated_at': timestamp,
        },
        '$inc' : {
            'total_votes' : 1,
            'options.$.votes': 1,
        },
        '$push': {
            'votes': {
                '_id': ObjectId(),
                'user_id': None,
                'user_name': 'Anonymous',
                'option_id': option_id,
                'user_avatar': 'https://polls.abrah.am/img/incognito.png',
                'created_at': timestamp,
                'post_id': None,
                'post_url': None,
            }
        },
        '$addToSet': {
            'votes_user_ids': user_id,
        }
    }
    db.polls.update(query, mutation)


def find_recent(db):
    results = db.polls.find({'status': 'active'}).sort('_id', -1).limit(20)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_recent_by_user_id(db, user_id):
    results = db.polls.find({'user_id': user_id, 'status': 'active'}).sort('_id', -1).limit(20)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_active(db, limit, min_vote_count):
    query = {
        'status': 'active',
        'total_votes': {
            '$gt': min_vote_count,
        }
    }
    results = db.polls.find(query).sort('active_at', -1).limit(limit)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_vintage(db):
    results = db.polls.find({'status': 'active'}).sort('active_at', 1).limit(20)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_top(db):
    results = db.polls.find({'status': 'active'}).sort('total_votes', -1).limit(20)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_top_viewed(db):
    results = db.polls.find({'status': 'active'}).sort('views', -1).limit(20)
    polls = []
    for poll in results:
        polls.append(poll)
    return polls


def find_by_id(db, poll_id):
    query = {
        '_id': poll_id,
        'status': 'active',
    }
    return db.polls.find_one(query)


def find_next(db, current_id):
    '''Find the next poll not voted on'''
    query = {
        '_id': {
            '$lt': current_id,
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', -1)])


def find_prev(db, current_id):
    '''Find the next poll not voted on'''
    query = {
        '_id': {
            '$gt': current_id,
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', 1)])

def find_random(db):
    query = {'status': 'active'}
    count = db.polls.find(query).count()
    rand = random.randint(0, count - 1)
    return db.polls.find(query).limit(-1).skip(rand).next()


def build_options_object(options):
    options_object = {}
    for option in options:
        _id = str(option['_id'])
        options_object[_id] = {
            '_id': _id,
            'text': option['display_text'],
            'votes': option['votes'],
        }
    return options_object


def add_to_set(db, poll_id, field, value):
    '''add a value to a set'''
    query = {
        '_id': poll_id,
    }
    mutation = {
        '$addToSet': {
            field: value,
        }
    }
    db.polls.update(query, mutation)


def set(db, poll_id, field, value):
    '''add a value to a set'''
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': poll_id,
    }
    mutation = {
        '$set': {
            field: value,
            'updated_at': timestamp,
        }
    }
    db.polls.update(query, mutation)


def inc_views(db, poll_id):
    '''Increment the views field for a user'''
    query = {
            '_id': poll_id,
        }
    mutation = {
        '$inc': {
            'views': 1,
        }
    }
    db.polls.update(query, mutation)


def add_reply(db, _id, poll_id, post_id, user_id, user_name, user_avatar, post_url, post_text, reply_type, post_client_id, post_reply_to, post_thread_id, created_at=None):
    '''Increment the views field for a user'''
    timestamp = datetime.datetime.utcnow()
    reply = {
        '_id': _id,
        'reply_type': reply_type,
        'user_id': user_id,
        'user_name': user_name,
        'user_avatar': user_avatar,
        'created_at': created_at or timestamp,
        'post_id': post_id,
        'post_url': post_url,
        'post_text': post_text,
        'post_client_id': post_client_id,
        'post_reply_to': post_reply_to,
        'post_thread_id': post_thread_id,
        'starred_by': [],
        'starred_count': 0,
        'reposted_by': [],
        'reposted_count': 0,
        'activity': [],
    }
    query = {
            '_id': poll_id,
        }
    mutation = {
        '$addToSet': {
            'post_replies': reply,
        },
    }
    db.polls.update(query, mutation)
    return reply


def add_reply_star(db, poll_id, reply_id, user_id):
    '''Increment the views field for a user'''

    query = {
        '_id': poll_id,
        'post_replies._id': reply_id,
    }

    mutation = {
        '$addToSet': {
            'post_replies.$.starred_by': user_id,
        },
        '$inc': {
            'post_replies.$.starred_count': 1,
        },
    }
    db.polls.update(query, mutation)


def add_reply_repost(db, poll_id, reply_id, user_id):
    '''Increment the views field for a user'''

    query = {
        '_id': poll_id,
        'post_replies._id': reply_id,
    }

    mutation = {
        '$addToSet': {
            'post_replies.$.reposted_by': user_id,
        },
        '$inc': {
            'post_replies.$.reposted_count': 1,
        },
    }
    db.polls.update(query, mutation)


def add_reply_activity(db, poll_id, reply_id, activity):
    '''Increment the views field for a user'''

    query = {
        '_id': poll_id,
        'post_replies._id': reply_id,
    }

    mutation = {
        '$addToSet': {
            'post_replies.$.activity': activity,
        },
    }
    db.polls.update(query, mutation)


def send_alert(channel_id, subject, poll_url):
    '''Send a new alert to ADN'''
    if os.environ.get('ADN_CHANNEL_ENABLED') not in ('True', 'true', True):
        print 'posting to channel disabled'
        print 'channel_id', channel_id, 'subject', subject, 'poll_url', poll_url
        return None

    if len(subject) > 128:
        subject = subject[:125] + u'...'

    access_token = os.environ.get('ADN_CHANNEL_ACCESS_TOKEN')
    url = 'https://alpha-api.app.net/stream/0/channels/{}/messages'.format(channel_id)
    data = {
        'machine_only': True,
        'annotations': [
            {
                "type": "net.app.core.broadcast.message.metadata",
                "value": {
                    "subject": subject,
                },
            },
            {
                "type": "net.app.core.crosspost",
                "value": {
                    "canonical_url": poll_url,
                }
            },
        ],
    }
    headers = {
        'Authorization': 'Bearer {}'.format(access_token),
        'Content-type': 'application/json',
    }
    result = requests.post(url, data=json.dumps(data), headers=headers)
    if result.status_code != 200:
        raise Exception(result.content)
