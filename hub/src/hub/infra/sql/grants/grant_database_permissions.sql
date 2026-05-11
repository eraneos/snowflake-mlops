-- Grant database permissions to workshop role
-- Keep ACCOUNTADMIN as co-owner
GRANT OWNERSHIP ON DATABASE {database_name} TO ROLE {role_name} COPY CURRENT GRANTS;
GRANT CREATE SCHEMA ON DATABASE {database_name} TO ROLE {role_name};
GRANT USAGE ON DATABASE {database_name} TO ROLE {role_name};
GRANT MODIFY ON DATABASE {database_name} TO ROLE {role_name};

-- Grant on all existing schemas
GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE {database_name} TO ROLE {role_name};

-- Grant on future schemas
GRANT ALL PRIVILEGES ON FUTURE SCHEMAS IN DATABASE {database_name} TO ROLE {role_name};
