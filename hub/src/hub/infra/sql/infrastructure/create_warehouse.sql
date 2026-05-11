-- Create workshop warehouse
CREATE WAREHOUSE IF NOT EXISTS {warehouse_name}
    WITH
    WAREHOUSE_SIZE = '{warehouse_size}'
    AUTO_SUSPEND = {warehouse_auto_suspend}
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Warehouse for workshop SQL operations and data loading';
