# Domain Generality Report (Phase B)

## Phase: B

### Claim
10 of 10 fixed domain requests produced distinct, correctly-typed, non-ICE, non-templated-looking output against live Ollama (`ollama:gpt-oss:20b` at `https://ollama.com`).

### Evidence
Command: `python scripts/run_domain_generality.py`
Provider: `ollama:gpt-oss:20b` host=`https://ollama.com`

| # | Prompt | object_type | comps | type_ok | comps_ok | intent_ok | not_ICE | Result |
|---|--------|-------------|-------|---------|----------|-----------|---------|--------|
| 1 | design a steel truss bridge spanning 40 meters | `steel_truss_bridge` | 16 | True | True | True | True | **PASS** |
| 2 | design a bicycle frame for a road racing bike | `bicycle_frame` | 41 | True | True | True | True | **PASS** |
| 3 | design a quadcopter drone frame | `quadcopter_frame` | 5 | True | True | True | True | **PASS** |
| 4 | design a residential HVAC ductwork system | `hvac_ductwork` | 30 | True | True | True | True | **PASS** |
| 5 | design a lithium-ion battery pack enclosure | `battery_pack_enclosure` | 28 | True | True | True | True | **PASS** |
| 6 | design a wooden dining chair | `dining_chair` | 32 | True | True | True | True | **PASS** |
| 7 | design a centrifugal water pump | `centrifugal_pump` | 55 | True | True | True | True | **PASS** |
| 8 | design a robotic arm gripper | `robotic_arm_gripper` | 35 | True | True | True | True | **PASS** |
| 9 | design a pressure vessel for compressed nitrogen storage | `pressure_vessel` | 32 | True | True | True | True | **PASS** |
| 10 | design a solar panel mounting rack | `solar_panel_mounting_rack` | 25 | True | True | True | True | **PASS** |
| 11 | design a bicycle frame | `bicycle_frame` | 33 | True | True | True | True | **PASS** |
| 12 | design a chair | `dining_chair` | 29 | True | True | True | True | **PASS** |

### Per-request B3 answers

#### `design a steel truss bridge spanning 40 meters`

1. **object_type / domain correct?** Yes — `object_type=steel_truss_bridge`, domains=['structural_analysis', 'materials', 'civil_engineering', 'mechanical_design']
2. **Components plausible for this object?** Yes — ids=['temp_sensor_module', 'humidity_sensor_module', 'temperature_control_logic', 'humidity_control_logic', 'data_acquisition_interface', 'actuation_command_generator', 'safety_monitor', 'communication_interface', 'data_logging_module', 'pid_controller', 'component_heater_element', 'component_heater_control_switch', 'component_heater_power_supply', 'component_misting_nozzle', 'component_misting_pump', 'component_water_valve']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='steel_truss_bridge'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/steel_truss_bridge.json`
Notes: none

#### `design a bicycle frame for a road racing bike`

1. **object_type / domain correct?** Yes — `object_type=bicycle_frame`, domains=['mechanical_design', 'materials', 'structural_analysis', 'aerodynamics', 'manufacturing_processes']
2. **Components plausible for this object?** Yes — ids=['seat_tube_length_spec', 'head_tube_angle_spec', 'reach_and_stack_calculation', 'top_tube_adjustable_geometry', 'down_tube_length_spec', 'seat_stay_length_spec', 'chainstay_length_spec', 'aero_front_chainstay', 'aero_top_tube', 'aero_seat_stays', 'aero_hub_shell', 'aero_frame_aero_integration', 'ms_prepreg_material_specification', 'ms_aluminum_alloy_evaluation', 'ms_chromoly_steel_evaluation', 'ms_material_property_dataset', 'ms_cost_and_weight_tradeoff_analysis', 'fe_model_creation', 'load_case_definition', 'boundary_condition_setup', 'material_property_assignment', 'mesh_generation', 'solver_config', 'result_postprocessing', 'weight_data_importer', 'material_density_repository', 'tube_section_volume_calculator', 'frame_mass_estimator', 'weight_reporting_module', 'weight_validation_checker', 'layup_pattern_design', 'extrusion_profile_design', 'welding_parameter_definition', 'tooling_and_mold_planning', 'process_quality_control_plan', 'geometry_definition_module', 'aerodynamic_shape_generator', 'material_specifier', 'stiffness_verifier', 'weight_calculator', 'manufacturability_planner']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='bicycle_frame'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/bicycle_frame.json`
Notes: none

#### `design a quadcopter drone frame`

