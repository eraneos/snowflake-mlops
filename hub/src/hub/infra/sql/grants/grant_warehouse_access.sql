-- Grant warehouse access to workshop role
GRANT USAGE ON WAREHOUSE {warehouse_name} TO ROLE {role_name};
GRANT OPERATE ON WAREHOUSE {warehouse_name} TO ROLE {role_name};
