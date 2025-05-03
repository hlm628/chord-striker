from section import Section
from random import choices, choice
from copy import copy
from scipy.stats import poisson
import numpy as np
from pychord import Chord, note_to_chord
from helper_fns import accidental_fixer, substitute, bernoulli_trial
from load_constants import (
    CHORD_CHANGE_PROBS,
    CHORD_EXTENSIONS,
    FAMOUS_CHORD_PROGRESSIONS,
    STRUCTURE_PARAMS,
)


# helpful function for choosing where to change chords in measure
def sample_measure_cc_locations(
    num_beats: int, units_per_beat: int, num_changes: float
):

    # give 100 times the weight to down beats, 20 times to upbeats
    measure_weights = [
        1
        + 100 * (i == 0)
        + 25 * (i % units_per_beat == 0)
        + 25 * (i % (2 * units_per_beat) == 0)
        + 5 * (i % units_per_beat == units_per_beat / 2)
        for i in range(num_beats * units_per_beat)
    ]
    # normalize
    measure_weights = [i / sum(measure_weights) for i in measure_weights]

    # sample at provided number of points
    sample = np.random.choice(
        list(range(num_beats * units_per_beat)),
        size=num_changes,
        p=measure_weights,
        replace=False,
    ).tolist()
    sample.sort()

    return sample


# a function that chooses chord changes in section
def choose_change_locations(
    section: Section, chords_per_measure: float = STRUCTURE_PARAMS["chords_per_measure"]
):
    """
    A function which decides where to place the chords in the section.

    Parameters:
        section (Section): An empty section. If this is not empty, it will be overwritten!
        chords_per_measure (float): The average number of chords we want per measure. This is actually the mean of a Poisson distribution that determines how many chords to ascribe to a given measure.
    """

    # list of number of changes in each measure
    change_vec = poisson.rvs(chords_per_measure, size=section.num_measures)

    # at most four changes per measure
    change_vec = [min(4, num_changes) for num_changes in change_vec]

    # first measure must contain 'change' at first tick
    change_vec[0] = max(0, change_vec[0] - 1)

    # get some essential timing info
    units_per_measure = section.total_units // section.num_measures
    beats_per_measure = units_per_measure // section.units_per_beat

    # initialize
    change_indices = [0]

    # loop through measures in section
    for meas in range(section.num_measures):
        if change_vec[meas] > 0:
            s = sample_measure_cc_locations(
                beats_per_measure, section.units_per_beat, change_vec[meas]
            )

            if meas == 0:
                s = [i for i in s if i != 0]

            change_indices += [i + units_per_measure * meas for i in s]

    return change_indices


class Chorder:
    def __init__(
        self, prev_chord=None, last_chord=False, chord_change_probs=CHORD_CHANGE_PROBS
    ):
        self.__chord_change_probs = chord_change_probs

        # the chord preceeding this one (affects probabilities)
        self.__prev_chord = prev_chord
        # flags indicating whether this chord is last in section
        self.__last_chord = last_chord

        # generate initial candidate for *this* chord
        self.__this_chord = self.__get_this_chord()

    def __get_this_chord(self):
        # split into chords and probabilities
        chords = [c for c in self.__chord_change_probs[self.__prev_chord]]
        probs = [self.__chord_change_probs[self.__prev_chord][c] for c in chords]

        # sample
        new_chord = choices(chords, weights=probs)[0]

        # if this is the last chord, we may revert to a 'perfect cadence' (choose the V chord) with 50% likelihood
        if self.__last_chord and choice([True, False]):
            new_chord = "V"

        return new_chord

    def new_chord(self):
        return self.__this_chord

    def __str__(self):
        return self.__this_chord