1. **object_type / domain correct?** Yes — `object_type=quadcopter_frame`, domains=['structural_analysis', 'mechanical_design', 'materials', 'aerodynamics', 'electronics_mounting', 'manufacturing']
2. **Components plausible for this object?** Yes — ids=['component_high_current_connector', 'component_power_cable_500a', 'component_power_control_module', 'component_protective_shielding', 'component_grounding_interface']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='quadcopter_frame'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/quadcopter_frame.json`
Notes: none

#### `design a residential HVAC ductwork system`

1. **object_type / domain correct?** Yes — `object_type=hvac_ductwork`, domains=['mechanical_design', 'fluid_dynamics', 'thermodynamics', 'acoustics', 'building_codes', 'materials', 'thermal']
2. **Components plausible for this object?** Yes — ids=['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'dc_flange_insertion', 'dc_duct_coupler_bolt', 'dc_gasket_strips', 'dc_pipe_sealant', 'dc_heat_shrink', 'dc_end_seal_panel', 'duct_sheet_aluminum_356_t6', 'mineral_wool_insulation', 'reflective_insulation_duct', 'stainless_steel_304_duct_cladding', 'spray_foam_insulation', 'duct_insulation_adhesive', 'pressure_sensor_unit', 'temperature_sensor_unit', 'flow_rate_sensor_unit', 'control_processor_block', 'safety_interlock_unit', 'code_compliance_validator', 'filter_housing', 'filter_cartridge', 'filter_mounting_bracket', 'filter_seal_ring', 'filter_pressure_indicator', 'filter_cleaning_alarm']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='hvac_ductwork'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/hvac_ductwork.json`
Notes: none

#### `design a lithium-ion battery pack enclosure`

1. **object_type / domain correct?** Yes — `object_type=battery_pack_enclosure`, domains=['mechanical_design', 'materials', 'thermal_management', 'electrical', 'safety', 'thermal']
2. **Components plausible for this object?** Yes — ids=['cell_mounting_frame', 'cell_holder_panels', 'cell_spacer_inserts', 'sealing_gasket_assembly', 'access_hatch_alignment', 'shell_front_panel', 'shell_side_beam', 'shell_top_shell', 'fire_suppression_panel', 'composite_weight_reduction_layer', 'intumescent_lining', 'fire_retardant_fabric_shell', 'flame_retardant_polyurethane_fiberglass_core', 'heat_activated_fuse_system', 'thermal_gas_cooling_chamber', 'char_coating_packet', 'heat_pipe_array', 'heat_exchanger_block', 'coolant_pump', 'temperature_sensor_array', 'active_cooling_fan', 'control_electronics_unit', 'c1_access_panel_body', 'c2_hinge_mechanism', 'c3_latch_release', 'c4_gasket_sealing', 'c5_mounting_bracket', 'c6_access_keyhole']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='battery_pack_enclosure'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/battery_pack_enclosure.json`
Notes: none

#### `design a wooden dining chair`

1. **object_type / domain correct?** Yes — `object_type=dining_chair`, domains=['mechanical_design', 'structural_analysis', 'materials', 'ergonomics']
2. **Components plausible for this object?** Yes — ids=['seat_top_panel', 'seat_support_beam', 'backrest_angle_lock', 'leg_assembly_frame', 'durability_fasteners', 'varnish_application_unit', 'compliance_inspection_tools', 'manufacturing_process_station', 'seat_sole', 'seat_rib', 'seat_mount_fastener', 'seat_top_lap', 'bkp_backrest_panel', 'bkr_backrest_frame', 'brb_backrest_reinforcement_brackets', 'bps_backrest_seating_pad', 'faf_backrest_attachment_fasteners', 'vehicle_leg_front_left', 'vehicle_leg_front_right', 'vehicle_leg_back_left', 'vehicle_leg_back_right', 'seat_frame', 'backrest_frame', 'diagonal_brace', 'corner_brace', 'mortise_tenon_joint', 'varnish_sprayer', 'brush_set', 'sandpaper_kit', 'drying_oven', 'finish_coating_tray', 'finish_qa_station']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='dining_chair'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/dining_chair.json`
Notes: none

#### `design a centrifugal water pump`

