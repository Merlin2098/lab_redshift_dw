-- Part 1.2 - Parallel load from S3. Authorization uses the namespace default IAM role
-- (IAM_ROLE DEFAULT): no access keys and no account-specific ARN in the SQL.
COPY users
FROM 's3://redshift-downloads/tickit/allusers_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY venue
FROM 's3://redshift-downloads/tickit/venue_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY category
FROM 's3://redshift-downloads/tickit/category_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY date
FROM 's3://redshift-downloads/tickit/date2008_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY event
FROM 's3://redshift-downloads/tickit/allevents_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' TIMEFORMAT 'YYYY-MM-DD HH:MI:SS' REGION 'us-east-1';

COPY listing
FROM 's3://redshift-downloads/tickit/listings_pipe.txt'
IAM_ROLE DEFAULT
DELIMITER '|' REGION 'us-east-1';

COPY sales
FROM 's3://redshift-downloads/tickit/sales_tab.txt'
IAM_ROLE DEFAULT
DELIMITER '\t' TIMEFORMAT 'MM/DD/YYYY HH:MI:SS' REGION 'us-east-1';
