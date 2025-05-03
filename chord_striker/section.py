from pychord import Chord
import numpy as np
from helper_fns import accidental_fixer
from load_constants import KEYS


def chord_nc_equality(chord_nc_1, chord_nc_2):
    """
    An auxillary function to get around a quirk of the Chord class equality method.

    This is written to only return a result (True/False) if both arguments are Chord types, but we also want a result if one or both arguments are None types.

    Parameters:
        chord_nc_1: Either a Chord or a None object.
        chord_nc_2: Either a Chord or a None object.
    """

    if type(chord_nc_1) != type(chord_nc_2):
        return False

    else:
        return chord_nc_1 == chord_nc_2


# a function for transpose a chord from one key to another
def true_transpose(chord, current_key: chr, new_key: chr):
    """
    A method which transposes chords correctly.
    Parameters:
        chord: A Chord or None object.
        current_key: The key the chord is currently in.
        new_key: The desired key.
    Return:
        Chord: The correctly transposed chord.
    """

    if not (chord is None or isinstance(chord, Chord)):
        raise TypeError("chord must be either Chord or None object")

    if not current_key in KEYS or not new_key in KEYS:
        raise ValueError("One of the keys supplied is invalid")

    # convert to indices
    current_key_index = KEYS.index(current_key)
    new_key_index = KEYS.index(new_key)

    # see how many steps separate the two keys
    transposition_factor = (new_key_index - current_key_index) % 12

    # there is a dummy method for handling Nones
    if chord is None:
        return None

    else:
        # produce the transposed chord
        # new_chord = chord.deepcopy()
        chord.transpose(transposition_factor)

        # check sharps/flats
        chord = accidental_fixer(chord, new_key)

        return chord