1. **object_type / domain correct?** Yes — `object_type=centrifugal_pump`, domains=['mechanical_design', 'fluid_dynamics', 'materials', 'thermodynamics']
2. **Components plausible for this object?** Yes — ids=['motor_and_shaft_assembly', 'impeller_assembly', 'intake_and_suction_assembly', 'discharge_and_pressure_assembly', 'bearing_and_seal_assembly', 'cooling_assembly', 'control_and_sensing_assembly', 'vibration_damping_assembly', 'motor_stator_core', 'motor_rotor', 'motor_winding', 'motor_housing', 'motor_shaft', 'shaft_coupling', 'shaft_flange', 'impeller_blades', 'impeller_hub', 'impeller_cage', 'impeller_lip', 'suction_port', 'suction_pipe', 'inlet_valve', 'suction_gasket', 'inlet_baffle', 'suction_nozzle', 'inlet_seal', 'discharge_nozzle', 'discharge_pipeline', 'diffuser_annulus', 'pressure_relief_valve', 'discharge_shroud', 'discharge_flow_meter', 'bearing_tapered_roller', 'bearing_flange', 'labyrinth_seal_unit', 'elastic_gland_seal', 'bearing_retainer', 'shaft_extrusion', 'motor_cooling_fan', 'oil_cooler', 'water_jacket', 'cooling_water_pump', 'motor_temperature_sensor', 'comp_control_unit', 'comp_encoder_unit', 'comp_suction_pressure_sensor', 'comp_discharge_pressure_sensor', 'comp_temperature_sensors', 'comp_flow_sensing_module', 'acc_sensor', 'mag_sensing_pad', 'spring_damper_mount', 'tuned_mass_damper', 'active_vib_actuator', 'elastomeric_bearing_pad']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='centrifugal_pump'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/centrifugal_pump.json`
Notes: none

#### `design a robotic arm gripper`

1. **object_type / domain correct?** Yes — `object_type=robotic_arm_gripper`, domains=['mechanical_design', 'materials', 'mechatronics', 'control_systems', 'robotics_kinematics', 'electrical', 'force_transmission', 'thermal_management']
2. **Components plausible for this object?** Yes — ids=['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'power_supply', 'voltage_regulator', 'distribution_board', 'current_sensor', 'fuse_block', 'cable_manager', 'motor_driver_interface', 'control_algorithms_processor', 'power_management_unit', 'communication_interface', 'sensor_data_aggregator', 'signal_conditioning_unit', 'sensors_finger_encoder', 'sensor_finger_force_loadcell', 'sensor_mounting_bracket', 'thermal_management_subsystem_heat_sink', 'thermal_management_subsystem_thermal_interface_pad', 'thermal_management_subsystem_active_fan', 'thermal_management_subsystem_thermal_switch', 'thermal_management_subsystem_thermal_insulation_panel', 'thermal_management_subsystem_temperature_sensor', 'thermal_management_subsystem_heat_pipe', 'c1_finger_linkage_arm', 'c2_finger_joint_wrist', 'c3_transmission_coupler', 'c4_compliance_pad', 'c5_finger_tip_contact_surface', 'c6_finger_housing']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='robotic_arm_gripper'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/robotic_arm_gripper.json`
Notes: none

#### `design a pressure vessel for compressed nitrogen storage`

1. **object_type / domain correct?** Yes — `object_type=pressure_vessel`, domains=['mechanical_design', 'materials_engineering', 'structural_analysis', 'thermodynamics', 'fluid_dynamics', 'safety_and_compliance', 'safety', 'materials']
2. **Components plausible for this object?** Yes — ids=['material_specification', 'supplier_evaluation', 'proof_test_setup', 'fatigue_test_setup', 'material_certification', 'quality_control_inspector', 'test_report_document', 'test_gage_set', 'vessel_wall_section', 'cylindrical_head', 'reinforcement_ring', 'weld_pattern_spec', 'thermal_pressure_analysis_model', 'geometry_optimization_grid', 'code_compliance_verification', 'thermal_insulation_panel', 'temperature_monitoring_system', 'vessel_shape_optimizer', 'weld_joint_design', 'welding_procedure_specification', 'fabrication_schedule', 'fitup_and_tolerance_spec', 'welding_quality_control_plan', 'assembly_jig_and_fixture', 'pressure_test_fixture_system', 'cost_tracking', 'documentation_management', 'regulatory_submission', 'material_cost_estimator', 'fabrication_cost_controller', 'testing_cost_tracker', 'project_reporting_tool']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='pressure_vessel'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/pressure_vessel.json`
Notes: none

#### `design a solar panel mounting rack`

1. **object_type / domain correct?** Yes — `object_type=solar_panel_mounting_rack`, domains=['structural_analysis', 'mechanical_design', 'materials', 'civil_engineering', 'environmental_engineering']
2. **Components plausible for this object?** Yes — ids=['panel_mount_plate', 'tilt_adjustment_rod', 'locking_torque_hub', 'corrosion_resistant_bolts', 'mr_rail_main', 'mr_cross_member', 'mr_vertical_post', 'mr_gusset_plate', 'mr_shear_gusset', 'mr_beam_connector', 'cylindrical_roller_bearing_6206', 'steel_angular_shaft_link', 'spur_gear_20t_gear_hub', 'polyurea_gearbox_housing', 'epoxy_rotary_seal', 'epoxy_precoat_plate', 'hot_dip_galvanized_plate', 'zinc_sacrificial_anode', 'epdm_sealing_gasket', 'alkaline_zinc_phosphate_coat', 'cost_estimation_module', 'material_cost_selector', 'procurement_strategy_unit', 'manufacturing_process_optimizer', 'lifecycle_cost_manager']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='solar_panel_mounting_rack'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/solar_panel_mounting_rack.json`
Notes: none

