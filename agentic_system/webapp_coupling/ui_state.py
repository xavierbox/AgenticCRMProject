
import pandas as pd, numpy as np 
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from wf_lib4_public.data.dataiku_local_folder_connector import  DataDrivenStorage 
from backend_blueprints4.globals.globals import get_config as get_storage_config



class UIState(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )

    subzone: str | None = None
    project_name: str | None = None
    study_name: str | None = None
    data_dates: list[str] | None = None
    sectors: list[int] | None = None
    query: str | None = Field(
        default=None,
        validation_alias="user_query",
    )

    def project_changed(self, incoming: "UIState") -> bool:
        return incoming.project_name != self.project_name

    def study_changed(self, incoming: "UIState") -> bool:
        return incoming.study_name != self.study_name

    def data_changed(self, incoming: "UIState") -> bool:
        return (
            incoming.subzone != self.subzone
            or incoming.sectors != self.sectors
            or incoming.data_dates != self.data_dates
        )

    def update_ui_state_from_payload(self, incoming: "UIState") -> None:
        for name, value in incoming.model_dump().items():
            #print(f"setting {name} to {value}")
            setattr(self, name, value)

            
def old_prepare_data_for_interpreter( crm_results):# project_name, study_name ):
    

    def get_production_rates_last_date_of_training( crm_results  ):
        # the last day of training?
        date = crm_results['crm_liquid_config']['simulation']['dates'][1] 
        target_date = pd.to_datetime( date )

        df = crm_results['crm_liquid_rates'].copy()
        df['DATE'] = pd.to_datetime( df['DATE']  )
        closest_row_index = (df['DATE'] - target_date).abs().idxmin()
        closest_date = df.loc[closest_row_index, 'DATE']
        df = df[ df['DATE'] == closest_date ].copy()


        df['current_produced_water_fraction']  = np.where( df['LIQUID_VOLUME'] > 0,  df['WATER_VOLUME'] / df['LIQUID_VOLUME'], 0.0 )
        df['current_produced_oil_fraction']    = np.where( df['LIQUID_VOLUME'] > 0,  df['OIL_VOLUME'] / df['LIQUID_VOLUME'], 0.0 )
        df['current_volume_liquid_produced']   =  df['LIQUID_VOLUME']  


        df.rename( columns = {'LIQUID_PRODUCTION_DUE_TO_PRIMARY':'current_liquid_production_due_to_depletion',
            'LIQUID_PRODUCTION_DUE_TO_PRESSURE':'current_liquid_production_due_to_pressure',
            'LIQUID_PRODUCTION_DUE_TO_INJECTION':'current_liquid_production_due_to_injection'        
        },inplace=True)


        columns = [ 'NAME', #'ACTIVITY', 
            'current_produced_water_fraction',  
                    'current_produced_oil_fraction',  
                    'current_volume_liquid_produced',  
                    'current_liquid_production_due_to_depletion',  
                    'current_liquid_production_due_to_injection', 
                    'current_liquid_production_due_to_pressure',
                    
                  ]

        df = df[columns].copy() 
        return df 


    columns = ['INJECTOR','PRODUCER','ALLOCATION','PRODUCER_ALLOCATION', 'DISTANCE'] 
    
    df_connectivity= crm_results['crm_liquid_parameters'][ columns ].rename( columns = {'ALLOCATION':'GAIN'} ).copy()
    gain = df_connectivity["GAIN"]
    eligible = gain[gain >= 0.05]

    low_cut, high_cut = eligible.quantile([1 / 3, 2 / 3])

    def classify_gain(x):
        if pd.isna(x):
            return "unknown"
        if x < 0.05:
            return "negligible"
        if x <= low_cut:
            return "low"
        if x <= high_cut:
            return "moderate"
        return "high"

    df_connectivity["GAIN_CLASS"] = gain.apply(classify_gain)
    
 
            
    ####
    
    columns = ['PRODUCER','CORRELATION','VARIANCE_RATIO','QUALITY_SCORE']#,'QUALITY_CLASS'] 
    df_quality= crm_results['crm_liquid_parameters'][ columns ].copy()
    
    df_quality['QUALITY_CLASS'] = df_quality['QUALITY_SCORE'].apply( lambda q: 'very good' if q > 0.85 else 'good' if q > 0.7 else 'moderate' if q > 0.5 else 'low') 
    ###
    
    df_producer  = get_production_rates_last_date_of_training( crm_results  )
    
    ### We add now TAU, TAUP and LO  then number_supporting_injectors
    df = crm_results['crm_liquid_parameters'].rename( columns = {'PRODUCER':'NAME'} ).copy() 
    columns_to_merge = ['NAME','TAU','TAUP','PRODUCTIVITY','LO']
    df = df[columns_to_merge]
    df_producer = df_producer.merge( df, how='left',left_on='NAME', right_on='NAME')
    
    
    #supporting injectors 
    df = df_connectivity.copy()#groupby( by = ['PRODUCER'] )[['PRODUCER','GAIN']].count() 
    df = df[ df['GAIN'] > 0.05 ].groupby( by = ['PRODUCER'] )[['PRODUCER']].count().rename( columns = {'PRODUCER':'number_supporting_injectors'} ).reset_index()
    df_producer = df_producer.merge( df[['PRODUCER','number_supporting_injectors']], how='left',
                                    left_on='NAME', right_on='PRODUCER')
    df_producer.drop( ['PRODUCER'], axis = 1, inplace=True)
    df_producer.rename( columns = {'PRODUCTIVITY':'pressure_coefficient','LO':'primary_depletion_coefficient'}, inplace=True)
    ###
    
    
    print('Returing connectivity table as ')
    print( df_connectivity.sample(10) )
    
    print('Returing df_quality table as ')
    print( df_quality.sample(10) )
    
    print('Returing df_producer table as ')
    print( df_producer.sample(10) )
    
    
    
    return df_connectivity, df_quality, df_producer 


