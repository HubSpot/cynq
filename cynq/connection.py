import logger
from pprint import pformat
#from pprint import pprint


#TODO: need to clean up relationship with local and decouple more -- right now it is very coupled - warning-- sizeable task!
# model must have 'deleted_at', and 'exists_in_webinar' and 'exists_in_hubspot', and 'syncable_updated_at'

#TODO: need to think through more the implications of expecting the same object to come back around from the remote object
    #   definitely need to be able to incorporate extra info that comes back on creates, but should I really be expecting it to be the same exact object-- doesn't seem right
#TODO: need to guard against external outages, and trying to keep db consistent

#TODO: need to consider whether we'd only ever get info back on creaets-- currently designed to only look for info back on outbound creates-- need to document either way

#TODO: need to think about difference between a truly shared attribute that you can possible change
#         versus an attribute that is only reported on somewhere else, i.e. owned, shared, and
#         (audited? or reported? or logged? or something that designates this store cares and
#         records this particular value but will never be changing it -- right now that has to be
#         designated as 'shareable'
class Connection(object):
    def __init__(self, faceted_local, faceted_remote):
        super(Connection,self).__init__()
        self.local = faceted_local
        self.remote = faceted_remote
        self.log = logger.get_log()

    def debug(self, action, local_obj=None, remote_obj=None):
        remote_class = str(self.remote.store.__class__)
        s = '%s: %s' % (remote_class, action)
        s += local_obj and '\n==== local_obj:\n%s'%pformat(vars(local_obj)) or ''
        caring_vars = self.remote.readable_attributes() + [self.remote.remote_expectation_attribute]
        if remote_obj:
            dict_ = dict((attr,getattr(remote_obj,attr,None)) for attr in caring_vars)
            s += '\n==== remote_obj:\n%s'%pformat(dict_)
        self.log.debug(s)

    def inbound_create_and_update(self):
        for key in self.remote:
            remote_obj = self.remote[key]
            if key in self.local:
                local_obj = self.local[key]
                if local_obj.deleted_at:  
                    if not self._has_remote_expectation(local_obj): #reanimate
                        self.debug("local reanimate...", local_obj, remote_obj)
                        self.remote.merge_readables(local_obj, remote_obj)
                        local_obj.deleted_at=None
                        self._set_remote_expectation(local_obj, True)
                else: 
                    if not self._has_local_changed_since_last_sync(local_obj): #update
                        if not self.remote.readables_seem_equal(local_obj, remote_obj): # only if diff
                            self.debug("local update...", local_obj, remote_obj)
                            self.remote.merge_readables(local_obj,remote_obj)
                        self._set_remote_expectation(local_obj, True)
            else: #create
                self.debug("local create...", None, remote_obj)
                local_obj = self.local.create(remote_obj)
                local_obj.deleted_at = local_obj.synced_at = local_obj.syncable_updated_at = None
                self._set_remote_expectation(local_obj, True)

    def inbound_delete(self, synced_at):
        for local_key in (self.local - self.remote):
            local_obj = self.local[local_key]
            if not local_obj.deleted_at and self._has_remote_expectation(local_obj):
                self.debug("local delete...", local_obj)
                local_obj.deleted_at = synced_at
                self._set_remote_expectation(local_obj, False)

    def outbound_delete(self):
        for key in (self.local & self.remote):
            local_obj = self.local[key]
            if local_obj.deleted_at and self._has_remote_expectation(local_obj):
                remote_obj = self.remote[key]
                self.debug("remote delete...", local_obj, remote_obj)
                self.remote.delete(remote_obj)
                self._set_remote_expectation(local_obj, False)

    def outbound_create_and_update(self):
        for local_obj in (self.local.all_() + self.local.leftovers.values()): # include leftovers since we may also want to create them (in the case that the key isn't generated til they are created remotely)
            if not local_obj.deleted_at: 
                key = getattr(local_obj, self.remote.key_attribute, None)
                if key and key in self.remote: #update
                    remote_obj = self.remote[key]
                    if not self.remote.writeables_seem_equal(local_obj, remote_obj): # only if diff
                        self.debug("remote update...", local_obj, remote_obj)
                        self.remote.update(self.remote.merge_writeables(remote_obj, local_obj))
                        self._set_remote_expectation(local_obj, True)
                else: 
                    if not self._has_remote_expectation(local_obj): #create
                        self.debug("remote create...", local_obj)
                        new_remote_obj = self.remote.create(local_obj)
                        self.remote.merge_readables(local_obj, new_remote_obj)
                        self._set_remote_expectation(local_obj, True)

    def _has_remote_expectation(self, local_obj):
        return getattr(local_obj, self.remote.remote_expectation_attribute, False)

    def _set_remote_expectation(self, obj, value=True):
        setattr(obj, self.remote.remote_expectation_attribute, value)

    def _has_local_changed_since_last_sync(self, local_obj):
        synced_at = local_obj.synced_at
        syncable_updated_at = local_obj.syncable_updated_at
        return synced_at and syncable_updated_at and syncable_updated_at > synced_at





