import unittest2
from datetime import timedelta
from cynq.connection import Connection
from cynq.stores.facet import Facet
from cynq.test import helper
from sanetime.sanetime import SaneTime

import logger
logger.configure_log()


class TestRemote(helper.TestStore):
    communal_attributes = ['attr','key']
    owned_attributes = ['owned']
    key_attribute = 'key'
    remote_expectation_attribute = 'remote_expectation'

    def create(self, obj):
        obj = super(TestRemote, self).create(obj)
        obj.change(['owned'])
        return obj

class TestLocal(helper.TestStore):
    communal_attributes = ['key','owned','attr','extra','remote_expectation']
    owned_attributes = ['id']

class TestObject(helper.TestObject):
    prepopulate_attributes = True
    attrs = ['id','key','owned','attr','extra','remote_expectation','deleted_at']

SIZE = 4
LIST = [TestObject() for i in xrange(0,SIZE)]

class ConnectionTest(helper.TestCase):
    def setUp(self):
        self.remote_store = TestRemote()
        self.remote = Facet(self.remote_store, 'key')
        self.local_store = TestLocal()
        self.local = Facet(self.local_store, 'key')
        self.conn = Connection(self.local, self.remote)

    def tearDown(self):
        pass

    def materialize_local_obj(self, deleted_at=None, remote_expectation=False, **kwargs):
        return TestObject(*self.local.outbound_attributes(), deleted_at=deleted_at, remote_expectation=remote_expectation, **kwargs)

    def materialize_remote_obj(self, deleted_at=None, remote_expectation=False):
        return TestObject(*self.remote.outbound_attributes(), **{TestRemote.remote_expectation_attribute: False})

    def test_inbound_create(self):
        remote_obj = self.materialize_remote_obj()
        self.remote_store._all = set([remote_obj])
        self.conn.inbound_create_and_update()
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.local.all_()))
        local_obj = list(self.local.all_())[0]
        self.assertTrue(local_obj.remote_expectation)
        self.assertIsNone(local_obj.deleted_at)
        self.assertIsNone(local_obj.extra)
        self.assert_store_changes(self.local_store, creates=[remote_obj], all_calls=1)
        self.assert_store_changes(self.remote_store, all_calls=1)

    def test_inbound_reanimate(self):
        remote_obj = self.materialize_remote_obj()
        local_obj = self.materialize_local_obj(deleted_at=SaneTime().to_naive_utc_datetime(), key=remote_obj.key)
        extra = local_obj.extra
        self.remote_store._all = set([remote_obj])
        self.local_store._all = set([local_obj])
        self.assertFalse(local_obj.remote_expectation)
        self.assertIsNotNone(local_obj.deleted_at)
        self.conn.inbound_create_and_update()
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.local.all_()))
        self.assertTrue(local_obj.remote_expectation)
        self.assertIsNone(local_obj.deleted_at)
        self.assertTrue(extra, local_obj.extra)
        self.assert_store_changes(self.local_store, all_calls=1)
        self.assert_store_changes(self.remote_store, all_calls=1)
        
    def test_inbound_update(self):
        remote_obj = self.materialize_remote_obj()
        local_obj = self.remote.inbound_merge(self.materialize_local_obj(remote_expectation=True, key=remote_obj.key), remote_obj)
        local_obj.syncable_updated_at = local_obj.synced_at = SaneTime().to_naive_utc_datetime()
        remote_obj.change(['attr'])
        val = remote_obj.attr
        self.assertNotEquals(remote_obj.attr, local_obj.attr)
        self.remote_store._all = set([remote_obj])
        self.local_store._all = set([local_obj])
        self.conn.inbound_create_and_update()
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.local.all_()))
        self.assertEquals(val, list(self.local.all_())[0].attr)
        self.assert_store_changes(self.local_store, all_calls=1)
        self.assert_store_changes(self.remote_store, all_calls=1)

    def test_inbound_delete(self):
        local_obj = self.materialize_local_obj(remote_expectation=True)
        local_obj.syncable_updated_at = local_obj.synced_at = SaneTime().to_naive_utc_datetime()
        self.local_store._all = set([local_obj])
        self.assertIsNone(local_obj.deleted_at)
        self.conn.inbound_delete(SaneTime().to_naive_utc_datetime())
        self.assertIsNotNone(local_obj.deleted_at)
        self.assertEquals(set([local_obj]), self.local.all_())
        self.assert_store_changes(self.local_store, all_calls=1)
        self.assert_store_changes(self.remote_store, all_calls=1)

    def test_outbound_delete(self):
        remote_obj = self.materialize_remote_obj()
        local_obj = self.remote.inbound_merge(self.materialize_local_obj(deleted_at=SaneTime().to_naive_utc_datetime(), remote_expectation=True, key=remote_obj.key), remote_obj)
        self.remote_store._all = set([remote_obj])
        self.local_store._all = set([local_obj])
        self.assertEquals(1, len(self.remote.all_()))
        self.conn.outbound_delete()
        self.assertEquals(0, len(self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([local_obj]), self.local.all_()))
        self.assert_store_changes(self.remote_store, deletes=[remote_obj], all_calls=1)
        self.assert_store_changes(self.local_store, all_calls=1)

    def test_outbound_create(self):
        local_obj = self.materialize_local_obj(owned=None)
        self.assertIsNone(local_obj.owned)
        self.local_store._all = set([local_obj])
        self.assertEquals(0, len(self.remote.all_()))
        self.conn.outbound_create_and_update()
        self.assertIsNotNone(local_obj.owned)
        self.assertTrue(self.remote.sets_seem_equal(set([local_obj]), self.local.all_()))
        self.assert_store_changes(self.remote_store, creates=[local_obj], all_calls=1)
        self.assert_store_changes(self.local_store, all_calls=1)

    def test_outbound_update(self):
        remote_obj = self.materialize_remote_obj()
        local_obj = self.remote.outbound_merge(self.materialize_local_obj(remote_expectation=True, key=remote_obj.key), remote_obj)
        local_obj.syncable_updated_at = SaneTime().to_naive_utc_datetime()
        local_obj.synced_at = local_obj.syncable_updated_at - timedelta(1)
        local_obj.change(['attr'])
        val = local_obj.attr
        self.assertNotEquals(remote_obj.attr, local_obj.attr)
        self.remote_store._all = set([remote_obj])
        self.local_store._all = set([local_obj])
        self.assertTrue(self.remote.sets_seem_equal(set([remote_obj]), self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([local_obj]), self.local.all_()))
        self.conn.outbound_create_and_update()
        self.assertTrue(self.remote.sets_seem_equal(set([local_obj]), self.remote.all_()))
        self.assertTrue(self.remote.sets_seem_equal(set([local_obj]), self.local.all_()))
        self.assertEquals(val, list(self.remote.all_())[0].attr)
        self.assert_store_changes(self.remote_store, updates=[remote_obj], all_calls=1)
        self.assert_store_changes(self.local_store, all_calls=1)



if __name__ == '__main__':
    unittest2.main()