def prepare_data_for_interpreter(crm_results):
    import numpy as np
    import pandas as pd

    GAIN_THRESHOLD = 0.05

    def validate_numeric(df, columns, label):
        df = df.copy()

        for column in columns:
            df[column] = pd.to_numeric(df[column], errors="raise")

            if not np.isfinite(
                df[column].to_numpy(dtype=float)
            ).all():
                raise ValueError(
                    f"{label}: column {column!r} contains "
                    "missing or infinite values."
                )

        return df

    def unique_records(df, key, columns, label):
        result = df[[key] + columns].drop_duplicates().copy()

        if result[key].isna().any():
            raise ValueError(f"{label}: missing {key} values.")

        duplicates = result.loc[
            result[key].duplicated(keep=False), key
        ].unique()

        if len(duplicates):
            raise ValueError(
                f"{label}: conflicting records for "
                f"{duplicates.tolist()}."
            )

        return result

    def select_snapshot(source, names, columns, label):
        source = source.copy()
        source["DATE"] = pd.to_datetime(
            source["DATE"], errors="coerce"
        )

        snapshot = source.loc[
            source["NAME"].isin(names)
            & source["DATE"].eq(snapshot_date),
            ["NAME"] + columns,
        ].copy()

        snapshot = validate_numeric(snapshot, columns, label)

        return unique_records(
            snapshot, "NAME", columns, label
        )

    def safe_divide(numerator, denominator):
        numerator = numerator.to_numpy(dtype=float)
        denominator = denominator.to_numpy(dtype=float)
        output = np.zeros(len(numerator), dtype=float)

        with np.errstate(
            divide="ignore",
            invalid="ignore",
            over="ignore",
        ):
            np.divide(
                numerator,
                denominator,
                out=output,
                where=denominator > 0,
            )

        if not np.isfinite(output).all():
            raise ValueError(
                "A division produced a non-finite result."
            )

        return output

    parameters = crm_results["crm_liquid_parameters"].copy()

    # ------------------------------------------------------------
    # Connectivity defines the complete well population.
    # ------------------------------------------------------------
    df_connectivity = (
        parameters[
            [
                "INJECTOR",
                "PRODUCER",
                "ALLOCATION",
                "PRODUCER_ALLOCATION",
                "DISTANCE",
            ]
        ]
        .rename(columns={"ALLOCATION": "GAIN"})
        .drop_duplicates()
        .copy()
    )

    if df_connectivity[
        ["INJECTOR", "PRODUCER"]
    ].isna().any().any():
        raise ValueError(
            "Connectivity contains missing injector or producer names."
        )

    if df_connectivity.duplicated(
        ["INJECTOR", "PRODUCER"]
    ).any():
        raise ValueError(
            "Connectivity contains conflicting records for "
            "the same injector–producer pair."
        )

    df_connectivity = validate_numeric(
        df_connectivity,
        ["GAIN", "PRODUCER_ALLOCATION", "DISTANCE"],
        "Connectivity",
    )

    gain = df_connectivity["GAIN"]
    eligible = gain[gain >= GAIN_THRESHOLD]
    low_cut, high_cut = eligible.quantile([1 / 3, 2 / 3])

    df_connectivity["GAIN_CLASS"] = np.select(
        [
            gain < GAIN_THRESHOLD,
            gain <= low_cut,
            gain <= high_cut,
        ],
        ["negligible", "low", "moderate"],
        default="high",
    )

    # ------------------------------------------------------------
    # Sectors: missing values become 99.
    # ------------------------------------------------------------
    all_names = pd.concat(
        [
            df_connectivity["INJECTOR"],
            df_connectivity["PRODUCER"],
        ],
        ignore_index=True,
    ).drop_duplicates()

    locations = crm_results["locations_df"][
        ["NAME", "SECTOR"]
    ].copy()

    locations = locations.loc[
        locations["NAME"].isin(all_names)
    ].copy()

    locations["SECTOR"] = pd.to_numeric(
        locations["SECTOR"], errors="coerce"
    ).replace([np.inf, -np.inf], np.nan)

    known_locations = unique_records(
        locations.dropna(subset=["SECTOR"]),
        "NAME",
        ["SECTOR"],
        "Locations",
    )

    sector_by_name = known_locations.set_index("NAME")["SECTOR"]

    df_connectivity["INJECTOR_SECTOR"] = (
        df_connectivity["INJECTOR"]
        .map(sector_by_name)
        .fillna(99)
    )
    df_connectivity["PRODUCER_SECTOR"] = (
        df_connectivity["PRODUCER"]
        .map(sector_by_name)
        .fillna(99)
    )

    # ------------------------------------------------------------
    # Shared production/injection snapshot date.
    # ------------------------------------------------------------
    target_date = pd.to_datetime(
        crm_results["crm_liquid_config"]["simulation"]["dates"][1]
    )

    if pd.isna(target_date):
        raise ValueError("The training end date is missing.")

    producer_names = df_connectivity["PRODUCER"].drop_duplicates()
    injector_names = df_connectivity["INJECTOR"].drop_duplicates()

    production_source = crm_results["crm_liquid_rates"]
    injection_source = crm_results["injectors_df"]

    def available_dates(source, names):
        dates = pd.to_datetime(
            source.loc[
                source["NAME"].isin(names),
                "DATE",
            ],
            errors="coerce",
        )
        return dates.dropna().drop_duplicates().sort_values()

    dates = available_dates(production_source, producer_names)

    if dates.empty:
        dates = available_dates(injection_source, injector_names)

    snapshot_date = (
        target_date
        if dates.empty
        else dates.iloc[(dates - target_date).abs().argmin()]
    )

    # ------------------------------------------------------------
    # Producer production snapshot.
    # ------------------------------------------------------------
    volume_columns = [
        "LIQUID_VOLUME",
        "WATER_VOLUME",
        "OIL_VOLUME",
        "LIQUID_PRODUCTION_DUE_TO_PRIMARY",
        "LIQUID_PRODUCTION_DUE_TO_PRESSURE",
        "LIQUID_PRODUCTION_DUE_TO_INJECTION",
    ]

    production_snapshot = select_snapshot(
        production_source,
        producer_names,
        volume_columns,
        "Production snapshot",
    ).rename(columns={"NAME": "PRODUCER"})

    df_producer = pd.DataFrame(
        {"PRODUCER": producer_names.to_numpy()}
    ).merge(
        production_snapshot,
        on="PRODUCER",
        how="left",
        validate="one_to_one",
    )

    df_producer[volume_columns] = (
        df_producer[volume_columns].fillna(0.0)
    )

    df_producer["current_produced_water_fraction"] = safe_divide(
        df_producer["WATER_VOLUME"],
        df_producer["LIQUID_VOLUME"],
    )
    df_producer["current_produced_oil_fraction"] = safe_divide(
        df_producer["OIL_VOLUME"],
        df_producer["LIQUID_VOLUME"],
    )

    df_producer = df_producer.rename(
        columns={
            "LIQUID_VOLUME": "current_volume_liquid_produced",
            "LIQUID_PRODUCTION_DUE_TO_PRIMARY":
                "current_liquid_production_due_to_depletion",
            "LIQUID_PRODUCTION_DUE_TO_PRESSURE":
                "current_liquid_production_due_to_pressure",
            "LIQUID_PRODUCTION_DUE_TO_INJECTION":
                "current_liquid_production_due_to_injection",
        }
    ).drop(columns=["WATER_VOLUME", "OIL_VOLUME"])

    df_producer["PRODUCER_ACTIVE"] = (
        df_producer["current_volume_liquid_produced"] > 0
    )
    df_producer["PRODUCER_SECTOR"] = (
        df_producer["PRODUCER"]
        .map(sector_by_name)
        .fillna(99)
    )

    # ------------------------------------------------------------
    # Producer model parameters.
    # ------------------------------------------------------------
    model = unique_records(
        parameters,
        "PRODUCER",
        ["TAU", "TAUP", "PRODUCTIVITY", "LO"],
        "Producer model parameters",
    ).rename(
        columns={
            "PRODUCTIVITY": "pressure_coefficient",
            "LO": "primary_depletion_coefficient",
        }
    )

    model = validate_numeric(
        model,
        [
            "TAU",
            "TAUP",
            "pressure_coefficient",
            "primary_depletion_coefficient",
        ],
        "Producer model parameters",
    )

    df_producer = df_producer.merge(
        model,
        on="PRODUCER",
        how="left",
        validate="one_to_one",
    )

    supported = df_connectivity.loc[
        df_connectivity["GAIN"] >= GAIN_THRESHOLD
    ]

    supporting_counts = supported.groupby("PRODUCER")[
        "INJECTOR"
    ].nunique()

    df_producer["number_supporting_injectors"] = (
        df_producer["PRODUCER"]
        .map(supporting_counts)
        .fillna(0)
        .astype(int)
    )

    # ------------------------------------------------------------
    # Producer model quality.
    # ------------------------------------------------------------
    quality_columns = [
        "CORRELATION",
        "VARIANCE_RATIO",
        "QUALITY_SCORE",
    ]

    df_quality = unique_records(
        parameters,
        "PRODUCER",
        quality_columns,
        "Producer quality",
    )

    df_quality = validate_numeric(
        df_quality,
        quality_columns,
        "Producer quality",
    )

    score = df_quality["QUALITY_SCORE"]

    df_quality["QUALITY_CLASS"] = np.select(
        [
            score > 0.85,
            score > 0.7,
            score > 0.5,
        ],
        ["very good", "good", "moderate"],
        default="low",
    )

    # ------------------------------------------------------------
    # Injector injection snapshot.
    # ------------------------------------------------------------
    injection_snapshot = select_snapshot(
        injection_source,
        injector_names,
        ["WATER_INJECTION_VOLUME"],
        "Injection snapshot",
    ).rename(
        columns={"WATER_INJECTION_VOLUME": "WATER_INJECTION"}
    )

    df_injectors = pd.DataFrame(
        {"NAME": injector_names.to_numpy()}
    ).merge(
        injection_snapshot,
        on="NAME",
        how="left",
        validate="one_to_one",
    )

    df_injectors["WATER_INJECTION"] = (
        df_injectors["WATER_INJECTION"].fillna(0.0)
    )
    df_injectors["INJECTOR_ACTIVE"] = (
        df_injectors["WATER_INJECTION"] > 0
    )
    df_injectors["SECTOR"] = (
        df_injectors["NAME"]
        .map(sector_by_name)
        .fillna(99)
    )

    # ------------------------------------------------------------
    # Attribution and efficiency.
    # All connections participate, including negligible gains.
    # ------------------------------------------------------------
    connections = df_connectivity.merge(
        df_producer[
            [
                "PRODUCER",
                "current_produced_water_fraction",
                "current_produced_oil_fraction",
                "current_liquid_production_due_to_injection",
            ]
        ],
        on="PRODUCER",
        how="left",
        validate="many_to_one",
    )

    # Attribution formula retained unchanged as requested.
    connections["attributable_liquid"] = (
        connections["PRODUCER_ALLOCATION"]
        * connections["current_liquid_production_due_to_injection"]
    )
    connections["attributable_oil"] = (
        connections["attributable_liquid"]
        * connections["current_produced_oil_fraction"]
    )
    connections["attributable_water"] = (
        connections["attributable_liquid"]
        * connections["current_produced_water_fraction"]
    )

    # Revised efficiency: sum of gain-weighted oil fractions.
    # Independent of current injection and producer allocations.
    connections["gain_weighted_oil_fraction"] = (
        connections["GAIN"]
        * connections["current_produced_oil_fraction"]
    )

    connections = validate_numeric(
        connections,
        [
            "attributable_liquid",
            "attributable_oil",
            "attributable_water",
            "gain_weighted_oil_fraction",
        ],
        "Attribution and efficiency",
    )

    connections["supported_producer"] = (
        connections["PRODUCER"].where(
            connections["GAIN"] >= GAIN_THRESHOLD
        )
    )

    summary = (
        connections.groupby(
            "INJECTOR",
            as_index=False,
            sort=False,
        )
        .agg(
            GAIN_SUM=("GAIN", "sum"),
            N_SUPPORTED_PRODUCERS=(
                "supported_producer",
                "nunique",
            ),
            total_attributable_liquid=(
                "attributable_liquid",
                "sum",
            ),
            total_attributable_oil=(
                "attributable_oil",
                "sum",
            ),
            total_attributable_water=(
                "attributable_water",
                "sum",
            ),
            INJECTOR_EFFICIENCY=(
                "gain_weighted_oil_fraction",
                "sum",
            ),
        )
        .rename(columns={"INJECTOR": "NAME"})
    )

    df_injectors = df_injectors.merge(
        summary,
        on="NAME",
        how="left",
        validate="one_to_one",
    )

    df_injectors["N_SUPPORTED_PRODUCERS"] = (
        df_injectors["N_SUPPORTED_PRODUCERS"].astype(int)
    )

    df_injectors["UNALLOCATED_INJECTION_FRACTION"] = (
        1.0 - df_injectors["GAIN_SUM"]
    ).clip(lower=0.0, upper=1.0)

    df_injectors["UNALLOCATED_WATER_INJECTION"] = (
        df_injectors["WATER_INJECTION"]
        * df_injectors["UNALLOCATED_INJECTION_FRACTION"]
    )

    df_injectors["INJECTION_OVERALLOCATED"] = (
        df_injectors["GAIN_SUM"] > 1.0 + 1e-9
    )

    # ------------------------------------------------------------
    # Final numeric checks.
    # ------------------------------------------------------------
    df_producer = validate_numeric(
        df_producer,
        [
            column
            for column in df_producer.columns
            if column not in [
                "PRODUCER",
                "PRODUCER_ACTIVE",
            ]
        ],
        "Producer output",
    )

    df_injectors = validate_numeric(
        df_injectors,
        [
            column
            for column in df_injectors.columns
            if column not in [
                "NAME",
                "INJECTOR_ACTIVE",
                "INJECTION_OVERALLOCATED",
            ]
        ],
        "Injector output",
    )

    for table in (
        df_connectivity,
        df_quality,
        df_producer,
        df_injectors,
    ):
        table.attrs["snapshot_date"] = snapshot_date.isoformat()

    return (
        df_connectivity.reset_index(drop=True),
        df_quality.reset_index(drop=True),
        df_producer.reset_index(drop=True),
        df_injectors.reset_index(drop=True),
    )




