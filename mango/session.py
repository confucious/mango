import datetime
from django.contrib.sessions.backends.base import SessionBase, CreateError
from django.utils.encoding import force_unicode
from mango import database as db, old_database as olddb, OperationFailure, collection, old_collection

class SessionStore(SessionBase):
    """
    Implements MongoDB session store.
    """
    def load(self):
        now = datetime.datetime.now()
        s = db[collection].find_one({'session_key': self.session_key, 'expire_date': {'$gt': now}})
        if not s:
            s = olddb[old_collection].find_one({'session_key': self.session_key, 'expire_date': {'$gt': now}})
            if s:
                db[collection].save(s)

        try:
            return self.decode(force_unicode(s['session_data']))
        except:
            self.create()
            return {}

    def exists(self, session_key):
        if db[collection].find_one({'session_key': session_key}):
            return True
        elif olddb[old_collection].find_one({'session_key': session_key}):
            return True
        else:
            return False

    def create(self):
        while True:
            self.session_key = self._get_new_session_key()
            try:
                # Save immediately to ensure we have a unique entry in the
                # database.
                self.save(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            self._session_cache = {}
            return

    def save(self, must_create=False):
        """
        Saves the current session data to the database. If 'must_create' is
        True, a database error will be raised if the saving operation doesn't
        create a *new* entry (as opposed to possibly updating an existing
        entry).
        """
        obj = {'session_key': self.session_key,
               'session_data': self.encode(self._get_session(no_load=must_create)),
               'expire_date': self.get_expiry_date()}

        try:
            if must_create:
                db[collection].ensure_index('session_key', unique=True, ttl=3600)
                db[collection].save(obj, safe=True)
            else:
                db[collection].update({'session_key': self.session_key}, obj, upsert=True)
        except OperationFailure, e:
            if must_create:
                raise CreateError
            raise

    def delete(self, session_key=None):
        if session_key is None:
            if self._session_key is None:
                return
            session_key = self._session_key
        db.session.remove({'session_key': session_key})
