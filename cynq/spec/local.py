from cynq.spec.base import BaseSpec

class LocalSpec(BaseSpec):
    name = 'local'
    # other attributes you care about that aren't sepcified in the atteached remotes, or implied by the remotes (expectation and updated_at attributes)
    pushed = ('id',)
    key = 'id'

    synced_at = 'synced_at'
    syncable_updated_at = 'syncable_updated_at'

    soft_delete = 'deleted_at'  # soft deletes are required but you can change what they're named -- keep the default unless you really have to change

    # overrideable specs
    createable = True
    updateable = True
    deleteable = True

    # format for derived attributes from remotes
    expected_format = '%(name)s_expected'


    # overrideable methods

    # since is anything-- whatever makes sense to that remote (id or time, etc)
    def all_(self): raise NotImplementedError() 

    def single_create(self, obj): raise NotImplementedError()
    def single_update(self, obj): raise NotImplementedError()

    # batch methods must return tuple of (successes, failures, untried) -- only override if you have legit batch methods, otherwise use single*
    def batch_create(self, objs): raise NotImplementedError()
    def batch_update(self, objs): raise NotImplementedError()

    # pre/post cynq hooks
    def pre_cynq(self, cynq_started_at): return True
    def post_cynq(self, cynq_started_at): return True
    def pre_cynq_phase(self, phase, remote_id, cynq_started_at): return True
    def post_cynq_phase(self, phase, remote_id, cynq_started_at): return True

    
    # private methods
    @classmethod
    def _deduce_all_attrs(kls, remote_spec_classes):
        attrs = [kls.soft_delete] + list(kls.pushed)
        for remote_kls in remote_spec_classes:
            attrs.extend(list(remote_kls._deduce_all_attrs()))
            attrs.append(kls.expected_format % {'name': remote_kls.name})
            attrs.append(kls.synced_at)
            attrs.append(kls.syncable_updated_at)
            attrs.append(kls.soft_delete)
        return tuple(set(attrs))
