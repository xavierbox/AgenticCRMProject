
import pandas as pd, numpy as np 
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
#from wf_lib4_public.data.dataiku_local_folder_connector import  DataDrivenStorage 
#from backend_blueprints4.globals.globals import get_config as get_storage_config



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
       
def prepare_data_for_interpreter( crm_results):# project_name, study_name ):
    

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


    columns = ['INJECTOR','PRODUCER','ALLOCATION','PRODUCER_ALLOCATION'] 
    
    df_connectivity= crm_results['crm_liquid_parameters'][ columns ].rename( columns = {'ALLOCATION':'GAIN'} ).copy()
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
    
    
    return df_connectivity, df_quality, df_producer 

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
             df_producer ) = prepare_data_for_interpreter( crm_results)

            raw_data = {
                "connectivity_table":       df_connectivity,
                "simulation_quality_table": df_quality, 
                "producer_model_table":     df_producer,
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
    
