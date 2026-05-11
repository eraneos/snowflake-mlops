-- Create compute pool
CREATE COMPUTE POOL IF NOT EXISTS {pool_name}
    MIN_NODES = {min_nodes}
    MAX_NODES = {max_nodes}
    INSTANCE_FAMILY = {instance_family}
    AUTO_RESUME = TRUE
    AUTO_SUSPEND_SECS = {auto_suspend_secs}
    COMMENT = '{comment}';