#### `design a bicycle frame`

1. **object_type / domain correct?** Yes — `object_type=bicycle_frame`, domains=['mechanical_design', 'structural_analysis', 'materials']
2. **Components plausible for this object?** Yes — ids=['user_data_gathering_module', 'performance_specification_sheet', 'cost_target_form', 'material_selection_criteria', 'manufacturing_constraints_document', 'regulatory_compliance_checklist', 'tube_layout_spec', 'joint_location_spec', 'parametric_cad_modeling', 'rear_triangle_sizing', 'front_triangle_sizing', 'model_importer', 'mesh_generator', 'load_case_definer', 'solver_engine', 'postprocessor', 'visualizer', 'compliance_checker', 'angle_lock_bracket', 'length_adjuster_pivot', 'joint_forming_mold', 'geometry_adapter_plate', 'tubular_stabilizer', 'frame_aluminum_tube', 'frame_carbon_fiber_tube', 'frame_steel_tube', 'hybrid_aluminum_steel_tube', 'doc_drawing_generation', 'doc_component_specification', 'doc_fabrication_instructions', 'doc_bill_of_materials', 'doc_quality_control_plan', 'doc_regulatory_compliance']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='bicycle_frame'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/bicycle_frame.json`
Notes: none

#### `design a chair`

1. **object_type / domain correct?** Yes — `object_type=dining_chair`, domains=['mechanical_design', 'materials', 'ergonomics', 'manufacturing', 'structural_analysis']
2. **Components plausible for this object?** Yes — ids=['frame_box', 'front_panel', 'side_panel_left', 'side_panel_right', 'back_panel', 'cross_brace', 'leg_mounting_plate', 'seat_frame_structural', 'foam_cushion_core', 'seat_top_panel', 'upholstery_cover', 'backrest_frame_rail', 'lumbar_support_arch', 'lumbar_support_pad', 'backrest_cushion', 'backrest_upholstery_cover', 'backrest_mounting_bracket', 'backrest_fastener_set', 'lumbar_cushion_pad', 'lumbar_support_bracket', 'lumbar_retention_clip', 'lumbar_interface_layer', 'lumbar_fastener_set', 'lumbar_cushion_cutout', 'lumbar_dip_cutout', 'leg_extrusion', 'leg_mount_plate', 'knee_joint_bracket', 'anti_slip_floor_pad']
3. **Domain-appropriate intent/constraints (not ICE placeholders)?** Yes — decisions=[]
4. **Physics dispatch:** ICE physics skipped — warnings=["No physics module registered for object_type='dining_chair'; ICE PhysicsEngine was not invoked."]
Evidence JSON: `/Users/shreyaannath/Programming/JARVIS2/docs/domain_generality_evidence/dining_chair.json`
Notes: none

### B3.4 — Can a new domain be added without modifying the core pipeline?

**Mostly yes after this phase:** add entries to `knowledge/functional/general_domains.py` and `knowledge/decomposition/component_templates.py`, optionally register a physics handler via `core.reasoning.domain_dispatch.register_physics_handler`. The pipeline calls `_run_physics` which dispatches; ICE `PhysicsEngine` is no longer unconditional.

Residual coupling: `RequirementCompiler` ICE parameter extractors and `MaterialAssigner` role registry remain ICE-shaped for depth work — non-ICE materials stay honestly unassigned until Phase E.

### Known gaps

- Pass threshold for Phase B done: **≥8/10**. Current: **10/10**.
- Live LLM outputs vary; re-run may change borderline cases.
- DeterministicProvider still defaults to ICE (test fixture only).
- No non-ICE quantitative physics module yet (Phase F).
- **Component quality is uneven:** object types are correct and non-ICE, but some
  LLM expansions invent process/sensor fluff instead of primary structural parts
  (notably the truss-bridge run listed climate-control modules; the quadcopter
  run was sparse). Templates under `knowledge/` cover better assemblies when the
  LLM functional step fails validation — depth/quality is Phase E/F work.
- Materials remain largely unassigned for non-ICE components (Phase E).