def prepare_data_for_analyst( project_name ):
    storage = DataDrivenStorage( get_storage_config() ) 
    crm_dataset = storage.get_project_dataset( project_name )
    return crm_dataset

def check_ui_state_changes(ui_state: UIState,incoming: UIState):
    project_changed = ui_state.project_changed(incoming)
    study_changed   = True if project_changed else ui_state.study_changed(incoming)
    data_changed    = True if project_changed else ui_state.data_changed(incoming)

    return project_changed, study_changed, data_changed

def process_ui_state_changes(
    ui_state: UIState,
    payload: dict[str, Any],
    agentic_system,
):# -> dict[str, bool]:

    # Validate before performing any updates.
    incoming = UIState.model_validate(payload)
    print("The incoming payload is ")
    print( incoming )

    (project_changed, 
     study_changed, 
     data_changed
    ) = check_ui_state_changes(ui_state,incoming)

    if not any( [project_changed,study_changed,data_changed] ):
        print("No changes in the UI detected")
        return None 

    refresh_history = True if project_changed else False 
    refresh_input_analyst = (project_changed or data_changed)
    refresh_results_interpreter = (project_changed or study_changed)
    
  
    storage = DataDrivenStorage( get_storage_config() )  
    project_name = incoming.project_name
    simulation_name = incoming.study_name
    print( project_name, simulation_name )
        
    if refresh_input_analyst:
        # Refresh using incoming.project_name, incoming.subzone, date, incoming.sectors and incoming.data_dates.
        crm_dataset = prepare_data_for_analyst( project_name )
        inj, prd, locs = crm_dataset.injectors_df,  crm_dataset.producers_df, crm_dataset.locations_df  
        agentic_system.set_analyst_data( {'injectors':inj, 'producers':prd, 'locations':locs })
        print("Anayst data updated")
            

    if refresh_results_interpreter:
        # Refresh using the incoming project, study and data selection.
        
        # if there isnt any study selected? 
        if not incoming.study_name:
            pass#agentic_system.set_interpreter_data( None )
            #to_return["interpreter_data"] = None 
                
        else:
            crm_results = storage.load_simulation_results(project_name,simulation_name ) 
            (df_connectivity, 
             df_quality, 
             df_producer,
             df_injector) = prepare_data_for_interpreter( crm_results)

            raw_data = {
                "connectivity_table":       df_connectivity,
                "simulation_quality_table": df_quality, 
                "producer_model_table":     df_producer,
                "injector_model_table": df_injector
            }
            
            agentic_system.set_interpreter_data( raw_data )
                
            #to_return["interpreter_data"] = (df_connectivity, df_quality,df_producer )
        
        # if we change the project, clear memory
        # but...should we clear it if we just change the simulation ? 
        #agentic_system.clear_memory() 
        print("The interpreter was updated")

        
        #/opt/dataiku/python-code-envs/XGTAgents
        
  
        
    # Store the new state after the refresh operations succeed.
    print(100*'=')
    print("The ui state was updated. ")
    ui_state.update_ui_state_from_payload(incoming)


    agentic_system.project_name = ui_state.project_name   
    return (project_changed, 
     study_changed, 
     data_changed
    )
    
  
    
