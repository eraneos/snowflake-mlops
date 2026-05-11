-- Grant EXECUTE TASK privilege (required to run DAGs)
-- This is a global privilege that must be granted by ACCOUNTADMIN
GRANT EXECUTE TASK ON ACCOUNT TO ROLE {role_name};

-- Grant EXECUTE MANAGED TASK privilege (required for tasks running on compute pools)
GRANT EXECUTE MANAGED TASK ON ACCOUNT TO ROLE {role_name};
