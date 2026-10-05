
idioms = {
     "duckdb": {
          "date subtraction": "Use column - INTERVAL 'X days/months'. NEVER use DATE_SUB() or DATEADD().",
          "date truncation": "Use DATE_TRUNC('month', column).",
          "reserved keywords": "Always wrap the column name \"DATE\" in double quotes to avoid Binder Errors.",
          "string concatenation": "Use the || operator or CONCAT().",
          "boolean aggregation": "Use FILTER clauses or BOOL_OR() / BOOL_AND() for cleaner logic.",
          "nested aggregates": "Avoid nested aggregates\u2014never wrap MAX/MIN inside SUM/AVG/etc. Example: WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX(\"DATE\")) AS year FROM injectors), yearly_totals AS (...), yoy AS (...) SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)",
          "cte helpers": "Use CTEs to capture helper scalars (like current_year via MAX(\"DATE\")) before performing group aggregations. For example:\n    WITH current_year AS (SELECT EXTRACT(YEAR FROM MAX(\"DATE\")) AS year FROM injectors),\n         yearly_totals AS (...),\n         yoy AS (...)\n    SELECT ... FROM ... WHERE YEAR = (SELECT year FROM current_year)"
     }
}