def chord_progression_selector(section: Section):

    # decide where to place chord changes + get number of changes
    change_indices = choose_change_locations(section)
    num_changes = len(change_indices)

    # choose chords
    chords = []

    this_chord = None
    for i in range(num_changes):
        this_chord = Chorder(
            prev_chord=this_chord, last_chord=(i == (num_changes - 1))
        ).new_chord()
        chords.append(this_chord)

    # decide whether or not to use famous CP - this can happen if there are 3/4 changes or 12 measures
    if section.num_measures == 12 and bernoulli_trial(
        STRUCTURE_PARAMS["famous_chord_progressions_probs"]["blues"]
    ):
        # get chords
        chords = FAMOUS_CHORD_PROGRESSIONS.get_prog("12 bar blues")

        # one chord per bar
        units_per_measure = section.total_units // section.num_measures

        # change indices
        if chords == ["I", "IV", "I", "V", "IV", "I"]:
            change_indices = [units_per_measure * m for m in [0, 4, 6, 8, 9, 10]]

        elif chords == ["I", "IV", "I", "V", "IV", "I", "V"]:
            change_indices = [units_per_measure * m for m in [0, 4, 6, 8, 9, 10, 11]]

        else:
            raise ValueError("this is some new kind of blues unseen before!")

    elif num_changes == 3 and bernoulli_trial(
        STRUCTURE_PARAMS["famous_chord_progressions_probs"][3]
    ):
        chords = FAMOUS_CHORD_PROGRESSIONS.get_prog(3)
    elif num_changes == 4 and bernoulli_trial(
        STRUCTURE_PARAMS["famous_chord_progressions_probs"][4]
    ):
        chords = FAMOUS_CHORD_PROGRESSIONS.get_prog(4)

    return change_indices, chords


def chord_parser(chord: "str", key: str):

    # possible chords
    diatonic_chords = ["I", "ii", "iii", "IV", "V", "vi", "vii"]
    borrowed = ["bIII", "III", "bVII"]

    if not chord in diatonic_chords + borrowed:
        raise ValueError("chord is not valid")

    # generate chord extensions
    extension = CHORD_EXTENSIONS.get_ext(chord)

    if not "sus" in extension:
        # incorporate minor tonality
        if chord != "vii":
            extension = "m" * (chord.islower()) + extension
        else:
            extension = "m7-5"

    if chord in diatonic_chords:
        py_chord = Chord.from_note_index(
            diatonic_chords.index(chord) + 1, extension, key + "maj"
        )

    elif chord in borrowed:
        py_chord = Chord.from_note_index(1, extension, key + "maj")
        transpose_tones = {"bIII": 3, "III": 4, "bVII": 10}
        py_chord.transpose(transpose_tones[chord])

    # invert
    if bernoulli_trial(STRUCTURE_PARAMS["invert_chord_prob"]):
        py_chord = invert(py_chord, key)

    # check sharps + flats are ok
    py_chord = accidental_fixer(py_chord, key)

    return py_chord


def invert(py_chord: Chord, key: str):
    # get all notes in chord
    notes = py_chord.components()

    # choose a new root note
    new_root = choice(notes[1:])

    # get string describing current chord
    py_chord_name = py_chord.info().split("\n")[0]

    # add root note
    py_chord_name = py_chord_name + "/" + new_root

    # add this is as root and return as new chord
    return Chord(py_chord_name)


def parse_chord_selections(section: Section, change_indices: list, chords: list):

    if len(change_indices) != len(chords):
        raise ValueError("number of change indices and chords to change to must agree")

    for idx in range(len(change_indices)):
        if (
            not isinstance(change_indices[idx], int)
            or change_indices[idx] < 0
            or change_indices[idx] >= section.total_units
        ):
            raise TypeError(
                "all change indices must be between {} and {}".format(
                    0, section.total_units
                )
            )

        if not isinstance(chords[idx], Chord):
            raise TypeError("one of the chords supplied is not a Chord")

        section.assign_chord(chords[idx], absolute_unit=change_indices[idx])

    return section


