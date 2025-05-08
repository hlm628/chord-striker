import networkx as nx
from chord_striker.section import Section
from chord_striker.probabilistic_dag import ProbDAG
from random import choices
from math import log
import numpy as np
from datetime import datetime
from chord_striker.chorder import ChordProgressionSelector
from chord_striker.load_constants import KEYS, KEY_PROBABILITIES, STRUCTURE_PARAMS
from chord_striker.helper_fns import sample_weights_dict, bernoulli_trial


class SongKey:
    """
    A class which stores key information.
    """

    def __init__(self, initial_key: str = None):
        self.__key = initial_key

        # if a key is given, check it is valid
        if initial_key != None:
            if not (initial_key in KEYS):
                raise ValueError(f"key supplied is not valid. Must be one of: {KEYS}")
        # if no key is given, we randomly select one
        if initial_key == None:
            # initial key chosen at random
            self.__key = sample_weights_dict(KEY_PROBABILITIES)

    def key_change(self, num_steps: int = None):

        # number of steps to transpose can be given or left to chance
        if not isinstance(num_steps, int):
            num_steps = sample_weights_dict(STRUCTURE_PARAMS["transpose_steps_probs"])

        current_index = KEYS.index(self.__key)
        new_index = (current_index + num_steps) % 12
        self.__key = KEYS[new_index]

    def get_key(self):
        return self.__key

    def __str__(self):
        return self.__key


def get_tempo(
    min_tempo: int = STRUCTURE_PARAMS["min_tempo"],
    max_tempo: int = STRUCTURE_PARAMS["max_tempo"],
    tempo_variation: int = STRUCTURE_PARAMS["tempo_variation"],
) -> int:
    """
    Function which randomly picks a tempo for the song by truncating a log-normal distribution (chosen so that ~99% of tempos are between the range specified).
    """

    # check that min and max tempo are valid
    if not isinstance(min_tempo, int) or not isinstance(max_tempo, int):
        raise TypeError("min_tempo and max_tempo must be integers")
    if min_tempo < 0 or max_tempo < 0:
        raise ValueError("min_tempo and max_tempo must be positive")

    # use min and max tempo to get mean and std of log-normal distribution
    mean = np.log((min_tempo + max_tempo) / 2)
    std = np.log(max_tempo / min_tempo) / 6

    # check that tempo variation is valid
    if not isinstance(tempo_variation, int):
        raise TypeError("tempo_variation must be an integer")
    if tempo_variation < 0:
        raise ValueError("tempo_variation must be positive")

    # use tempo variation to adjust std
    std = std * (tempo_variation / 100)

    # get tempo
    tempo = np.random.lognormal(mean, std)
    # truncate to range
    tempo = max(min_tempo, min(tempo, max_tempo))
    # round to nearest integer
    tempo = int(round(tempo))
    return tempo


def get_song_variables():
    """Generates some song variables which determine the song structure."""

    # the number of choruses random, and depends on weights in structural params
    num_choruses = sample_weights_dict(STRUCTURE_PARAMS["num_choruses_probs"])

    # should there be a prechorus?
    prechorus = bernoulli_trial(STRUCTURE_PARAMS["pre_chorus_prob"])

    # should there be a postchorus? this depends on whether there was a prechorus
    if prechorus:
        postchorus = bernoulli_trial(
            STRUCTURE_PARAMS["post_chorus_probs"]["pre_chorus_yes"]
        )
    else:
        postchorus = bernoulli_trial(
            STRUCTURE_PARAMS["post_chorus_probs"]["pre_chorus_no"]
        )

    # should the bridge come before the solo (if there is one)?
    bridge_solo_order = bernoulli_trial(STRUCTURE_PARAMS["bridge_before_solo"])

    return num_choruses, prechorus, postchorus, bridge_solo_order


