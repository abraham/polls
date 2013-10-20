from functools import wraps


from models import users


def require_auth(f):

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.user is None:
            args = {
                'redirect': self.request.path,
            }
            self.set_json_cookie(args)
            self.redirect('/auth/redirect')
        else :
            f(self, *args, **kwargs)

    return wrapper
