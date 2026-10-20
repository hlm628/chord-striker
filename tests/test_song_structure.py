import random

import numpy as np
import pytest
from pychord import Chord

from chord_striker.chorder import ChordProgressionSelector, start_on_tonic
from chord_striker.helper_fns import accidental_fixer
from chord_striker.load_constants import STRUCTURE_PARAMS, constants_override
from chord_striker.section import Section
from chord_striker.song_structure import (
    generate_song_structure,
    parse_key,
    parse_song_structure,
)


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)


def generate_sections(seed, tmp_path, structure_params=None):
    with constants_override(structure_params=structure_params):
        seed_all(seed)
        song = generate_song_structure(output_dir=str(tmp_path))
        return parse_song_structure(song, None)


@pytest.mark.parametrize("seed", range(20))
def test_variations_do_not_alter_base_progression(seed):
    seed_all(seed)
    generator = ChordProgressionSelector(
        Section(name="Verse", variation=0, key="C", num_measures=4)
    )
    before = [str(c) for c in generator.get_variation(0).chord_progression]
    for var in (1, 2, 3):
        generator.get_variation(var)
    assert [str(c) for c in generator.get_variation(0).chord_progression] == before


@pytest.mark.parametrize("seed", range(20))
def test_sections_are_independent(seed, tmp_path):
    sections = generate_sections(seed, tmp_path)
    objects = [s["section"] for s in sections]
    assert len({id(o) for o in objects}) == len(objects)
    # each section is in the key it was planned in (key changes are kept)
    assert all(s["section"].key == s["key"] for s in sections)
    # only the last section is marked as final
    assert [o.final_section for o in objects] == [False] * (len(objects) - 1) + [True]


def test_key_changes_are_kept(tmp_path):
    # force a key change before every chorus after the first
    sections = generate_sections(
        0, tmp_path, {"truck_drivers_base_prob": 1.0, "num_choruses_probs": {3: 1}}
    )
    choruses = [s for s in sections if s["name"] == "Chorus"]
    assert len({c["key"] for c in choruses}) > 1
    for c in choruses:
        assert c["section"].key == c["key"]


def test_only_final_verse_is_halved(tmp_path):
    lengths = {**STRUCTURE_PARAMS["measure_distributions"], "Verse": {8: 1}}
    sections = generate_sections(
        1,
        tmp_path,
        {
            "halve_final_verse_prob": 1.0,
            "measure_distributions": lengths,
            "num_choruses_probs": {3: 1},
            "skip_last_verse_prob": 0.0,
        },
    )
    verses = [s["section"].num_measures for s in sections if s["name"] == "Verse"]
    assert len(verses) > 1
    assert verses[:-1] == [8] * (len(verses) - 1)
    assert verses[-1] == 4


def test_end_on_tonic(tmp_path):
    sections = generate_sections(2, tmp_path, {"end_on_tonic_prob": 1.0})
    last = sections[-1]["section"]
    assert last.chord_progression[-1].root == last.key


def test_minor_song_ends_on_relative_minor(tmp_path):
    sections = generate_sections(
        3, tmp_path, {"minor_prob": 1.0, "end_on_tonic_prob": 1.0}
    )
    last = sections[-1]["section"]
    relative_minor = accidental_fixer(
        Chord.from_note_index(6, "m", last.key + "maj"), last.key
    )
    assert last.chord_progression[-1].root == relative_minor.root


@pytest.mark.parametrize(
    "progression, minor, expected",
    [
        (["vi", "IV", "I", "V"], False, ["I", "V", "vi", "IV"]),
        (["I", "V", "vi", "IV"], True, ["vi", "IV", "I", "V"]),
        (["IV", "V", "vi"], False, ["IV", "V", "vi"]),
    ],
)
def test_start_on_tonic(progression, minor, expected):
    assert start_on_tonic(progression, minor) == expected


@pytest.mark.parametrize(
    "key, expected",
    [
        (None, (None, None)),
        ("C", ("C", False)),
        ("F#", ("F#", False)),
        ("Am", ("C", True)),
        ("F#m", ("A", True)),
        ("Bbm", ("C#", True)),
        ("A#m", ("C#", True)),
        ("Cm", ("Eb", True)),
    ],
)
def test_parse_key(key, expected):
    assert parse_key(key) == expected


@pytest.mark.parametrize("key", ["H", "Cmaj", "m", "C#b", "Xm"])
def test_parse_key_rejects_invalid(key):
    with pytest.raises(ValueError):
        parse_key(key)
