-- Part 2 - The star schema with real data: sales (fact) in the center, date/event/venue around it.
SELECT
    s.salesid, s.qtysold, s.pricepaid,
    d.caldate, d.month, d.year,
    e.eventname,
    v.venuename, v.venuestate
FROM sales s
JOIN date d  ON s.dateid  = d.dateid
JOIN event e ON s.eventid = e.eventid
JOIN venue v ON e.venueid = v.venueid
LIMIT 20;
