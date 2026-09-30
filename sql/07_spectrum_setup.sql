-- Part 6.1/6.2 - External schema and table. The Glue database already exists (created by Terraform),
-- so there is no CREATE EXTERNAL DATABASE: destroy removes it together with this table.
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '${glue_database}'
IAM_ROLE DEFAULT;

DROP TABLE IF EXISTS spectrum.sales;

CREATE EXTERNAL TABLE spectrum.sales(
    salesid    INTEGER,
    listid     INTEGER,
    sellerid   INTEGER,
    buyerid    INTEGER,
    eventid    INTEGER,
    dateid     SMALLINT,
    qtysold    SMALLINT,
    pricepaid  DECIMAL(8,2),
    commission DECIMAL(8,2),
    saletime   TIMESTAMP
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION 's3://redshift-downloads/tickit/spectrum/sales/';