class ChordProgressionSelector:
    def __init__(self, section: Section):
        self.__section = section
        self.__change_indices, self.__chords_nashville = chord_progression_selector(
            self.__section
        )

        self.__base_chords = [
            chord_parser(c, self.__section.key) for c in self.__chords_nashville
        ]

        # initialize dictionary
        self.__var_dict = {
            0: {
                "result": parse_chord_selections(
                    self.__section, self.__change_indices, self.__base_chords
                ),
                "allow_double": False,
                "variation_type": None,
            }
        }

    def get_variation(self, var: int = 0, allow_double: bool = False, key: str = None):
        if var in self.__var_dict:
            # check 'allow double' flag is consistent with that is already stored in the dict
            if allow_double != self.__var_dict[var]["allow_double"]:
                raise ValueError("allow double flag is not correct for this variation")

        else:
            # decide which type of variation to go with
            options = ["add", "remove", "change"] + [
                x for x in ["double"] if allow_double
            ]
            variation_type = choice(options)

            # make a duplicate of section with 'variation' encoded
            new_section = copy(self.__section)
            new_section.change_variation(var)

            n = len(self.__change_indices)

            if variation_type == "double":
                output_section = parse_chord_selections(
                    new_section, self.__change_indices, self.__base_chords
                )
                output_section = output_section.concat(output_section)

            elif variation_type in ["remove", "change"]:
                # pick an existing index - double weight to first index, triple to last

                # need at least 2 chords to modify
                if n == 1:
                    output_section = new_section
                else:
                    alter_weights = [1 for i in range(n)]
                    alter_weights[-1] = 3
                    alter_weights[0] = 2

                    if variation_type == "remove":

                        # cannot remove first chord
                        alter_index = choices(
                            list(range(1, n)), weights=alter_weights[1:]
                        )[0]

                        new_indices = [
                            self.__change_indices[idx]
                            for idx in range(n)
                            if idx != alter_index
                        ]
                        new_chords = [
                            self.__base_chords[idx]
                            for idx in range(n)
                            if idx != alter_index
                        ]
                        output_section = parse_chord_selections(
                            new_section, new_indices, new_chords
                        )

                    else:

                        # cannot remove first chord
                        alter_index = choices(list(range(n)), weights=alter_weights)[0]

                        # change
                        if alter_index == n - 1:
                            next_chord = None
                        else:
                            next_chord = self.__chords_nashville[alter_index + 1]

                        if alter_index == 0:
                            prev_chord = None
                        else:
                            prev_chord = self.__chords_nashville[alter_index - 1]

                        new_chord = substitute(
                            prev_chord, self.__chords_nashville[alter_index], next_chord
                        )
                        # parse
                        new_chord = chord_parser(new_chord, new_section.key)

                        new_chords = self.__base_chords.copy()
                        new_chords[alter_index] = new_chord

                        output_section = parse_chord_selections(
                            new_section, self.__change_indices, new_chords
                        )

            elif variation_type == "add":
                available_indices = [
                    i
                    for i in range(new_section.total_units)
                    if not i in self.__change_indices
                ]
                measure_weights = [
                    1
                    + 100 * (i == 0)
                    + 25 * (i % new_section.units_per_beat == 0)
                    + 25 * (i % (2 * new_section.units_per_beat) == 0)
                    + 5
                    * (i % new_section.units_per_beat == new_section.units_per_beat / 2)
                    for i in available_indices
                ]

                new_index = choices(available_indices, weights=measure_weights)[0]

                new_indices = self.__change_indices + [new_index]
                new_indices.sort()

                alter_index = new_indices.index(new_index)

                # prev chord index does not change
                prev_chord = self.__chords_nashville[alter_index - 1]

                if alter_index == n:
                    next_chord = None
                else:
                    next_chord = self.__chords_nashville[alter_index]

                new_chord = substitute(prev_chord, None, next_chord)
                new_chord = chord_parser(new_chord, new_section.key)

                new_chords = (
                    self.__base_chords[:alter_index]
                    + [new_chord]
                    + self.__base_chords[alter_index:]
                )

                output_section = parse_chord_selections(
                    new_section, new_indices, new_chords
                )

            else:
                # something has gone wrong - but this will fail when creating the following dict...
                pass

            # add this variation to dictionary
            self.__var_dict[var] = {
                "result": output_section,
                "allow_double": allow_double,
                "variation_type": variation_type,
            }

        # get output section
        output_section = self.__var_dict[var]["result"]
        if key is not None:
            output_section.transpose(key)

        return output_section