def song_structure_graph(num_choruses, prechorus, postchorus, bridge_solo_order):
    """The function which generates the song structure."""

    # get song variables
    num_choruses, prechorus, postchorus, bridge_solo_order = get_song_variables()

    ## now we build the graph of possible song structure
    G = nx.DiGraph()

    # song must have placeholders for when it starts and ends
    G.add_node("Song Start", event_type="source")
    G.add_node("Song Finish", event_type="sink")

    # song can have an intro and an outro
    G.add_node("Intro", event_type="section")
    G.add_node("Outro", event_type="section")

    # the intro can be followed by modulation (a la Cheap Trick's 'Surrender')
    G.add_node("Cheap Trick Modulation", event_type="modulation")

    # each chorus can be associated with a verse, post-chorus solo and/or bridge
    # they can also be associated with a pre/post-chorus (if allowed)

    possible_events = ["Verse", "Chorus", "Bridge", "Solo"]
    if prechorus:
        possible_events.append("Prechorus")
    if postchorus:
        possible_events.append("Postchorus")

    for i in range(num_choruses):
        for event in possible_events:
            # placeholder for start of iteration
            G.add_node(f"Iteration {i + 1} Start", event_type="source")

            # nodes for possible sections
            G.add_node(f"{event} {i + 1}", event_type="section")

            # there is also a possible modulation post-chorus
            G.add_node(f"Postchorus Modulation {i + 1}", event_type="modulation")

            # four sim. placeholders for latter-half/end of iteration
            G.add_node(f"Iteration {i + 1} Middle", event_type="sink")
            for j in ["II", "III"]:
                G.add_node(f"Iteration {i + 1} Middle {j}", event_type="sink")
            G.add_node(f"Iteration {i + 1} Ending", event_type="sink")

    # add initial edges with probabilities
    G.add_weighted_edges_from(
        [
            # song goes straight to verse/chorus
            ("Song Start", "Iteration 1 Start", 1 - STRUCTURE_PARAMS["intro_prob"]),
            # otherwise, we have an intro
            ("Song Start", "Intro", STRUCTURE_PARAMS["intro_prob"]),
            # cheap trick modulation can happen at the start
            ("Intro", "Cheap Trick Modulation", STRUCTURE_PARAMS["cheap_trick_prob"]),
            ("Intro", "Iteration 1 Start", 1 - STRUCTURE_PARAMS["cheap_trick_prob"]),
            ("Cheap Trick Modulation", "Iteration 1 Start", 1),
            # outro
            (
                f"Iteration {num_choruses} Ending",
                "Outro",
                STRUCTURE_PARAMS["outro_prob"],
            ),
            (
                f"Iteration {num_choruses} Ending",
                "Song Finish",
                1 - STRUCTURE_PARAMS["outro_prob"],
            ),
            # outro must go to song end
            ("Outro", "Song Finish", 1),
        ],
        weight="p",
    )

    # then add verse/chorus cycles

    for i in range(1, num_choruses + 1):

        # go to verse unless we are in the first or final iteration (may skip straight to prechorus/chorus)
        if i == 1:
            if prechorus:
                G.add_weighted_edges_from(
                    [
                        # go to prechorus
                        (
                            f"Iteration {i} Start",
                            f"Prechorus {i}",
                            STRUCTURE_PARAMS["start_pre_chorus_prob"],
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Chorus {i}",
                            STRUCTURE_PARAMS["start_chorus_prob"],
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Verse {i}",
                            1
                            - (
                                STRUCTURE_PARAMS["start_pre_chorus_prob"]
                                + STRUCTURE_PARAMS["start_chorus_prob"]
                            ),
                        ),
                    ],
                    weight="p",
                )

            else:
                G.add_weighted_edges_from(
                    [
                        # suitably adjusted if there is no prechorus
                        (
                            f"Iteration {i} Start",
                            f"Chorus {i}",
                            STRUCTURE_PARAMS["start_pre_chorus_prob"]
                            + STRUCTURE_PARAMS["start_chorus_prob"],
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Verse {i}",
                            1
                            - (
                                STRUCTURE_PARAMS["start_pre_chorus_prob"]
                                + STRUCTURE_PARAMS["start_chorus_prob"]
                            ),
                        ),
                    ],
                    weight="p",
                )

        elif i < num_choruses:
            G.add_weighted_edges_from(
                [(f"Iteration {i} Start", f"Verse {i}", 1)], weight="p"
            )

        else:
            # skip to chorus/prechorus 25% of the time
            if prechorus:
                G.add_weighted_edges_from(
                    [
                        (
                            f"Iteration {i} Start",
                            f"Prechorus {i}",
                            STRUCTURE_PARAMS["skip_last_verse_prob"]
                            * (1 - STRUCTURE_PARAMS["skip_last_pre_chorus_prob"]),
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Chorus {i}",
                            STRUCTURE_PARAMS["skip_last_verse_prob"]
                            * STRUCTURE_PARAMS["skip_last_pre_chorus_prob"],
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Verse {i}",
                            1 - STRUCTURE_PARAMS["skip_last_verse_prob"],
                        ),
                    ],
                    weight="p",
                )

            else:
                G.add_weighted_edges_from(
                    [
                        (
                            f"Iteration {i} Start",
                            f"Chorus {i}",
                            STRUCTURE_PARAMS["skip_last_verse_prob"],
                        ),
                        (
                            f"Iteration {i} Start",
                            f"Verse {i}",
                            1 - STRUCTURE_PARAMS["skip_last_verse_prob"],
                        ),
                    ],
                    weight="p",
                )

        # if there is a prechorus, go from verse -> prechorus -> chorus
        if prechorus:
            G.add_weighted_edges_from(
                [
                    (f"Verse {i}", f"Prechorus {i}", 1),
                    (f"Prechorus {i}", f"Chorus {i}", 1),
                ],
                weight="p",
            )

        # otherwise, straight from verse to chorus
        else:
            G.add_weighted_edges_from([(f"Verse {i}", f"Chorus {i}", 1)], weight="p")

        # go to prechorus if prechoruses exist and we are not approaching the final chorus
        if prechorus and i < num_choruses:
            G.add_weighted_edges_from(
                [
                    (f"Verse {i}", f"Prechorus {i}", 1),
                    (f"Prechorus {i}", f"Chorus {i}", 1),
                ],
                weight="p",
            )
        elif prechorus:
            # if its the last chorus, there's a 10% chance we skip the prechorus
            G.add_weighted_edges_from(
                [
                    (
                        f"Verse {i}",
                        f"Prechorus {i}",
                        1 - STRUCTURE_PARAMS["skip_last_pre_chorus_only_prob"],
                    ),
                    (
                        f"Verse {i}",
                        f"Chorus {i}",
                        STRUCTURE_PARAMS["skip_last_pre_chorus_only_prob"],
                    ),
                    (f"Prechorus {i}", f"Chorus {i}", 1),
                ],
                weight="p",
            )

        else:
            # if no prechorus, straight to chorus
            G.add_weighted_edges_from([(f"Verse {i}", f"Chorus {i}", 1)], weight="p")

        # if there is no postchorus, straight to next placeholder
        if not postchorus:
            G.add_weighted_edges_from(
                [(f"Chorus {i}", f"Iteration {i} Middle", 1)],
                weight="p",
            )

        elif postchorus and i < num_choruses:
            # if it's not the last chorus, go to postchorus, then placeholder
            G.add_weighted_edges_from(
                [
                    (f"Chorus {i}", f"Postchorus {i}", 1),
                    (f"Postchorus {i}", f"Iteration {i} Middle", 1),
                ],
                weight="p",
            )

        else:
            # if last chorus, skip postchorus 30% of the time
            G.add_weighted_edges_from(
                [
                    (
                        f"Chorus {i}",
                        f"Iteration {i} Middle",
                        STRUCTURE_PARAMS["skip_last_post_chorus_prob"],
                    ),
                    (
                        f"Chorus {i}",
                        f"Postchorus {i}",
                        1 - STRUCTURE_PARAMS["skip_last_post_chorus_prob"],
                    ),
                    (f"Postchorus {i}", f"Iteration {i} Middle", 1),
                ],
                weight="p",
            )

        # possible key change at this point ("Truck Driver's gear change") - probability increases as we approach final chorus
        G.add_weighted_edges_from(
            [
                (
                    f"Iteration {i} Middle",
                    f"Postchorus Modulation {i}",
                    (i / num_choruses) * STRUCTURE_PARAMS["truck_drivers_base_prob"],
                ),
                (
                    f"Iteration {i} Middle",
                    f"Iteration {i} Middle II",
                    1
                    - (i / num_choruses) * STRUCTURE_PARAMS["truck_drivers_base_prob"],
                ),
                (
                    f"Postchorus Modulation {i}",
                    f"Iteration {i} Middle II",
                    1,
                ),
            ],
            weight="p",
        )

        ##  possibility of bridge and/or solo
        # if bridge before solo...
        if bridge_solo_order:
            G.add_weighted_edges_from(
                [
                    # chance of bridge increases linearly
                    (
                        f"Iteration {i} Middle II",
                        f"Bridge {i}",
                        STRUCTURE_PARAMS["bridge_base_prob"] * (i / num_choruses),
                    ),
                    (f"Bridge {i}", f"Iteration {i} Middle III", 1),
                    (
                        f"Iteration {i} Middle II",
                        f"Iteration {i} Middle III",
                        1 - STRUCTURE_PARAMS["bridge_base_prob"] * (i / num_choruses),
                    ),
                    # chance of solo (sim. increase)
                    (
                        f"Iteration {i} Middle III",
                        f"Solo {i}",
                        STRUCTURE_PARAMS["solo_base_prob"] * (i / num_choruses),
                    ),
                    (f"Solo {i}", f"Iteration {i} Ending", 1),
                    (
                        f"Iteration {i} Middle III",
                        f"Iteration {i} Ending",
                        1 - STRUCTURE_PARAMS["solo_base_prob"] * (i / num_choruses),
                    ),
                ],
                weight="p",
            )
        # if solo before bridge...
        else:
            G.add_weighted_edges_from(
                [
                    (
                        f"Iteration {i} Middle II",
                        f"Solo {i}",
                        STRUCTURE_PARAMS["solo_base_prob"] * (i / num_choruses),
                    ),
                    (f"Solo {i}", f"Iteration {i} Middle III", 1),
                    (
                        f"Iteration {i} Middle II",
                        f"Iteration {i} Middle III",
                        1 - STRUCTURE_PARAMS["solo_base_prob"] * (i / num_choruses),
                    ),
                    (
                        f"Iteration {i} Middle III",
                        f"Bridge {i}",
                        STRUCTURE_PARAMS["bridge_base_prob"] * (i / num_choruses),
                    ),
                    (f"Bridge {i}", f"Iteration {i} Ending", 1),
                    (
                        f"Iteration {i} Middle III",
                        f"Iteration {i} Ending",
                        1 - STRUCTURE_PARAMS["bridge_base_prob"] * (i / num_choruses),
                    ),
                ],
                weight="p",
            )

        # if we are not in the final iteration, go to beginning of next
        if i < num_choruses:
            G.add_weighted_edges_from(
                [
                    (
                        f"Iteration {i} Ending",
                        f"Iteration {i + 1} Start",
                        1,
                    )
                ],
                weight="p",
            )

    return ProbDAG(G)


