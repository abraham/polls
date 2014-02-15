from functools import wraps
import pymongo
from bson.objectid import ObjectId


from models import users, polls


def require_auth(f):

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.current_user is None:
            args = {
                'redirect': self.request.path,
            }
            self.set_json_cookie(args)
            self.redirect('/auth/redirect')
        else :
            f(self, *args, **kwargs)

    return wrapper


def require_poll(f):

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        db      = self.db
        poll_id = object_id(args[0])

        if poll_id is None:
            self.write_error(404)
            return

        poll = polls.find_by_id(db=db, poll_id=poll_id)

        if poll is None:
            self.write_error(404)
            return

        self.current_poll       = poll
        self.viewed_poll        = poll
        self.current_poll_id    = poll_id
        self.viewed_poll_id     = poll_id
        f(self, *args, **kwargs)

    return wrapper


def require_user(f):

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        db      = self.db
        user_id = object_id(args[0])

        if user_id is None:
            self.write_error(404)
            return

        user = users.find_by_id(db=db, user_id=user_id)

        if user is None:
            self.write_error(404)
            return

        self.viewed_user    = user
        self.viewed_user_id = user_id
        f(self, *args, **kwargs)

    return wrapper


def object_id(id):
    '''convert an id to an ObjectId or return None'''
    try:
        return ObjectId(id)
    except pymongo.errors.InvalidId:
        return None
