from string import Template


# Redis instance where lock are stored
redis = Template('redis://:${redis_password}@${redis_host}:${redis_port}')

# This constant defines a timeout for each kind of lock, after which the lock will expire and clear itself
LOCK_TIMEOUTS = {
    'olm-bundle': 60*60*2, # 2 hours
}

# This constant defines how many times the lock manager should try to acquire the lock before giving up;
# it also defines the sleep interval between two consecutive retries, in seconds
RETRY_POLICY = {
    # olm-bundle: give up after 1 hour
    'olm_bundle': {
        'retry_count': 36000,
        'retry_delay_min': 0.1
    }
}
