-- Part 5 - Redshift as a data producer: aggregated result to the lab bucket as partitioned Parquet.
-- If IAM_ROLE DEFAULT is rejected by UNLOAD, replace it with IAM_ROLE '${redshift_role_arn}'.
UNLOAD ('SELECT d.year, d.month, c.catgroup, SUM(s.pricepaid) AS ingresos
         FROM sales s
         JOIN date d ON s.dateid = d.dateid
         JOIN event e ON s.eventid = e.eventid
         JOIN category c ON e.catid = c.catid
         GROUP BY d.year, d.month, c.catgroup')
TO 's3://${bucket}/gold/ventas_agregadas/'
IAM_ROLE DEFAULT
FORMAT AS PARQUET
PARTITION BY (year)
ALLOWOVERWRITE;
