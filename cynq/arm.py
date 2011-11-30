from cynq.error import Error

#important! do not expect these to change during execution!  need to get that in the docs (if you do change them those changes likey won't be honored)
 
# inherit from this to specify your cynq config

ATTR_COMPONENTS = ('rpushed', 'rpulled', 'shared')

class Arm(object):

    # overrideable specs
    rpushed = ()  # list of items that are generated by this remote and can never be written to this remote
    rpulled = ()  # lsit of items that are written to this remote and are never generated by this remote
    shared = ()  # list of items that can be written by both sides
    key = None  # the key attribute to use when comparing

    # private methods
    def __init__(self, api, local, snapshot):
        super(Arm,self).__init__()
        for conf in ATTR_COMPONENTS:
            setattr(self, conf, set(getattr(self.__class__, conf, ())))
        self.key = self.__class__.key
        attrs_set = set(attr for conf in ATTR_COMPONENTS for attrs in getattr(self, conf) for attr in attrs)
        attrs_set.discard(self.key)
        self.attrs_without_key = attrs_set
        self.attrs = self.attrs_with_key = set(list(attrs_set) + [self.key])
        self._assert_valid_spec()
        self.key_remotely_generated = self.key in self.remotely_generated
        self.stores = (api, local, snapshot)
        self.api = api
        self.local = local
        self.snapshot = snapshot
        #assign arm to 

    def _assert_valid_spec(self):
        individual_sum = sum(len(getattr(self,conf)) for conf in ATTR_COMPONENTS)
        set_sum = len(self.attrs)
        if individual_sum != set_sum:
            raise Error("Spec doesn't make sense -- there is overlap in the attrs")
        if self.key and self.key not in self.attrs:
            raise Error("Spec doesn't make sense -- key not in set of possible attrs")
        if not self.key:
            raise Error("Gotta specify a key dude!")

    def _pre_cynq(self, master):
        if any
        self.

    def _cynq(self, master):
        _pre_arm_cynq(self, master)

        outgoing_changeset = ChangeSet(self).build(self.local, self.snapshot)
        incoming_changeset = ChangeSet(self).build(self.api, self.snapshot)
        self.api.apply_changes(outgoing_changeset.subtract(incoming_changeset))

        outgoing_changeset = ChangeSet(self).build(self.local, self.snapshot)
        incoming_changeset = ChangeSet(self).build(self.api, self.snapshot) 
        self.local.apply_changes(incoming_changeset.subtract(outgoing_changeset))

        _post_arm_cynq(self, master)

