-- Part 7 - COPY with a role that has no S3 permissions: the error is about the role, not the SQL or the data.
-- @expect-error
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE '${no_permissions_role_arn}'
DELIMITER '|' REGION 'us-east-1';

-- Diagnose. Row-level load errors show up here; a permission error may only appear in the query history.
SELECT * FROM sys_load_error_detail ORDER BY start_time DESC LIMIT 5;

SELECT query_id, status, error_message
FROM sys_query_history
WHERE query_text LIKE 'COPY users%'
ORDER BY start_time DESC
LIMIT 5;

-- Fix: same COPY with the default role. users was already loaded in Part 1, so empty it first.
TRUNCATE users;

COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';
