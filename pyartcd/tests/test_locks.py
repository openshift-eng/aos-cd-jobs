from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock

from pyartcd.locks import LockManager, LOCK_POLICY, Lock, run_with_lock


class TestLocks(IsolatedAsyncioTestCase):
    def test_lock_policy(self):
        lock: Lock = Lock.DISTGIT_REBASE
        lock_policy: dict = LOCK_POLICY[lock]
        self.assertEqual(lock_policy['retry_count'], 36000)
        self.assertEqual(lock_policy['retry_delay_min'], 0.1)
        self.assertEqual(lock_policy['lock_timeout'], 60 * 60 * 6)

    def test_lock_name(self):
        lock: Lock = Lock.DISTGIT_REBASE
        lock_name = lock.value.format(version='4.14')
        self.assertEqual(lock_name, 'distgit-rebase-lock-4.14')

    @patch("pyartcd.redis.redis_url", return_value='fake_url')
    @patch("aioredlock.algorithm.Aioredlock.__attrs_post_init__")
    def test_lock_manager(self, *_):
        lock: Lock = Lock.COMPOSE
        lm = LockManager.from_lock(lock)
        self.assertEqual(lm.retry_count, LOCK_POLICY[Lock.COMPOSE]['retry_count'])
        self.assertEqual(lm.retry_delay_min, LOCK_POLICY[Lock.COMPOSE]['retry_delay_min'])
        self.assertEqual(lm.internal_lock_timeout, LOCK_POLICY[Lock.COMPOSE]['lock_timeout'])
        self.assertEqual(lm.redis_connections, ['fake_url'])

    @patch("pyartcd.locks.LockManager.from_lock", return_value=AsyncMock)
    async def test_run_with_lock(self, mocked_lm):
        mocked_cm = AsyncMock()
        mocked_cm.__aenter__ = AsyncMock()
        mocked_cm.__aexit__ = AsyncMock()

        mocked_lm.return_value = AsyncMock()
        mocked_lm.return_value.is_locked = AsyncMock()
        mocked_lm.return_value.lock.return_value = mocked_cm

        task = AsyncMock()

        # Do not check if locked: just run the task
        await run_with_lock(
            coro=task(1, 2, 3),
            lock=Lock.DISTGIT_REBASE,
            lock_name='bogus'
        )
        task.assert_awaited_once_with(1, 2, 3)

        # Check if locked, is_locked = False: task gets run
        task.reset_mock()
        mocked_lm.return_value.is_locked.return_value = False
        await run_with_lock(
            coro=task(1, 2, 3),
            lock=Lock.DISTGIT_REBASE,
            lock_name='bogus',
            check_if_locked=True
        )
        task.assert_awaited_once_with(1, 2, 3)

        # Check if locked, is_locked = True: task not run
        task.reset_mock()
        mocked_lm.return_value.is_locked.return_value = True
        await run_with_lock(
            coro=task(1, 2, 3),
            lock=Lock.DISTGIT_REBASE,
            lock_name='bogus',
            check_if_locked=True
        )
        task.assert_not_awaited()
