-- Part 6.3 - Query S3 without loading anything into the workgroup.
SELECT COUNT(*) FROM spectrum.sales;

-- Join external data (Spectrum) with data already loaded in Redshift.
SELECT sp.salesid, sp.pricepaid, u.city
FROM spectrum.sales sp
JOIN users u ON sp.buyerid = u.userid
LIMIT 10;