class Section:
    def __init__(
        self,
        name=None,
        variation=None,
        time_signature="4/4",
        key="C",
        num_measures=8,
        units_per_beat=2,
        final_section=False,
    ):
        """
        This is a class for storing chord information for a section of a song.

        Attributes:
            name (str): Name for the section.
            variation(int): (Optional) Variation number for this section.
            time_signature (str): The time signature. Currently only 4/4 is supported.
            key (str): The key of this section (inter-section modulation is not currently supported).
            num_measures (int): The number of measures in the section.
            units_per_beat (int): The smallest recorded time unit, measured as subdivisions of a beat in the given time signature. This is 0-indexed.
            final_section (bool): Whether this is the final section in the piece.

        """

        if name != None and not isinstance(name, str):
            raise TypeError("name must be a string")

        if variation != None and not isinstance(variation, int):
            raise TypeError("variation must be an int")

        allowed_time_signatures = ["4/4"]  # TODO: add more time signatures
        if not time_signature in allowed_time_signatures:
            raise ValueError(
                "time_signature must be one of: {}.".format(allowed_time_signatures)
            )

        if not key in KEYS:
            raise ValueError("key must be supplied")

        if not isinstance(num_measures, int):
            raise TypeError("num_measures must be an int")

        if not isinstance(units_per_beat, int):
            raise TypeError("units_per_beat must be an int")

        if not isinstance(final_section, bool):
            raise ValueError("final_section must be logical")

        # set attributes
        self.name = name
        self.variation = variation
        self.time_signature = time_signature
        self.key = key
        self.num_measures = num_measures
        self.units_per_beat = units_per_beat
        self.final_section = final_section

        # get the number of beats per measure
        self.__beats_per_measure = int(self.time_signature.split("/")[0])

        # save total number of units
        self.total_units = (
            self.num_measures * self.__beats_per_measure * self.units_per_beat
        )

        # create list to store chord progression
        self.chord_progression = [None] * self.total_units

    def change_variation(self, var: int):
        self.variation = var

    def assign_chord(
        self, chord, measure=None, beat=None, unit=None, absolute_unit=None
    ):
        """
        This method adds a chord to a progression.

        Parameters:
            chord (Chord): The chord to add.
            measure (int): The measure in which to add the chord (using 1-indexing).
            beat (int): The beat in the measure at which to add the chord (1-indexed).
            unit (int): The unit in the beat at which to add the chord (1-indexed).
            absolute_unit (int): This only applies if the previous three parameters are all None. In this case an absolute unit can be specified for adding the chord at.


        """
        if not isinstance(chord, Chord):
            raise TypeError("chord must be a Chord object")

        if measure != None:
            # check measure provided is allowed
            if not isinstance(measure, int):
                raise TypeError("measure must be an int")
            if not (measure >= 1 and measure <= self.num_measures):
                raise ValueError(
                    "measure must be between 1 and the number of measures in the section"
                )

            # default beat value is 1
            if beat == None:
                beat = 1
            # else, check beat value is allowed
            else:
                if not isinstance(beat, int):
                    raise TypeError("beat must be an int")
                if not (beat >= 1 and beat <= self.__beats_per_measure):
                    raise ValueError(
                        "beat must be a between 1 and the number of beats per measure"
                    )

            # default unit value is 1
            if unit == None:
                unit = 1
            # else, check unit value is allowed
            else:
                if not isinstance(unit, int):
                    raise TypeError("unit must be an int")
                if not (unit >= 1 and unit <= self.units_per_beat):
                    raise ValueError(
                        "unit must be between 1 and the number of units per beat"
                    )

            absolute_unit = (
                (measure - 1) * self.__beats_per_measure * self.units_per_beat
                + (beat - 1) * self.units_per_beat
                + (unit - 1)
            )

        else:
            if absolute_unit == None:
                raise ValueError(
                    "You must provide some indication of where you want the chord added!"
                )

            if not isinstance(absolute_unit, int):
                raise TypeError("absolute_unit must be an int")

            if not (absolute_unit >= 0 or absolute_unit < self.total_units):
                raise ValueError(
                    "absolute_unit must be between 0 and the total number of units in the measure (exclusive)"
                )

            if beat != None or unit != None:
                raise Warning(
                    "You have provided a beat/unit but not a measure. Is this what you intended?"
                )

        # add the new chord in the desired position
        current_index = absolute_unit
        existing_chord = self.chord_progression[current_index]
        self.chord_progression[current_index] = chord

        # keep adding the chord until the next chord change
        while (
            current_index + 1 < self.total_units
            and self.chord_progression[current_index + 1] == existing_chord
        ):
            self.chord_progression[current_index + 1] = chord
            current_index += 1

    def get_chord(self, absolute_unit):
        return self.chord_progression[absolute_unit]

    def make_final_section(self):
        self.final_section = True

    def truncate(self, start_measure: int, end_measure: int):

        if (
            start_measure < 0
            or end_measure < 0
            or start_measure > self.num_measures
            or end_measure > self.num_measures
            or start_measure >= end_measure
        ):
            raise ValueError(
                "start/end measures must be legitimate measure numbers and start measure must preceed end measure"
            )

        self.num_measures = (end_measure - start_measure) + 1

        # update total number of units
        self.total_units = (
            self.num_measures * self.__beats_per_measure * self.units_per_beat
        )

        # update chord progression
        start_unit = (
            (start_measure - 1) * self.units_per_beat * self.__beats_per_measure
        )
        end_unit = (end_measure) * self.units_per_beat * self.__beats_per_measure
        self.chord_progression = self.chord_progression[start_unit:end_unit]

    def halve(self, half=0):
        if self.num_measures % 2 != 0:
            raise ValueError("number of measures must be divisible by 2")
        self.truncate(
            1 + half * self.num_measures // 2,
            self.num_measures // 2 + half * self.num_measures // 2,
        )

    def transpose(self, new_key):
        # a method to transpose an entire section

        # transpose chords
        self.chord_progression = [
            true_transpose(c, self.key, new_key) for c in self.chord_progression
        ]

        # change key
        self.key = new_key

    def __slashes_needed(self, compressed_chord_progression=None):
        """
        Helper function which determines, for each measure, if slashes will be needed to render chord charts.
        Parameters:
            compressed_chord_progression(list): The compressed chord progression, supplied by the main print method.
        """

        # get all chord change indices
        compressed_chord_change_indices = [
            i
            for i in range(len(compressed_chord_progression))
            if i == 0
            or not chord_nc_equality(
                compressed_chord_progression[i - 1], compressed_chord_progression[i]
            )
        ]

        ## see if chord changes evenly divide each measure; if so, we will not need any "/" symbols

        # this involves looping through measures

        slashes_needed_all = []

        for measure in range(1, self.num_measures + 1):

            # restrict to those in the current measure
            compressed_units_per_measure = (
                len(compressed_chord_progression) // self.num_measures
            )

            CCI_this_measure = [
                i
                for i in compressed_chord_change_indices
                if i // compressed_units_per_measure == (measure - 1)
            ]

            first_unit_of_measure = compressed_units_per_measure * (measure - 1)

            if len(CCI_this_measure) == 0 or CCI_this_measure == [
                first_unit_of_measure
            ]:
                # just one chord for whole measures - no slashes necessary
                slashes_needed = False
            elif len(CCI_this_measure) == 1:
                slashes_needed = True
            elif (
                first_unit_of_measure in CCI_this_measure
                and len(np.diff(CCI_this_measure)) == 1
            ):
                constant_diff = np.diff(CCI_this_measure)[0]
                if compressed_units_per_measure % constant_diff == 0:
                    slashes_needed = False
                else:
                    slashes_needed = True
            else:
                slashes_needed = True

            # add to vector
            slashes_needed_all.append(slashes_needed)

        return slashes_needed_all

    def __print_measure(
        self,
        measure=None,
        compressed_chord_progression=None,
        chord_length=None,
        slashes_needed=None,
    ):
        """
        Helper function for print method, which prints individual measures.

        Parameters:
            measure (int): The measure to print (1-indexing).
            compressed_chord_progression (list): The compressed chord progression, supplied by the main print method.
            chord_length (int): The space which should be allowed for chord strings, determined by the main print method.
            slashes_needed (bool): Logical indicating whether slashes are needed for this measure, provided by print method.
        """

        print_str = ""

        # get all chord change indices
        compressed_chord_change_indices = [
            i
            for i in range(len(compressed_chord_progression))
            if i == 0
            or not chord_nc_equality(
                compressed_chord_progression[i - 1], compressed_chord_progression[i]
            )
        ]

        # restrict to those in the current measure
        compressed_units_per_measure = (
            len(compressed_chord_progression) // self.num_measures
        )

        CCI_this_measure = [
            i
            for i in compressed_chord_change_indices
            if i // compressed_units_per_measure == (measure - 1)
        ]

        first_unit_of_measure = compressed_units_per_measure * (measure - 1)

        for i in range(
            first_unit_of_measure, first_unit_of_measure + compressed_units_per_measure
        ):
            if i in CCI_this_measure:
                this_chord = compressed_chord_progression[i]

                if chord_nc_equality(this_chord, None):
                    this_chord_str = "N.C."
                elif isinstance(this_chord, Chord):
                    this_chord_str = this_chord.chord
                else:
                    raise TypeError("chord must be either a Chord object or None!")

                print_str += this_chord_str + " " * (chord_length - len(this_chord_str))

            elif i == 0 and len(CCI_this_measure) == 0:
                print_str += "/" + " " * (chord_length - 1)

            else:
                if slashes_needed:
                    print_str += "/"
                else:
                    print_str += " "
                print_str += " " * (chord_length - 1)

        return print_str

    def changes(self):
        chord_change_indices = [
            i
            for i in range(len(self.chord_progression))
            if i % (self.__beats_per_measure * self.units_per_beat) == 0
            or not chord_nc_equality(
                self.chord_progression[i - 1], self.chord_progression[i]
            )
        ]

        chord_changes = [
            (
                accidental_fixer(self.chord_progression[idx], self.key)
                if idx in chord_change_indices
                else None
            )
            for idx in range(self.total_units)
        ]

        if self.units_per_beat != 2 or self.__beats_per_measure != 4:
            raise ValueError("We cannot handle other than 2 units per beat in 4/4 yet!")

        # add slashes where necessary
        slash_indices = self.__get_slash_indices(chord_change_indices)

        for idx in slash_indices:
            chord_changes[idx] = "/"

        return chord_changes

    def __slasher(self, index_list: list, n: int = 8):
        """
        A helper function which adds a slash position to a possible list of chord change indices.

        Args:
            index_list: A subset of k*n + [0,1,..,n-1] for some k.
            n: A multiple of 4.

        Return:
            index_list, possibly with one element added.
        """

        if n % 4 != 0:
            raise ValueError("n must be divisible by 4")

        extent_test = {i // n for i in index_list}

        if len(extent_test) > 2:
            raise ValueError(
                "index_list must be in the range kn, ..., k(n+1)-1 for some k"
            )

        if len(index_list) == 0:
            return index_list

        else:
            # extract k (this must be unique)
            k = max(extent_test)

            # shift back to 0,...n-1
            index_list_shifted = [i - (k * n) for i in index_list]

            if (
                (n // 4 in index_list_shifted) or (3 * n // 4 in index_list_shifted)
            ) and not (n // 2 in index_list_shifted):
                index_list_shifted.append(n // 2)
                index_list_shifted.sort()

            return [i + (k * n) for i in index_list_shifted]

    def __add_slashes(self, index_list, n):
        """
        A recursive function which adds all necessary slash positions to a
        list of chord change indices.

        Args:
            index_list: A subset of k*n + [0,1,..,n-1] for some k.
            n: A multiple of 4.

        Return:
            index_list with slash positions added.
        """

        if n == 4:
            return self.__slasher(index_list, n)

        else:
            index_list = self.__slasher(index_list, n)

            # split in 2
            m = n // 2
            lower, upper = [i for i in index_list if i % n < m], [
                i for i in index_list if i % n >= m
            ]

            # special case
            if (len(lower) >= 2 or len(upper) >= 1) and not (min(lower) + m in upper):
                upper.append(min(lower) + m)

            # recurse
            return self.__add_slashes(lower, m) + self.__add_slashes(upper, m)

    def __get_slash_indices(self, index_list):
        """
        A function which figures out the index of all points where slashes should be inserted.

        Args:
            index_list: A list of indices between 0 (inclusive) and self.total_units (exclusive).
        """
        units_per_measure = self.total_units // self.num_measures

        slash_indices = []

        for m in range(self.num_measures):
            chords_this_measure = [i for i in index_list if i // units_per_measure == m]

            # we append to this
            with_slashes = chords_this_measure

            # add slash to start of measure if required
            if m * units_per_measure not in with_slashes:
                with_slashes = [m * units_per_measure] + with_slashes

            # add slashes
            with_slashes = self.__add_slashes(with_slashes, units_per_measure)

            # where should slashes be inserted?
            only_slashes = [i for i in with_slashes if i not in chords_this_measure]

            # add
            slash_indices += only_slashes

        return slash_indices

    def __largest_possible_beat_multiple(self, CC_indices=None):
        """
        Helper function which determines the largest possible multiple of a beat that we can divide the chord chart into.

        Parameters:
            CC_indices (list): The list of all chord change indices, supplied by main print method.
        """

        # possible multiples of beat
        possible_multiples = [
            i
            for i in range(1, self.__beats_per_measure + 1)
            if self.__beats_per_measure % i == 0
        ]

        # possible subdivisions of beat (using unit size)
        possible_subdivisions = [
            i for i in range(1, self.units_per_beat + 1) if self.units_per_beat % i == 0
        ]

        # starting with the possible multiple, we see how much we can condense our chart spacing
        simplify_test = False
        simplify_type = "multiple"
        simplify_factor = max(possible_multiples) + 1

        while not simplify_test and (
            simplify_type == "multiple" or simplify_factor > 1
        ):

            if simplify_factor == 1:
                simplify_type = "subdivision"
                simplify_factor = max(possible_subdivisions)
            elif simplify_type == "multiple":
                remaining_possible_multiples = [
                    i for i in possible_multiples if i < simplify_factor
                ]
                simplify_factor = max(remaining_possible_multiples)
            else:
                remaining_possible_subdivisions = [
                    i for i in possible_subdivisions if i < simplify_factor
                ]
                simplify_factor = max(remaining_possible_subdivisions)

            # test
            if simplify_type == "multiple":
                mod_test = [
                    i % (simplify_factor * self.units_per_beat) for i in CC_indices
                ]
                simplify_test = max(mod_test) == 0
            else:
                # simplify_type is "subdivision"
                mod_test = [i % simplify_factor for i in CC_indices]
                simplify_test = max(mod_test) == 0

        return simplify_type, simplify_factor

    def __str__(self):
        """
        Displays chord chart for section.
        """

        print_str = ""

        # take a look at all strings representing chords in the progression
        all_possible_chords_strings = [
            c.chord for c in self.chord_progression if isinstance(c, Chord)
        ]

        # add "N.C." if appropriate
        for c in self.chord_progression:
            if chord_nc_equality(c, None) and not (
                "N.C." in all_possible_chords_strings
            ):
                all_possible_chords_strings.append("N.C.")

        # now get the max chord string length we may have to print
        max_chord_string_length = max(
            [len(chord_str) for chord_str in all_possible_chords_strings]
        )

        ##  what is the most basic multiple/subdivision of the beat we can get away with printing?

        # get all chord change indices
        chord_change_indices = [
            i
            for i in range(len(self.chord_progression))
            if i == 0
            or not chord_nc_equality(
                self.chord_progression[i - 1], self.chord_progression[i]
            )
        ]

        simplify_type, simplify_factor = self.__largest_possible_beat_multiple(
            chord_change_indices
        )

        # we "compress" the chord progression according to this simplification
        if simplify_type == "multiple":
            compressed_chord_progression = [
                self.chord_progression[i]
                for i in range(self.total_units)
                if i % (simplify_factor * self.units_per_beat) == 0
            ]
        else:
            compressed_chord_progression = [
                self.chord_progression[i]
                for i in range(self.total_units)
                if i % simplify_factor == 0
            ]

        # we also want to know whether slashes will be required in each measure
        slashes_needed_all = self.__slashes_needed(compressed_chord_progression)

        # if different chords occur in adjacent blocks of the compressed progression, or slashes will be required, we need to extend the max chord string length by 1 to allow for white space
        compressed_chord_change_indices = [
            i
            for i in range(len(compressed_chord_progression))
            if i == 0
            or not chord_nc_equality(
                compressed_chord_progression[i - 1], compressed_chord_progression[i]
            )
        ]

        if (
            len(compressed_chord_change_indices) > 1
            and min(np.diff(compressed_chord_change_indices)) == 1
        ) or max(slashes_needed_all) == True:
            max_chord_string_length += 1

        # it must also be at least 2
        max_chord_string_length = max(max_chord_string_length, 2)

        # now we can print the chord chart, measure-by-measure (see helper function above)
        for measure in range(self.num_measures):
            print_str += "|" + self.__print_measure(
                measure + 1,
                compressed_chord_progression,
                max_chord_string_length,
                slashes_needed_all[measure],
            )

        # add closing bar
        print_str += "|"

        # double bar if this is the final section
        if self.final_section:
            print_str += "|"

        return print_str

    def concat(self, another_section):
        """
        A method for concatenating two sections to form a third.
        """

        if not isinstance(another_section, Section):
            raise TypeError("another_section must be, in fact, a section!")

        # if names are the same, keep; otherwise, concatenate
        if self.name == another_section.name:
            concat_name = self.name

            available_variations = [
                x
                for x in [self.variation, another_section.variation]
                if isinstance(x, int)
            ] + [0]
            concat_variation = max(available_variations) + 1
        else:
            concat_name = "{}_{}".format(self.name, another_section.name)

            if self.variation == None:
                concat_variation = 1
            else:
                concat_variation = self.variation + 1

        # if time signatures do not agree, stop
        if self.time_signature != another_section.time_signature:
            raise ValueError("time signatures must agree!")

        # sim. for units per beat
        if self.units_per_beat != another_section.units_per_beat:
            raise ValueError("units per beat must agree!")

        # sim. for keys
        if self.key != another_section.key:
            raise ValueError("keys must agree!")

        # create new section
        concat_section = Section(
            name=concat_name,
            variation=concat_variation,
            num_measures=self.num_measures + another_section.num_measures,
            time_signature=self.time_signature,
            key=self.key,
            units_per_beat=self.units_per_beat,
            final_section=max(self.final_section, another_section.final_section),
        )

        # add chords
        for unit in range(self.total_units):
            chord = self.get_chord(unit)
            if isinstance(chord, Chord):
                concat_section.assign_chord(absolute_unit=unit, chord=chord)

        for unit in range(another_section.total_units):
            next_section_chord = another_section.get_chord(unit)
            if isinstance(next_section_chord, Chord):
                concat_section.assign_chord(
                    absolute_unit=self.total_units + unit, chord=next_section_chord
                )
            elif isinstance(chord, Chord):
                concat_section.assign_chord(
                    absolute_unit=self.total_units + unit, chord=chord
                )

        return concat_section
