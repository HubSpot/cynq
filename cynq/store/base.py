from .. import Error,StoreError
from .. import logging_helper
from traceback import format_exc

#TODO: factor out spec and arm from each other (spec can be owned by stores, and arms own stores)

class BaseStore(object):
    # all the methods available to override (but should not be called directly by you ever!)
    def _all(self): raise NotImplementedError()
    
    # you can choose to implement just the bulk ones or just the single ones-- not really a need to implement both
    def _bulk_create(self, dobjs): raise NotImplementedError() # return obj,dobj tuples (obj is None on failure)    exceptions unnecessary(will get picked up in unsuccesses) 
    def _bulk_update(self, update_tuples): raise NotImplementedError()  # return success,obj,djchanges tuples (update_tuple=(obj, dchanges))    throwing exceptions unnecessary(will get picked up in unsuccesses) 
    def _bulk_delete(self, objs): raise NotImplementedError() # return success,obj tuples    exceptions unnecessary(will get picked up in unsuccesses) 

    def _single_create(self, dobj): raise NotImplementedError()  # returns new obj   throws exception on error
    def _single_update(self, obj, dchanges): raise NotImplementedError()  # returns obj with changes  throws excption on error   
    def _single_delete(self, obj): raise NotImplementedError()  # returns obj if   throws exception on error

    def _pre_cynq(self): return True
    def _post_cynq(self): return True

    def _createable(self): return True
    def _updateable(self): return True
    def _deleteable(self): return True


    # public methods
    def bulk_create(self, dobjs):
        if not self._createable(): return # avoid error reporting since this is on purpose
        try:
            for obj,dobj in self._bulk_create(dobjs):
                if obj: self._single_created(obj, dobj)
                else: self._single_create_fail(dobj)
        except NotImplementedError:
            for dobj in dobjs:
                self.single_create(dobj)

    def single_create(self, dobj):
        try:
            obj = self._single_create(dobj)
            self._single_created(obj, dobj)
        except NotImplementedError:
            raise Error("You need to implement either the _single_create or the _bulk_create")
        except StandardError as err:
            self._single_create_fail(dobj, err)


    def bulk_update(self, tuples):
        if not self._updateable(): return  # avoid error reporting since this is on purpose
        try:
            for success,obj,dchanges in self._bulk_update(tuples):
                if success: self._single_updated(obj, dchanges)
                else: self._single_update_fail(obj, dchanges)
        except NotImplementedError:
            for obj,dchanges in tuples:
                self.single_update(obj, dchanges)

    def single_update(self, obj, dchanges):
        try:
            self._single_update(obj, dchanges)
            self._single_updated(obj, dchanges)
        except NotImplementedError:
            raise Error("You need to implement either the _single_update or the _bulk_update")
        except StandardError as err:
            self._single_update_fail(obj, dchanges, err)

    def bulk_delete(self, objs):
        if not self._deleteable(): return # avoid error reporting since this is on purpose
        try:
            for success,obj in self._bulk_delete(objs):
                if success: self._single_deleted(obj)
                else: self._single_delete_fail(obj)
        except NotImplementedError:
            for obj in objs:
                self.single_delete(obj)

    def single_delete(self, obj):
        try:
            self._single_delete(obj)
            self._single_deleted(obj)
        except NotImplementedError:
            raise Error("You need to implement either the _single_delete or the _bulk_delete")
        except StandardError as err:
            self._single_delete_fail(obj, err)

    def apply_changeset(self, changeset):
        self.bulk_create(changeset.creates.values())
        self.bulk_update((self.hash_[t[0]],t[1]) for t in changeset.updates.iteritems())
        self.bulk_delete(self.hash_[key] for key in changeset.deletes)
        self.bulk_create(changeset.keyless_creates.values())

    def generate_update_trigger(self, obj):
        def trigger(new_key_value):
            setattr(obj, self.key, new_key_value)
            self.bulk_update([(obj, {self.key : new_key_value})])
        return trigger


    #private methods
    def __init__(self):
        super(BaseStore, self).__init__()
        self.arm, self.type_, self.spec = None,None,None # will get set by owning arm during cynq setup
        self._clear_cache()
        self.changes = [0,0,0,0,0,0] #success/fails for create/update/delete

    def with_arm(self, arm, type_):
        self.arm = arm
        self.type_ = type_
        self.spec = arm.spec
        self.key = self.spec.key
        self.log = logging_helper.get_log('cynq.store.%s.%s'% (self.type_, self.spec.name))
        return self

    def _single_created(self, obj, dobj):
        self.changes[0] += 1
        self.log.debug('create | key=%s | dobj=%s | obj=%s' % (getattr(obj,self.key), dobj, obj))
        self.list_.append(obj)
        self.hash_[getattr(obj,self.key)] = obj
        if dobj.get('_keyless_update_trigger'): dobj['_keyless_update_trigger'](getattr(obj, self.key))

    def _single_updated(self, obj, dchanges):
        self.changes[2] += 1
        self.hash_[getattr(obj, self.key)] = obj
        self.log.debug('update | key=%s | dchanges=%s | obj=%s' % (getattr(obj, self.key), dchanges, obj))

    def _single_deleted(self, obj):
        self.changes[4] += 1
        self.log.debug('delete | key=%s | obj=%s' % (getattr(obj, self.key), obj))
        obj = self.hash_.pop(getattr(obj, self.key))
        self.list_.remove(obj)

    def _single_create_fail(self, dobj, err=None):
        self.changes[1] += 1
        self.log.error('create failure | dobj=%s | err=%s' % (dobj, format_exc(err)))
        self._excessive_failure_check()

    def _single_update_fail(self, obj, dchanges, err=None):
        self.changes[3] += 1
        self.log.error('update failure | dchanges=%s | key=%s | obj=%s | err=%s' % (dchanges, getattr(obj, self.key), obj, format_exc(err)))
        self._excessive_failure_check()

    def _single_delete_fail(self, obj, err=None):
        self.changes[5] += 1
        self.log.error('delete failure | key=%s | obj=%s | err=%s' % (getattr(obj, self.key), obj, format_exc(err)))
        self._excessive_failure_check()

    def _get_list(self):
        if self._list is None:
            self._list = self._all()
        return self._list
    list_ = property(_get_list)

    def _get_hash(self):
        if self._hash is None:
            self._hash = dict((getattr(o,self.key),o) for o in self.list_ if hasattr(o,self.key))
        return self._hash
    hash_ = property(_get_hash)

    def _clear_cache(self):
        self._list = None
        self._hash = None

    def _excessive_failure_check(self):
        attempts = sum(self.changes)
        fails = sum(self.changes[i] for i in xrange(len(self.changes)) if i%2==0)
        if attempts <= 2: return
        if fails > int(attempts/float(attempts)**0.5+1):
            raise StoreError("Too many failures on this store for this cynq | store=%s | changes=%s"%(self, self.changes))