def generate_song_structure(print_graph: bool = False, print_filepath: str = None):
    """
    Function which generates a song structure.
    """

    num_choruses, prechorus, postchorus, bridge_solo_order = get_song_variables()

    G = song_structure_graph(num_choruses, prechorus, postchorus, bridge_solo_order)
    event_type_mapping = G.get_node_attributes("event_type")

    if print_graph and print_filepath == None:
        print_filepath = (
            f"song_structure_graphs/{str(datetime.now()).replace(' ', '_')}.dot"
        )

    if print_graph:
        G.write_graphviz(print_filepath)

    raw_song_structure = G.get_random_path()

    return [
        (event, {"event_type": event_type_mapping[event]})
        for event in raw_song_structure
    ]


def variation_assign(n: int):
    section_variations = [0] * n

    # all but the first section can be varied
    for idx in range(1, n):
        # add variations with various probabilities
        add_variation = choices(
            [True, False], weights=[(idx == n - 1) * 4 + (idx + 1 == n / 2) * 2 + 1, 8]
        )[0]
        if add_variation:
            section_variations[idx] = max(section_variations) + 1

    return section_variations


def section_variation(base_variations: list):
    # most likely to vary final section
    vary_idx = choices(
        list(range(len(base_variations))),
        weights=[
            1 + (idx == len(base_variations) - 1) for idx in range(len(base_variations))
        ],
    )[0]
    new_variations = base_variations.copy()
    new_variations[vary_idx] = max(new_variations) + 1

    return new_variations


