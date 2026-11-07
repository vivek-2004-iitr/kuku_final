"""Kuku promo finder — finds the best 20-60s promotional clips in microdrama
screenplays and explains why each one works.

Pipeline:
    parse   -> score -> search -> copy -> audit
    (LLM refiner is optional and only rewords the human copy; it never
     touches timestamps or scores, so the rules engine stays the source of
     truth and the tool works fully offline.)
"""
__version__ = "1.0"
