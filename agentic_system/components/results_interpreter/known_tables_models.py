
# known_table_mdels.py

interpreter_semantic_catalog = {
    "tables": [
        {
            "name": "connectivity_table",
            "description": (
                "CRM injector-producer connectivity results. "
                "Each row represents one modeled injector-producer pair."
            ),
            "kind": "base",
            "columns": [
                {
                    "name": "INJECTOR",
                    "data_type": "string",
                    "description": "Injector well name (source).",
                },
                {
                    "name": "PRODUCER",
                    "data_type": "string",
                    "description": "Producer well name (sink).",
                },
                {
                    "name": "GAIN",
                    "data_type": "float",
                    "description": (
                        "Fraction of water injected at injector i recovered as "
                        "liquid production at producer j. Denoted G_ij. "
                        "Controls the modeled strength of support from the "
                        "injector to the producer."
                    ),
                },
                {
                    "name": "PRODUCER_ALLOCATION",
                    "data_type": "float",
                    "description": (
                        "Producer allocation: fraction of the producer's total "
                        "liquid production attributed to this injector. "
                        "The sum across injectors for a producer must be <= 1. "
                        "Total producer liquid production includes injection, "
                        "pressure-change and primary-depletion contributions."
                    ),
                },
                {
                    "name": "GAIN_CLASS",
                    "data_type": "string",
                    "description": (
                        "Categorical interpretation of GAIN. "
                        "GAIN < 0.05 is negligible; "
                        "GAIN in [0.05, 0.15] is low; "
                        "GAIN > 0.7 is high. "
                        "Other categories depend on the classification "
                        "implemented when this table was generated."
                    ),
                },
                {
                    "name": "DISTANCE",
                    "data_type": "float",
                    "description": "Distance between injector and producer",
                },
                
                
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "connectivity_table",
                        "simulation_quality_table",
                    ],
                    "join_type": "left",
                    "join_condition": (
                        "connectivity_table.PRODUCER = "
                        "simulation_quality_table.PRODUCER"
                    ),
                    "description": (
                        "Attach producer-model quality to each connectivity "
                        "pair. Multiple pairs may reference the same producer."
                    ),
                },
                {
                    "tables_involved": [
                        "connectivity_table",
                        "producer_model_table",
                    ],
                    "join_type": "left",
                    "join_condition": (
                        "connectivity_table.PRODUCER = "
                        "producer_model_table.PRODUCER"
                    ),
                    "description": (
                        "Attach producer production state and support "
                        "decomposition to each connectivity pair. "
                        "Producer-level values repeat across connected injectors."
                    ),
                },
            ],
        },
        {
            "name": "simulation_quality_table",
            "description": (
                "Producer-level CRM history-match quality metrics. "
                "Each row represents one producer model."
            ),
            "kind": "base",
            "columns": [
                {
                    "name": "PRODUCER",
                    "data_type": "string",
                    "description": "Producer well name.",
                },
                {
                    "name": "CORRELATION",
                    "data_type": "float",
                    "description": (
                        "Correlation between observed and simulated liquid "
                        "production time series."
                    ),
                },
                {
                    "name": "VARIANCE_RATIO",
                    "data_type": "float",
                    "description": (
                        "Ratio between simulated and observed production "
                        "variance."
                    ),
                },
                {
                    "name": "QUALITY_SCORE",
                    "data_type": "float",
                    "description": (
                        "Composite CRM history-match quality metric from "
                        "0 to 1. Higher values indicate better model quality."
                    ),
                },
                {
                    "name": "QUALITY_CLASS",
                    "data_type": "string",
                    "description": (
                        "Categorical interpretation of model quality."
                    ),
                },
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "simulation_quality_table",
                        "producer_model_table",
                    ],
                    "join_type": "left",
                    "join_condition": (
                        "simulation_quality_table.PRODUCER = "
                        "producer_model_table.PRODUCER"
                    ),
                    "description": (
                        "Combine producer-model quality with current production "
                        "state and support decomposition."
                    ),
                },
            ],
        },
        {
            "name": "producer_model_table",
            "description": (
                "Current producer-level production state and modeled "
                "production-support decomposition. "
                "Each row represents one producer."
            ),
            "kind": "base",
            "columns": [
                {
                    "name": "PRODUCER",
                    "data_type": "string",
                    "description": "Producer well name.",
                },
                {
                    "name": "current_produced_water_fraction",
                    "data_type": "float",
                    "description": (
                        "Current fraction of produced liquid that is water. "
                        "Also called water cut."
                    ),
                },
                {
                    "name": "current_produced_oil_fraction",
                    "data_type": "float",
                    "description": (
                        "Current fraction of produced liquid that is oil."
                    ),
                },
                {
                    "name": "current_volume_liquid_produced",
                    "data_type": "float",
                    "description": "Latest observed liquid production.",
                },
                {
                    "name": "current_liquid_production_due_to_depletion",
                    "data_type": "float",
                    "description": (
                        "Recent modeled liquid production attributed to "
                        "primary depletion."
                    ),
                },
                {
                    "name": "current_liquid_production_due_to_injection",
                    "data_type": "float",
                    "description": (
                        "Recent modeled liquid production attributed to "
                        "injection."
                    ),
                },
                {
                    "name": "current_liquid_production_due_to_pressure",
                    "data_type": "float",
                    "description": (
                        "Recent modeled liquid production attributed to "
                        "pressure changes."
                    ),
                },

                {
                    "name": "TAU",
                    "data_type": "float",
                    "description": (
                        "Producer-level time constant governing the modeled response "
                        "to injection support. All injector connections to this producer "
                        "share this response timescale. Smaller values indicate faster "
                        "response; larger values indicate slower response. "
                        "It is not an injector-producer-specific travel time."
                    ),
                },
                {
                    "name": "TAUP",
                    "data_type": "float",
                    "description": (
                        "Producer-level time constant governing the modeled decay of "
                        "the primary-depletion contribution. Smaller values indicate "
                        "faster decay; larger values indicate more persistent depletion "
                        "contribution."
                    ),
                },

                {
                    "name": "pressure_coefficient",
                    "data_type": "float",
                    "description": (
                        "CRM-P productivity coefficient: derivative of liquid "
                        "production with respect to bottom-hole pressure, "
                        "according to the model's pressure convention."
                    ),
                },
                {
                    "name": "total_allocation",
                    "data_type": "float",
                    "description": (
                        "Sum of PALLOCATION over all injectors connected "
                        "to this producer."
                    ),
                },
                {
                    "name": "number_supporting_injectors",
                    "data_type": "integer",
                    "description": (
                        "Number of injectors having non-negligible GAIN "
                        "(GAIN >= 0.05) to this producer."
                    ),
                },
            ],
            "relationships": [
                {
                    "tables_involved": [
                        "producer_model_table",
                        "simulation_quality_table",
                    ],
                    "join_type": "left",
                    "join_condition": (
                        "producer_model_table.PRODUCER = "
                        "simulation_quality_table.PRODUCER"
                    ),
                    "description": (
                        "Attach history-match quality to each producer's "
                        "production state and support decomposition."
                    ),
                },
            ],
        },
    ],
    "semantic_constraints": [
        (
            "GAIN and PALLOCATION have different physical meanings and "
            "must not be used interchangeably."
        ),
        "GAIN is injector-centric.",
        "PALLOCATION is producer-centric.",
        "GAIN below 0.05 is considered negligible.",
        (
            "For a balanced simulation, the sum of GAIN across producers "
            "for an injector must be <= 1."
        ),
        (
            "The sum of PALLOCATION across injectors for a producer "
            "must be <= 1."
        ),
        (
            "Produced water fraction and produced oil fraction "
            "must sum to 1."
        ),
        (
            "Joining producer-level tables to connectivity_table repeats "
            "producer-level values across injector-producer pairs. "
            "Do not sum those repeated values as field production totals."
        ),
    ],
    "query_catalog": [],
}


