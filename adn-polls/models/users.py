import datetime
from bson.objectid import ObjectId
import time


def create(db, access_token, adn_id, user_name, user_avatar, user_avatar_is_default, user_cover, user_cover_is_default, user_text, user_full_name):
    '''Create a new user'''
    timestamp = datetime.datetime.utcnow()
    new_user = {
        '_id': ObjectId(),
        'access_token': access_token,
        'adn_id': adn_id,
        'user_avatar': user_avatar,
        'user_avatar_is_default': user_avatar_is_default,
        'user_cover': user_cover,
        'user_cover_is_default': user_cover_is_default,
        'user_name': user_name,
        'user_text': user_text,
        'user_full_name': user_full_name,

        'polls_count': 0,
        'votes_count': 0,

        'created_at': timestamp,
        'active_at': timestamp,
        'updated_at': timestamp,
        'views': 1,
    }
    db.users.insert(new_user)
    return new_user


def update(db, user_id, access_token, user_name, user_avatar, user_avatar_is_default, user_cover, user_cover_is_default, user_text, user_full_name):
    '''Update an existing users info'''
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': user_id,
    }
    mutation = {
        '$set': {
            'access_token': access_token,
            'user_name': user_name,
            'user_avatar': user_avatar,
            'user_avatar_is_default': user_avatar_is_default,
            'user_cover': user_cover,
            'user_cover_is_default': user_cover_is_default,
            'user_text': user_text,
            'user_full_name': user_full_name,

            'active_at': timestamp,
            'updated_at': timestamp,
        }
    }
    db.users.update(query, mutation)


def find_by_adn_id(db, adn_id):
    '''Find an existing user by their ADN id'''
    query = {
        'adn_id': adn_id,
    }
    return db.users.find_one(query)


def find_by_id(db, user_id):
    '''Find an existing user by their id'''
    query = {
        '_id': user_id,
    }
    return db.users.find_one(query)


def find_recent(db):
    '''Find all users'''
    all_users = []
    for user in db.users.find().sort('active_at', -1).limit(100):
        all_users.append(user)
    return all_users


def inc_views(db, user_id):
    '''Increment the views field for a user'''
    query = {
        '_id': user_id,
    }
    mutation = {
        '$inc': {
            'views': 1,
        }
    }
    db.users.update(query, mutation)


def inc_votes_count(db, user_id):
    '''Increment the votes_count field for a user'''
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': user_id,
    }
    mutation = {
        '$set': {
            'active_at': timestamp,
            'updated_at': timestamp,
        },
        '$inc': {
            'votes_count': 1,
        }
    }
    db.users.update(query, mutation)


def inc_polls_count(db, user_id):
    '''Increment the polls_count field for a user'''
    timestamp = datetime.datetime.utcnow()
    query = {
        '_id': user_id,
    }
    mutation = {
        '$set': {
            'active_at': timestamp,
            'updated_at': timestamp,
        },
        '$inc': {
            'polls_count': 1,
        }
    }
    db.users.update(query, mutation)
