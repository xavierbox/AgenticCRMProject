inj_prod_locs_semantic_catalog = {
    "tables": [
        {
            "name": "injectors",
            "description": "Water injection time series. Each row contains a dated observation of water injection for a given Injector well in a given subzone and sector",
            "kind": "base",
            "columns": [
                {
                    "name": "DATE",
                    "data_type": "timestamp",
                    "description": "Injection date.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "NAME",
                    "data_type": "string",
                    "description": "Injector well identifier.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "WATER_INJECTION_VOLUME",
                    "data_type": "float",
                    "description": "Injected water volume.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "SUBZONE",
                    "data_type": "string",
                    "description": "Vertical subzone.",
                    "derived_column": False,
                    "business_rules": [
                        "Typical values: LW, RW, UW, Unique."
                    ]
                },
                {
                    "name": "SECTOR",
                    "data_type": "integer",
                    "description": "Geographic sector.",
                    "derived_column": False,
                    "business_rules": [
                        "Integer sector id."
                    ]
                },
                {
                    "name": "YEAR",
                    "data_type": "integer",
                    "description": "Year from DATE.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "MONTH",
                    "data_type": "integer",
                    "description": "Month from DATE.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "DAY",
                    "data_type": "integer",
                    "description": "Day from DATE.",
                    "derived_column": False,
                    "business_rules": []
                }
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "injectors",
                        "locations"
                    ],
                    "join_type": "inner",
                    "join_condition": "injectors.NAME = locations.NAME AND locations.WELL_TYPE = 'Injector'",
                    "description": "Join injectors to injector metadata."
                }
            ]
        },
        {
            "name": "producers",
            "description": "Production time series. Each row contains a dated observation of produced volumes (oil,gas,water) and ratios (opional) for a given producer name, sector and subzone",
            "kind": "base",
            "columns": [
                {
                    "name": "DATE",
                    "data_type": "timestamp",
                    "description": "Production date.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "NAME",
                    "data_type": "string",
                    "description": "Producer well identifier.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "LIQUID_VOLUME",
                    "data_type": "float",
                    "description": "Total produced liquid.",
                    "derived_column": False,
                    "business_rules": [
                        "Approx = WATER + OIL + GAS."
                    ]
                },
                {
                    "name": "WATER_VOLUME",
                    "data_type": "float",
                    "description": "Produced water.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "GAS_VOLUME",
                    "data_type": "float",
                    "description": "Produced gas.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "OIL_VOLUME",
                    "data_type": "float",
                    "description": "Produced oil.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "SUBZONE",
                    "data_type": "string",
                    "description": "Vertical subzone.",
                    "derived_column": False,
                    "business_rules": [
                        "Typical values: LW, RW, UW, Unique."
                    ]
                },
                {
                    "name": "SECTOR",
                    "data_type": "integer",
                    "description": "Geographic sector.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "YEAR",
                    "data_type": "integer",
                    "description": "Year from DATE.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "MONTH",
                    "data_type": "integer",
                    "description": "Month from DATE.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "DAY",
                    "data_type": "integer",
                    "description": "Day from DATE.",
                    "derived_column": False,
                    "business_rules": []
                }
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "producers",
                        "locations"
                    ],
                    "join_type": "inner",
                    "join_condition": "producers.NAME = locations.NAME AND locations.WELL_TYPE = 'Producer'",
                    "description": "Join producers to producer metadata."
                }
            ]
        },
        {
            "name": "locations",
            "description": "Data of well name, sector, well type and coordinates of the named well in each subzone.",
            "kind": "base",
            "columns": [
                {
                    "name": "NAME",
                    "data_type": "string",
                    "description": "Well identifier.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "X",
                    "data_type": "float",
                    "description": "X coordinate.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "Y",
                    "data_type": "float",
                    "description": "Y coordinate.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "SUBZONE",
                    "data_type": "string",
                    "description": "Vertical subzone.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "SECTOR",
                    "data_type": "integer",
                    "description": "Geographic sector.",
                    "derived_column": False,
                    "business_rules": []
                },
                {
                    "name": "WELL_TYPE",
                    "data_type": "string",
                    "description": "Injector or Producer.",
                    "derived_column": False,
                    "business_rules": [
                        "Allowed: Injector, Producer."
                    ]
                }
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "locations",
                        "injectors"
                    ],
                    "join_type": "left",
                    "join_condition": "locations.NAME = injectors.NAME AND locations.WELL_TYPE = 'Injector'",
                    "description": "Link injector wells."
                },
                {
                    "tables_involved": [
                        "locations",
                        "producers"
                    ],
                    "join_type": "left",
                    "join_condition": "locations.NAME = producers.NAME AND locations.WELL_TYPE = 'Producer'",
                    "description": "Link producer wells."
                }
            ]
        }
    ],
    "semantic_constraints": [
        "WELL_TYPE domain is restricted to exactly two values: 'Injector' and 'Producer'.",
        "Each well belongs to exactly one WELL_TYPE category (mutually exclusive).",
        "Well identifiers are stored in NAME and used consistently as join keys across tables.",
        "injectors.NAME joins to locations.NAME only for rows where locations.WELL_TYPE = 'Injector'.",
        "producers.NAME joins to locations.NAME only for rows where locations.WELL_TYPE = 'Producer'.",
        "All volume measures are non-negative (WATER_INJECTION_VOLUME, LIQUID_VOLUME, WATER_VOLUME, OIL_VOLUME, GAS_VOLUME).",
        "Production balance constraint: LIQUID_VOLUME is approximately WATER_VOLUME + OIL_VOLUME + GAS_VOLUME (allowing small numerical tolerance).",
        "If YEAR, MONTH, DAY are present, they should match the corresponding DATE components."
    ],
    "query_catalog": [
        {
            "id": "monthly_injection_by_subzone",
            "question": "Show monthly aggregated water injection for each subzone.",
            "tables": [
                "injectors"
            ],
            "sql": "SELECT strftime('%Y-%m', i.DATE) AS month, i.SUBZONE, SUM(i.WATER_INJECTION_VOLUME) AS total_water_injection FROM injectors i GROUP BY strftime('%Y-%m', i.DATE), i.SUBZONE ORDER BY month, i.SUBZONE;",
            "tags": [
                "time-series",
                "aggregation",
                "subzone"
            ],
            "notes": "Uses strftime('%Y-%m', DATE) for monthly aggregation."
        },
        {
            "id": "avg_distance_injector_to_closest_producer_by_sector",
            "question": "What is the average distance between an injector and its closest producer in each sector?",
            "tables": [
                "injectors",
                "locations",
                "producers"
            ],
            "sql": "WITH injector_points AS (  SELECT l.NAME AS injector_name, l.SECTOR, l.X, l.Y   FROM locations l   WHERE l.WELL_TYPE = 'Injector'), producer_points AS (  SELECT l.NAME AS producer_name, l.SECTOR, l.X, l.Y   FROM locations l   WHERE l.WELL_TYPE = 'Producer'), nearest AS (  SELECT i.SECTOR, i.injector_name,          MIN(SQRT(POWER(i.X - p.X, 2) + POWER(i.Y - p.Y, 2))) AS nearest_distance   FROM injector_points i   JOIN producer_points p ON p.SECTOR = i.SECTOR   GROUP BY i.SECTOR, i.injector_name) SELECT SECTOR, AVG(nearest_distance) AS avg_nearest_producer_distance FROM nearest GROUP BY SECTOR ORDER BY SECTOR;",
            "tags": [
                "distance",
                "spatial",
                "nearest-neighbor",
                "aggregation"
            ],
            "notes": "Distance is Euclidean using X/Y coordinates and restricted to producers in the same sector."
        },
        {
            "id": "top_injectors_by_total_injection",
            "question": "List the top 10 injectors by total injected water volume.",
            "tables": [
                "injectors"
            ],
            "sql": "SELECT i.NAME, SUM(i.WATER_INJECTION_VOLUME) AS total_injection FROM injectors i GROUP BY i.NAME ORDER BY total_injection DESC LIMIT 10;",
            "tags": [
                "ranking",
                "aggregation"
            ],
            "notes": "Useful for ranking high-impact injectors."
        },
        {
            "id": "monthly_injection_trend_by_sector",
            "question": "Track monthly water injection trends by sector.",
            "tables": [
                "injectors"
            ],
            "sql": "SELECT strftime('%Y-%m', i.DATE) AS month, i.SECTOR, SUM(i.WATER_INJECTION_VOLUME) AS total_water_injection FROM injectors i GROUP BY strftime('%Y-%m', i.DATE), i.SECTOR ORDER BY month, i.SECTOR;",
            "tags": [
                "time-series",
                "aggregation",
                "sector"
            ],
            "notes": "Uses strftime('%Y-%m', DATE) for monthly aggregation."
        },
        {
            "id": "monthly_oil_by_subzone",
            "question": "Show monthly aggregated oil production for each subzone.",
            "tables": [
                "producers"
            ],
            "sql": "SELECT strftime('%Y-%m', p.DATE) AS month, p.SUBZONE, SUM(p.OIL_VOLUME) AS total_oil_volume FROM producers p GROUP BY strftime('%Y-%m', p.DATE), p.SUBZONE ORDER BY month, p.SUBZONE;",
            "tags": [
                "time-series",
                "aggregation",
                "subzone"
            ],
            "notes": "Uses strftime('%Y-%m', DATE) for monthly aggregation."
        },
        {
            "id": "water_cut_by_producer",
            "question": "Compute average water cut by producer.",
            "tables": [
                "producers"
            ],
            "sql": "SELECT p.NAME, AVG(CASE WHEN p.LIQUID_VOLUME = 0 THEN NULL          ELSE p.WATER_VOLUME * 1.0 / p.LIQUID_VOLUME END) AS avg_water_cut FROM producers p GROUP BY p.NAME ORDER BY avg_water_cut DESC;",
            "tags": [
                "ratio",
                "aggregation",
                "producer-performance"
            ],
            "notes": "Water cut is WATER_VOLUME / LIQUID_VOLUME with division-by-zero protection."
        },
        {
            "id": "producer_output_with_coordinates",
            "question": "Show total oil and water production per producer with coordinates.",
            "tables": [
                "producers",
                "locations"
            ],
            "sql": "SELECT p.NAME, l.X, l.Y, SUM(p.OIL_VOLUME) AS total_oil_volume, SUM(p.WATER_VOLUME) AS total_water_volume FROM producers p JOIN locations l   ON p.NAME = l.NAME AND l.WELL_TYPE = 'Producer' GROUP BY p.NAME, l.X, l.Y ORDER BY total_oil_volume DESC;",
            "tags": [
                "join",
                "spatial",
                "aggregation"
            ],
            "notes": "Ensures producer rows map only to Producer entries in locations."
        },
        {
            "id": "sector_injection_to_oil_ratio",
            "question": "Compare injected water to produced oil by sector and month.",
            "tables": [
                "injectors",
                "producers",
                "locations"
            ],
            "sql": "WITH inj AS (  SELECT strftime('%Y-%m', i.DATE) AS month, l.SECTOR,          SUM(i.WATER_INJECTION_VOLUME) AS inj_water   FROM injectors i   JOIN locations l ON i.NAME = l.NAME AND l.WELL_TYPE = 'Injector'   GROUP BY strftime('%Y-%m', i.DATE), l.SECTOR), prod AS (  SELECT strftime('%Y-%m', p.DATE) AS month, l.SECTOR,          SUM(p.OIL_VOLUME) AS prod_oil   FROM producers p   JOIN locations l ON p.NAME = l.NAME AND l.WELL_TYPE = 'Producer'   GROUP BY strftime('%Y-%m', p.DATE), l.SECTOR), keys AS (  SELECT month, SECTOR FROM inj   UNION   SELECT month, SECTOR FROM prod) SELECT k.month, k.SECTOR, i.inj_water, p.prod_oil,        CASE WHEN p.prod_oil = 0 OR p.prod_oil IS NULL THEN NULL             ELSE i.inj_water * 1.0 / p.prod_oil END AS inj_to_oil_ratio FROM keys k LEFT JOIN inj i ON i.month = k.month AND i.SECTOR = k.SECTOR LEFT JOIN prod p ON p.month = k.month AND p.SECTOR = k.SECTOR ORDER BY k.month, k.SECTOR;",
            "tags": [
                "join",
                "cross-table",
                "time-series",
                "sector",
                "ratio"
            ],
            "notes": "Uses strftime for month buckets and CASE WHEN to guard ratio division by zero."
        },
        {
            "id": "validate_well_type_domain",
            "question": "Find any rows with invalid WELL_TYPE values (should return zero rows).",
            "tables": [
                "locations"
            ],
            "sql": "SELECT l.NAME, l.WELL_TYPE FROM locations l WHERE l.WELL_TYPE IS NULL    OR l.WELL_TYPE NOT IN ('Injector', 'Producer');",
            "tags": [
                "data-quality",
                "domain-validation",
                "well-type"
            ],
            "notes": "Valid results are an empty set when domain constraints are enforced."
        }
    ]
}

## add the summary results table for liquid 

## add the rates  table for liquid 

