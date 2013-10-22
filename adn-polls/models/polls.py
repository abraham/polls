import datetime
from bson.objectid import ObjectId


'''
poll: {
    _id: xyz,
    poll_type: multiplechoice,
    display: 'donut',
    user_name: abraham,
    user_avatar: http://,
    user_id: 123,
    post_id: 123,
    post_url: http://,
    question: what the what,
    total_votes: 4,
    options: [],
    votes: [],
    created_at: 123,
    updated_at: 123,
    active_at: 123,
    status: active,
}

votes: {
    _id: xyz,
    user_id: 123,
    user_name: 123,
    option_id: 123
    user_avatar: http://,
    created_at,
    post_id
    post_url
}

options: {
    text: 'xya',
    id: xyz,
    votes: 123
}
'''


def create(db, poll_type, display_type, question, options, user_name, user_avatar, user_id):
    timestamp = datetime.datetime.utcnow()
    new_poll = {
        '_id': ObjectId(),
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
        'status': 'active',

        'post_id': None,
        'post_url': None,
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
    results = db.polls.find({'status': 'active'}).sort('active_at', -1).limit(20)
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
            '$gt': ObjectId(current_id_str),
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', 1)])


def find_prev(db, current_id_str):
    '''Find the next poll not voted on'''
    query = {
        '_id': {
            '$lt': ObjectId(current_id_str),
        },
        'status': 'active',
    }
    return db.polls.find_one(query, sort=[('_id', -1)])


def build_options_array(options):
    options_array = [['Option','Votes']]
    for option in options:
        options_array.append([str(option['display_text']), option['votes']])
    return options_array
