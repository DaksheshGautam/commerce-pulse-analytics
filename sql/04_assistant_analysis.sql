-- @question sku_performance
WITH sku AS (
 SELECT category,sku,COUNT(*) AS line_count,
 SUM(CASE WHEN is_sales_eligible=1 THEN quantity ELSE 0 END) AS units,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
 FROM v_order_lines GROUP BY category,sku
 HAVING SUM(CASE WHEN is_sales_eligible=1 THEN quantity ELSE 0 END)>0)
SELECT *,ROW_NUMBER() OVER(ORDER BY __SKU_SORT__) AS sales_rank
FROM sku ORDER BY __SKU_SORT__;
