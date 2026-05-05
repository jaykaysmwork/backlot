"""Post-capture mission validator.

Reads the MissionPlan + produced capture_output, emits validation_report.json
covering:

  B-scope: frame count / file integrity / simple counts
  A-scope: coverage_goals (min_unique_classes_seen, per-class min_frames,
           altitude diversity) + constraints (min_actors_per_frame etc.)

Populated in Phase P1.7.
"""
