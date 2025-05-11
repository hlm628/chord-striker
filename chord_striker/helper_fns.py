from pychord import Chord
from pychord.constants.scales import FLATTED_SCALE, SHARPED_SCALE, SCALE_VAL_DICT
from chord_striker.load_constants import CHORD_CHANGE_PROBS, STRUCTURE_PARAMS
from random import choices


def sample_weights_dict(d):
    """
    A function to sample a dictionary of weights, where the keys are the possible values
    and the values are the weights. Weights are raised to the power of the weirdness factor
    to make common choices more likely and rare choices less likely.
    """

    # check that all weights are positive
    for k, v in d.items():
        if not isinstance(v, (int, float)):
            raise TypeError("weights must be real numbers")
        if v < 0:
            raise ValueError("weights must be positive")

    # get keys and weights
    keys = list(d.keys())
    weights = list(d.values())

    # Apply weirdness factor (defaults to 1.0 if not set)
    weirdness = STRUCTURE_PARAMS.get("weirdness", 1.0)
    weights = [w**weirdness for w in weights]

    # sample
    return choices(keys, weights=weights)[0]


def bernoulli_trial(p):
    """
    A function to sample a Bernoulli trial, where p is the probability of success.
    """

    # check that p is a valid probability
    if not isinstance(p, (int, float)):
        raise TypeError("p must be a real number")
    if p < 0 or p > 1:
        raise ValueError("p must be between 0 and 1")

    # sample
    return choices([True, False], weights=[p, 1 - p])[0]


def fix_accidental(note: str, key: str):
    """
    A function which ensures accidentals are being used correctly within the current key.
    """
    # check key
    possible_keys = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

    if not key in possible_keys:
        raise ValueError(f"Key supplied ({key}) is not valid")

    ## check whether we are dealing with a sharp or flat key
    # what we should be seeing (sharp or flat)
    correct_scale = SCALE_VAL_DICT[key]

    # check if the root of the given chord appears in this scale
    if note not in correct_scale.values():
        # get the OTHER scale
        if correct_scale == SHARPED_SCALE:
            wrong_scale = FLATTED_SCALE
        else:
            wrong_scale = SHARPED_SCALE

        # find the idx of the root in THIS scale
        note_index = list(wrong_scale.values()).index(note)

        return correct_scale[note_index]

    # nothing to do if the root is correct
    else:
        return note


def accidental_fixer(chord: Chord, key: str):
    """
    A convenient function to apply the sharp_flat_fixer to chords.
    """

    # apply fix to root (if necessary)
    correct_root = fix_accidental(chord.root, key)

    # get string describing current chord
    chord_name = chord.info().split("\n")[0]

    # replace root note with correct one
    chord_name = chord_name.replace(chord.root, correct_root, 1)

    # if there is a slash root, replace this too
    if chord.on != None:
        correct_on = fix_accidental(chord.on, key)
        chord_name = chord_name.replace(chord.on, correct_on, 1)

    # return as new chord
    return Chord(chord_name)


def substitute(prev_chord, current_chord, next_chord=None):
    """
    A function to substitute a chord with another chord, based on the previous and next chords.
    The function uses a dictionary of probabilities to determine the most likely chord to substitute.
    """

    all_possible_chords = list(CHORD_CHANGE_PROBS.keys())

    if next_chord == None:
        possible_chords = [
            c for c in all_possible_chords if not c in [None, current_chord, prev_chord]
        ]
        weights = [CHORD_CHANGE_PROBS[prev_chord][c] for c in possible_chords]

    else:
        # we use a probabilistic result:
        # P(B|AC) ~ P(C|B) P(B|A)
        possible_chords = [
            c
            for c in all_possible_chords
            if not c in [None, current_chord, prev_chord, next_chord]
        ]
        weights = [
            CHORD_CHANGE_PROBS[c][next_chord] * CHORD_CHANGE_PROBS[prev_chord][c]
            for c in possible_chords
        ]

    return choices(possible_chords, weights=weights)[0]
