import datetime
from bson.objectid import ObjectId


'''
user
@bob signed up for polls []


voted
[] @bob voted "this and the other" on "the large and barg"

poll
"the blarg marg" was asked by @bob []

'''


def new_user(db, user_name, user_avatar, user_id):
    '''Create new_user actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_user',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_vote(db, user_name, user_avatar, user_id, poll_id, question, option, post_url):
    '''Create new_vote actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_vote',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'question': question,
        'option': option,
        'poll_id': poll_id,
        'post_url': post_url,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_poll(db, user_name, user_avatar, user_id, question, poll_id, post_url):
    '''Create new_poll actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_poll',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'question': question,
        'poll_id': poll_id,
        'post_url': post_url,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def find_recent(db):
    '''Find recent actions'''
    results = db.actions.find().sort('created_at', -1).limit(100)
    actions = []
    for action in results:
        actions.append(action)
    return actions
