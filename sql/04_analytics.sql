-- Part 3 - Recurring BI aggregation (by month and category group).
SELECT
    d.year,
    d.month,
    c.catgroup,
    SUM(s.qtysold)             AS total_tickets_vendidos,
    SUM(s.pricepaid)           AS ingresos_totales,
    ROUND(AVG(s.pricepaid), 2) AS ticket_promedio
FROM sales s
JOIN date d     ON s.dateid  = d.dateid
JOIN event e    ON s.eventid = e.eventid
JOIN category c ON e.catid   = c.catid
GROUP BY d.year, d.month, c.catgroup
ORDER BY d.year, d.month, ingresos_totales DESC;
