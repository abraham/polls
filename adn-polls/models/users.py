import datetime
from bson.objectid import ObjectId
import time


'''
user: {
    _id: 123,
    user_name: abraham,
    user_image: http://,
    user_cover: http://,
    adn_id: 123,
    access_token: 123,

    created_at: 123,
    active_at: 123,
    updated_at: 123,
}
'''


def create(db, access_token, adn_id, user_name, user_avatar, user_cover):
    '''Create a new user'''
    timestamp = datetime.datetime.utcnow()
    new_user = {
        '_id': ObjectId(),
        'access_token': access_token,
        'adn_id': adn_id,
        'user_avatar': user_avatar,
        'user_cover': user_cover,
        'user_name': user_name,

        'created_at': timestamp,
        'active_at': timestamp,
        'updated_at': timestamp,
    }
    db.users.insert(new_user)
    return new_user


def update(db, user_id, access_token, user_name, user_avatar, user_cover):
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
            'user_cover': user_cover,

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
        '_id': ObjectId(user_id),
    }
    return db.users.find_one(query)
