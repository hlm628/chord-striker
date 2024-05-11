from pychord import Chord
from pychord.constants.scales import FLATTED_SCALE, SHARPED_SCALE, SCALE_VAL_DICT


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
