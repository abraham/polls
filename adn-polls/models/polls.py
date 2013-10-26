import datetime
from bson.objectid import ObjectId


def create(db, poll_id, poll_type, display_type, question, options, user_name, user_avatar, user_id, post_id, post_url):
    timestamp = datetime.datetime.utcnow()
    new_poll = {
        '_id': poll_id,
        'poll_type': poll_type,
        'display_type': display_type,
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
        'views': 1,
        'status': 'active',

        'post_id': post_id,
        'post_url': post_url,
        'post_starred_by': [],
        'post_reposted_by': [],
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
        '_id': ObjectId(poll_id),
        'votes_user_ids': {'$ne': user_id},
        'options._id': ObjectId(option_id),
    }
    mutation = {
        '$set': {
            'active_at': timestamp,
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


def find_recent(db):
    results = db.polls.find({'status': 'active'}).sort('created_at', -1).limit(20)
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


def find_by_id(db, str_id):
    query = {
        '_id': ObjectId(str_id),
        'status': 'active',
    }
    return db.polls.find_one(query)


def find_next(db, current_id_str):
    '''Find the next poll not voted on'''
    query = {
        '_id': {
            '$lt': ObjectId(current_id_str),
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', -1)])


def find_prev(db, current_id_str):
    '''Find the next poll not voted on'''
    query = {
        '_id': {
            '$gt': ObjectId(current_id_str),
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', 1)])


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
