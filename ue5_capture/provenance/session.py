"""Session manifest + per-frame provenance blocks.

The session manifest is immutable once written. Provenance blocks on every
frame link that frame back to a specific mission step + capture tick so any
downstream consumer can reconstruct exactly how the frame was produced.

Populated in Phases P1.1 (session) and P1.4 (full provenance).
"""
