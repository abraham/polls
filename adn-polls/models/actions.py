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


def new_vote(db, user_name, user_avatar, user_id, poll_id, question, option, post_url, post_id):
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
        'post_id': post_id,

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


def new_reply(db, user_name, user_avatar, user_id, poll_id, question, post_text, post_url):
    '''Create new_vote actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_reply',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'question': question,
        'post_text': post_text,
        'poll_id': poll_id,
        'post_url': post_url,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_poll_star(db, user_name, user_avatar, user_id, poll_id, question, post_url, post_id):
    '''Create new_vote actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_poll_star',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'question': question,
        'poll_id': poll_id,
        'post_url': post_url,
        'post_id': post_id,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_poll_repost(db, user_name, user_avatar, user_id, poll_id, question, post_url, post_id):
    '''Create new_vote actions'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'new_poll_repost',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'question': question,
        'poll_id': poll_id,
        'post_url': post_url,
        'post_id': post_id,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_reply_star(db, user_name, user_avatar, user_id, poll_id, reply_id, text, post_url, post_id):
    '''Create actions for stars on a reply'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'polls_id_replies_id_stars',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'text': text,
        'poll_id': poll_id,
        'reply_id': reply_id,
        'post_url': post_url,
        'post_id': post_id,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def new_reply_repost(db, user_name, user_avatar, user_id, poll_id, reply_id, text, post_url, post_id):
    '''Create actions for stars on a reply'''
    timestamp = datetime.datetime.utcnow()
    action = {
        '_id': ObjectId(),
        'type': 'polls_id_replies_id_reposts',
        'user_name': user_name,
        'user_avatar': user_avatar,
        'user_id': user_id,

        'text': text,
        'poll_id': poll_id,
        'reply_id': reply_id,
        'post_url': post_url,
        'post_id': post_id,

        'created_at': timestamp,
    }

    db.actions.insert(action)
    return action


def find_recent(db):
    '''Find recent actions'''
    results = db.actions.find().sort('_id', -1).limit(100)
    actions = []
    for action in results:
        actions.append(action)
    return actions


def find_recent_by_user_id(db, user_id):
    '''Find recent actions'''
    query = {
        'user_id': user_id,
    }
    results = db.actions.find(query).sort('_id', -1).limit(100)
    actions = []
    for action in results:
        actions.append(action)
    return actions
