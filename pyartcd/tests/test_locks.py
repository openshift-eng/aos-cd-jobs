from unittest import TestCase
from unittest.mock import patch

from pyartcd.locks import LockManager, LOCK_POLICY, Lock


class TestLocks(TestCase):
    def test_lock_policy(self):
        lock: Lock = Lock.BUILD
        lock_policy: dict = LOCK_POLICY[lock]
        self.assertEqual(lock_policy['retry_count'], 36000)
        self.assertEqual(lock_policy['retry_delay_min'], 0.1)
        self.assertEqual(lock_policy['lock_timeout'], 60 * 60 * 6)

    def test_lock_name(self):
        lock: Lock = Lock.BUILD
        lock_name = lock.value.format(version='4.14')
        self.assertEqual(lock_name, 'build-lock-4.14')

    @patch("pyartcd.redis.redis_url", return_value='fake_url')
    @patch("aioredlock.algorithm.Aioredlock.__attrs_post_init__")
    def test_lock_manager(self, *_):
        lock: Lock = Lock.COMPOSE
        lm = LockManager.from_lock(lock)
        self.assertEqual(lm.retry_count, LOCK_POLICY[Lock.COMPOSE]['retry_count'])
        self.assertEqual(lm.retry_delay_min, LOCK_POLICY[Lock.COMPOSE]['retry_delay_min'])
        self.assertEqual(lm.internal_lock_timeout, LOCK_POLICY[Lock.COMPOSE]['lock_timeout'])
        self.assertEqual(lm.redis_connections, ['fake_url'])
