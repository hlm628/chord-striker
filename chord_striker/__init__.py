"""Chord Striker - A Python library for generating random harmonic song structures."""

__version__ = "0.1.0"

# Public API
from chord_striker.hit_maker import create_song, create_album
from chord_striker.create_chord_chart import ChordChart
from chord_striker.song_structure import (
    generate_song_structure,
    parse_song_structure,
    get_tempo,
)
from chord_striker.section import Section
from chord_striker.load_constants import load_constants

__all__ = [
    "__version__",
    "create_song",
    "create_album",
    "ChordChart",
    "generate_song_structure",
    "parse_song_structure",
    "get_tempo",
    "Section",
    "load_constants",
]
