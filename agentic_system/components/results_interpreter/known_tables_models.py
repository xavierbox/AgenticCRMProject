
# known_table_mdels.py

old_interpreter_semantic_catalog = {
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
                        "implemented when this table was generated."
                    ),
                },
                {
                    "name": "DISTANCE",
                    "data_type": "float",
                    "description": "Distance between injector and producer, in meters.",
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
                        "Sum of PRODUCER_ALLOCATION over all injectors connected "
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
            "GAIN and PRODUCER ALLOCATION have different physical meanings and "
            "must not be used interchangeably."
        ),
        "GAIN is injector-centric.",
        "PRODUCER_ALLOCATION is producer-centric.",
        "GAIN below 0.05 is considered negligible.",
        (
            "For a balanced simulation, the sum of GAIN across producers "
            "for an injector must be <= 1."
        ),
        (
            "The sum of PRODUCER ALLOCATION across injectors for a producer "
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

interpreter_semantic_catalog = {
    "tables": [
        {
            "name": "connectivity_table",
            "description": (
                "Simulation-derived injector-producer connectivity results. "
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
                        "This is referred as the -injector allocation- in the technical jargon"
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
                        "implemented when this table was generated."
                    ),
                },
                {
                    "name": "DISTANCE",
                    "data_type": "float",
                    "description": "Distance between injector and producer, in meters.",
                },
                
                
                {
                    'name': 'INJECTOR_SECTOR',
                    'data_type': 'integer',
                    'description': 'Injector sector identifier. 99 means unknown or missing.',
                },
                {
                    'name': 'PRODUCER_SECTOR',
                    'data_type': 'integer',
                    'description': 'Producer sector identifier. 99 means unknown or missing.',
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
                "Producer-level history-match quality metrics. "
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
                        "Composite history-match quality metric from "
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
                        "Simulation-derived productivity coefficient: derivative of liquid "
                        "production with respect to bottom-hole pressure, "
                        "according to the model's pressure convention."
                    ),
                },
                {
                    "name": "total_allocation",
                    "data_type": "float",
                    "description": (
                        "Sum of PRODUCER_ALLOCATION over all injectors connected "
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
                {
                    'name': 'primary_depletion_coefficient',
                    'data_type': 'float',
                    'description': 'Producer-level primary-depletion coefficient, copied from model parameter LO. Interpret according to the model equations.',
                },
                {
                    'name': 'PRODUCER_SECTOR',
                    'data_type': 'integer',
                    'description': 'Producer sector identifier. 99 means unknown or missing.',
                },
                {
                    'name': 'PRODUCER_ACTIVE',
                    'data_type': 'boolean',
                    'description': 'True when current_volume_liquid_produced > 0 at the selected training-end snapshot; otherwise False. Missing snapshot records are assigned zero volumes and therefore False. This is not an independently observed operational status.',
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
        {'name': 'injector_model_table',
         'description': 'Injector-level injection snapshot, connectivity summaries, and modeled '
                        'attributable production. One row per injector in unfiltered connectivity_table, '
                        'including injectors missing from the injection snapshot. Missing snapshot rates '
                        'become zero. Production and injection use the shared selected date; this is not '
                        'necessarily today. Injector attribution uses the preparation-code allocation '
                        'formula and requires confirmation of the allocation basis.',
         'kind': 'base',
         'columns': [{'name': 'NAME',
                      'data_type': 'string',
                      'description': 'Injector well name. Unique per row. The injector population is '
                                     'defined by all distinct INJECTOR values in unfiltered '
                                     'connectivity_table.'},
                     {'name': 'WATER_INJECTION',
                      'data_type': 'float',
                      'description': 'Water injection at the shared snapshot nearest the training end '
                                     'date. Missing injection records are assigned 0.0. Not a cumulative '
                                     'volume; use the source injection units and time basis.'},
                     {'name': 'SECTOR',
                      'data_type': 'integer',
                      'description': 'Injector sector identifier. 99 means unknown or missing.'},
                     {'name': 'GAIN_SUM',
                      'data_type': 'float',
                      'description': 'Sum of GAIN over every producer connected to this injector, '
                                     'including negligible connections. Not clipped; values above one '
                                     'indicate modeled over-allocation.'},
                     {'name': 'N_SUPPORTED_PRODUCERS',
                      'data_type': 'integer',
                      'description': 'Number of distinct connected producers with GAIN >= 0.05. Negligible '
                                     'connections are excluded only from this count, not from gain sums or '
                                     'attribution.'},
                     {'name': 'total_attributable_liquid',
                      'data_type': 'float',
                      'description': 'Sum over connected producers of PRODUCER_ALLOCATION * '
                                     'current_liquid_production_due_to_injection, as implemented by '
                                     'preparation code. Includes negligible connections. Uses producer '
                                     'production units and time basis. May be positive when current '
                                     'injection is zero. The allocation basis must be verified against the '
                                     'existing PRODUCER_ALLOCATION definition before physical '
                                     'interpretation.'},
                     {'name': 'total_attributable_oil',
                      'data_type': 'float',
                      'description': 'Sum over connected producers of PRODUCER_ALLOCATION * '
                                     'current_liquid_production_due_to_injection * '
                                     'current_produced_oil_fraction. Assumes injection-driven liquid has '
                                     'the current total-produced-liquid oil fraction. Model attribution, '
                                     'not independently measured causal oil production.'},
                     {'name': 'total_attributable_water',
                      'data_type': 'float',
                      'description': 'Sum over connected producers of PRODUCER_ALLOCATION * '
                                     'current_liquid_production_due_to_injection * '
                                     'current_produced_water_fraction. Assumes injection-driven liquid has '
                                     'the current total-produced-liquid water fraction. Not a direct '
                                     'measurement of recovered injected water.'},
                     {'name': 'INJECTOR_ACTIVE',
                      'data_type': 'boolean',
                      'description': 'True when WATER_INJECTION > 0 at the selected snapshot; otherwise '
                                     'False. Missing snapshot records are assigned zero and therefore '
                                     'False. An inactive injector may still have positive attributable '
                                     'production.'},
                     {'name': 'INJECTOR_EFFICIENCY',
                      'data_type': 'float',
                      'description': 'total_attributable_oil / WATER_INJECTION when WATER_INJECTION > 0; '
                                     'otherwise the fallback is 0.0. Exclude nonpositive-injection wells '
                                     'from efficiency rankings. An average snapshot ratio, not marginal '
                                     'oil response to injection changes. Comparable only with compatible '
                                     'units and time bases.'},
                     {'name': 'UNALLOCATED_INJECTION_FRACTION',
                      'data_type': 'float',
                      'description': 'clip(1 - GAIN_SUM, 0, 1). Modeled fraction of injector water not '
                                     'assigned to represented producers. Does not establish physical loss, '
                                     'out-of-zone flow, or channeling. Clipping conceals negative '
                                     'residuals when GAIN_SUM > 1; inspect INJECTION_OVERALLOCATED.'},
                     {'name': 'UNALLOCATED_WATER_INJECTION',
                      'data_type': 'float',
                      'description': 'WATER_INJECTION * UNALLOCATED_INJECTION_FRACTION. Uses injection '
                                     'units and time basis. Modeled unallocated injection, not a measured '
                                     'water loss.'},
                     {'name': 'INJECTION_OVERALLOCATED',
                      'data_type': 'boolean',
                      'description': 'True when GAIN_SUM > 1.0 + 1e-9, matching the preparation-code '
                                     'floating-point tolerance. Flags a modeled allocation inconsistency '
                                     'requiring investigation.'}],
         'relationships': [{'tables_involved': ['injector_model_table', 'connectivity_table'],
                            'join_type': 'left',
                            'join_condition': 'injector_model_table.NAME = connectivity_table.INJECTOR',
                            'description': 'Retrieve all producer connections for an injector. '
                                           'Injector-level metrics repeat across these connections; do not '
                                           'sum repeated injection or attributable totals after joining.'}]},
    ],
    "semantic_constraints": [
        (
            "GAIN and PRODUCER ALLOCATION have different physical meanings and "
            "must not be used interchangeably."
            "The term GAIN is generally replaced by -injector allocation- in results, summaries and technical jargon"
        ),
        "GAIN is injector-centric.",
        "PRODUCER_ALLOCATION is producer-centric.",
        "GAIN below 0.05 is considered negligible.",
        (
            "For a balanced simulation, the sum of GAIN across producers "
            "for an injector must be <= 1."
        ),
        (
            "The sum of PRODUCER ALLOCATION across injectors for a producer "
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
            "The term -total injector allocation- if preferred over -utility-" 
        ),
        (
            "injector efficiency is the ratio of the total attributable oil produced "
            "as result of the injection to the total water injected"
        ),
        (
            "The term GAIN is must replaced by -injector allocation- in all the answers"

        ),
         (" producer efficiency is the ratio of the total oil produced at a given producer p to its total liquid production"
         )
    ],
    "business_rules": [
        "GAIN < 0.05 is negligible.",
        (
            "A high-utility injector supports one or more producers and "
            "has total GAIN across producers approaching 1 in a balanced model."
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

        (
            "Simulations can run in balanced or unbalanced mode. "
            "In unbalanced mode, the sum of GAIN across producers for an injector "
            "is not constrained to be <= 1 and can exceed 1. Such results do not "
            "enforce injector-level mass conservation and may be used diagnostically. "
            "In balanced mode, the sum of GAIN across producers for each injector "
            "is constrained to be <= 1, enforcing injector-level mass conservation."
        ),
        (
            "simulations can be ran with or without pressure information."
        )

    ],
    "interpretation_guidelines": [
        (
            "Scenario evaluation is outside this component's scope. Do not predict "
            "the effects of shutting wells, changing injection rates, or other "
            "hypothetical operational interventions."
        ),
        (
            "For ambiguous rankings such as best, worst, strongest, or most effective, "
            "determine the intended criterion from the question; do not assume these "
            "terms always refer to the same metric. Request clarification when needed."
        ),

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
            "number_supporting_injectors, total_allocation, PRODUCER ALLOCATION "
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
            "support to a fast-responding producer. It might indicate Channeling  but "
            "more analysis needs to be performed"
            ""
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
            "producer connections."
        ),
        (
            "For quantities without established absolute thresholds, such "
            "as unusually large TAU, TAUP or pressure_coefficient, compare "
            "wells relative to the population in the current simulation "
            "rather than inventing fixed thresholds. Assess only parameters "
            "available in the data."
        ),
        (
            "Always consider simulation quality when interpreting simulation "
            "parameters. Strong connectivity or unusual parameter values "
            "associated with poorly matched producers should be reported "
            "with reduced confidence."
        ),
                (
            "Select evidence across tables as needed: connectivity_table describes "
            "injector-producer connections, producer_model_table describes production "
            "drivers and response parameters, and simulation_quality_table describes "
            "history-match quality. For current oil attribution to an injector, combine "
            "PRODUCER_ALLOCATION with producer current liquid production and oil fraction. "
            "For reliable strong connections, combine connectivity with producer quality."
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


    ],
}



