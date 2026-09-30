-- Part 4.2 - The same business question on both engines. Both queries use only columns of sales,
-- so Athena can answer it straight from S3 (through the Glue table created in 07_spectrum_setup.sql).

-- @engine: athena
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM ${glue_database}.sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;

-- @engine: redshift
SELECT dateid, COUNT(*) AS ventas, SUM(pricepaid) AS ingresos
FROM sales
GROUP BY dateid
ORDER BY ingresos DESC
LIMIT 10;
