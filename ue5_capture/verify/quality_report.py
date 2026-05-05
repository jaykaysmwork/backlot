"""Quality report generator.

Validates every capture_output JSON against its Pydantic schema, checks file
integrity (every frame dir has all required files), and prints a summary
to quality_report.md + _report.json.

Populated in Phase P1.8.
"""