def base_section_length(n: int):
    # function which decides base chord structure in CP

    # check if n is a power of 2
    if n == 1 or int(log(n, 2)) != log(n, 2):
        return n

    else:
        # if n=8 then there is a 50% chance we repeat a 4-measure section
        keep_n = choices([True, False], weights=[8, n])[0]
        if keep_n:
            return n
        else:
            # recursively
            return base_section_length(n // 2)


def measures_assign():
    """
    A function which decides how long each section should be. Note: some sections may not actually appear in the song.
    """

    # initialize dict
    chosen_lengths = dict()

    # populate
    for section_name, length_probs in STRUCTURE_PARAMS["measure_distributions"].items():
        chosen_length = sample_weights_dict(length_probs)
        chosen_lengths[section_name] = chosen_length

    return chosen_lengths


def parse_song_structure(song_structure: list = None, initial_key: str = None):
    """Function which converts a song structure into a sequence of sections."""

    # input checker
    for elt in song_structure:
        if len(elt) != 2:
            raise ValueError(
                "every element of song_structure should be an ordered pair"
            )
        if not isinstance(elt[0], str):
            raise TypeError(
                "every element of song_structure should have a string in the first position"
            )
        if not isinstance(elt[1], dict):
            raise TypeError(
                "every element of song_structure should have a dict in the second position"
            )
        if list(elt[1].keys()) != ["event_type"]:
            raise ValueError(
                "every element of song_structure should include a dict specifying event_type"
            )

    ## parse sections with key changes

    # figure out keys
    song_key = SongKey(initial_key)

    # store lengths of various song sections
    song_section_lengths = measures_assign()

    # initialize list of sections
    sections = []

    # and dict of generators
    generators = {}

    # grab index of final section
    final_section = song_structure[
        max(
            [
                i
                for i in range(len(song_structure))
                if song_structure[i][1]["event_type"] == "section"
            ]
        )
    ]

    for elt in song_structure:
        # print(song_key.get_key())

        if elt[1]["event_type"] == "modulation":
            song_key.key_change()

        elif elt[1]["event_type"] == "section":
            # get section name by ignoring # (eg. 'Verse 4' becomes 'Verse')
            section_name = elt[0].split(" ")[0]

            if not section_name in generators:
                section_measures = song_section_lengths[section_name]
                section_kernel_length = base_section_length(section_measures)

                section_kernel = Section(
                    name=section_name,
                    variation=0,
                    key=song_key.get_key(),
                    num_measures=section_kernel_length,
                )

                generators[section_name] = {
                    "generator": ChordProgressionSelector(section_kernel),
                    "variations": variation_assign(
                        section_measures // section_kernel_length
                    ),
                }

            # get no. of section
            section_number = 1
            if len(elt[0].split(" ")) > 1:
                section_number = int(elt[0].split(" ")[1])

            section_measures = song_section_lengths[section_name]
            final_section_test = elt == final_section

            section_data = {
                "name": section_name,
                "number": section_number,
                "key": song_key.get_key(),
                "num_measures": section_measures,
                "final_section": final_section_test,
            }

            sections.append(section_data)

        else:
            # throwaway all sources/sinks
            pass

    # get count of each type of section
    section_numbers = {sec["name"]: sec["number"] for sec in sections}

    # apply variations
    for section in sections:
        section_name = section["name"]

        if section["number"] > 1:
            # possibility of changing variations
            variation_prob = 2 ** (
                -2 - (section_numbers[section_name] - section["number"])
            )

            if choices([True, False], weights=[variation_prob, 1 - variation_prob])[0]:
                generators[section_name]["variations"] = section_variation(
                    generators[section_name]["variations"]
                )

        variations = generators[section_name]["variations"]

        section_components = [
            generators[section_name]["generator"].get_variation(var, key=section["key"])
            for var in variations
        ]

        this_section = section_components[0]

        for next_section in section_components[1:]:
            this_section = this_section.concat(next_section)

        # transpose if necessary
        # this_section.transpose(section['key'])

        # potentially halve final verse
        if (
            section_name == "Verse"
            and section["number"] == section_numbers["Verse"]
            and this_section.num_measures % 2 == 0
        ):
            if bernoulli_trial(STRUCTURE_PARAMS["halve_final_verse_prob"]):
                this_section.halve(half=1)

        # potentially double final chorus
        if section_name == "Chorus" and section["number"] == section_numbers["Chorus"]:
            if bernoulli_trial(STRUCTURE_PARAMS["double_final_chorus_prob"]):
                this_section = this_section.concat(this_section)

        # make last section if necessary
        if section["final_section"]:
            this_section.make_final_section()

        section["section"] = this_section

    return sections