interpreter_semantic_context = {
    "definitions": [
        (
            "A producer is supported when one or more injectors have "
            "non-negligible GAIN to that producer."
        ),
        (
            "An injector supports producers when it has non-negligible "
            "GAIN to one or more producers."
        ),
        (
            "Injector utility is related to the sum of GAIN across the "
            "producers supported by that injector."
        ),
    ],
    "business_rules": [
        "GAIN < 0.05 is negligible.",
        (
            "A high-utility injector supports one or more producers and "
            "has total GAIN across producers approaching 1 in a balanced model."
        ),
        (
            "Model quality should be considered when assessing confidence "
            "in producer-level interpretations."
        ),
    ],
    "domain_knowledge": [
        (
            "A producer may be supported by injection while only a small "
            "fraction of its total liquid production is due to injection."
        ),
        (
            "Total producer liquid production may contain contributions "
            "from injection, depletion and pressure changes."
        ),
        (
            "total_allocation measures the fraction of producer liquid "
            "production attributable to all modeled injectors combined."
        ),
    ],
    "interpretation_guidelines": [
        (
            "Do not simply repeat table values. Identify patterns, extremes, "
            "rankings, anomalies and combinations of metrics that provide "
            "useful interpretation."
        ),
        (
            "Distinguish between direct observations, model interpretations "
            "and diagnostic hypotheses. Do not present a hypothesis as a "
            "confirmed physical mechanism."
        ),
        (
            "For injector-focused questions, examine GAIN, injector utility, "
            "number of supported producers and the distribution of "
            "connectivity across producers."
        ),
        (
            "For producer-support questions, examine "
            "number_supporting_injectors, total_allocation, PALLOCATION "
            "and the modeled injection-production contribution."
        ),
        (
            "A highly connected injector-producer relationship is "
            "characterized primarily by high GAIN."
        ),




        (
            "TAU is producer-centric. Low TAU indicates a fast modeled response "
            "to injection support for the producer, not a uniquely fast "
            "injector-producer connection."
        ),
        (
            "High GAIN to a producer with low TAU indicates strong modeled "
            "support to a fast-responding producer. It does not establish "
            "a pair-specific travel time or prove channeling."
        ),
        (
            "TAUP describes the persistence of the primary-depletion contribution. "
            "Interpret it together with the magnitude of that contribution."
        ),
        (
            "Joining producer_model_table to connectivity_table repeats TAU and "
            "TAUP across connections. These repetitions are not independent "
            "producer observations."
        ),








        (
            "A poorly supported producer may be characterized by few or "
            "no meaningful injector connections together with low "
            "total_allocation."
        ),
        (
            "A well-supported producer may have several meaningful injector "
            "connections and/or a substantial fraction of its production "
            "allocated to injection."
        ),
        (
            "A producer whose modeled injection contribution is the largest "
            "production component should be described as injection-dominated."
        ),
        (
            "A producer whose depletion contribution is the largest "
            "production component should be described as depletion-dominated."
        ),
        (
            "A producer whose pressure contribution is the largest "
            "production component should be described as pressure-dominated."
        ),
        (
            "When identifying underutilized or potentially stranded "
            "injectors, look for low injector utility and few meaningful "
            "producer connections. If actual injection rate information "
            "is unavailable, describe the conclusion as low modeled "
            "utilization rather than definitively calling the injector "
            "operationally stranded."
        ),
        (
            "For quantities without established absolute thresholds, such "
            "as unusually large TAU, TAUP or pressure_coefficient, compare "
            "wells relative to the population in the current simulation "
            "rather than inventing fixed thresholds. Assess only parameters "
            "available in the data."
        ),
        (
            "Always consider simulation quality when interpreting CRM "
            "parameters. Strong connectivity or unusual parameter values "
            "associated with poorly matched producers should be reported "
            "with reduced confidence."
        ),
        (
            "For broad summary requests, synthesize findings across tables "
            "rather than summarizing each table independently."
        ),
        (
            "For a broad simulation summary, actively identify the strongest "
            "and weakest injectors, well-supported and poorly supported "
            "producers, dominant production drivers, unusual response "
            "behavior, possible diagnostic signals and model-quality "
            "issues, where the available data permits."
        ),
        (
            "Prioritize findings supported by several independent metrics. "
            "Do not treat mathematically related metrics as independent "
            "confirmation."
        ),
        (
            "Do not enumerate every producer or injector unless the user "
            "explicitly requests an exhaustive listing."
        ),
        (
            "Scenario evaluation, such as predicting the impact of shutting "
            "an injector or changing injection rates, is outside the scope "
            "of this interpreter."
        ),
        (
            "Do not infer response speed or use TAU-based diagnostic "
            "criteria when TAU is unavailable."
        ),
    ],
}



