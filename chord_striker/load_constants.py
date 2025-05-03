from random import choices
import yaml

ALLOWED_SYMBOLS = ["I", "II", "III", "IV", "V", "VI", "VII"]
ALLOWED_SYMBOLS = ALLOWED_SYMBOLS + [c.lower() for c in ALLOWED_SYMBOLS]
ALLOWED_SYMBOLS = ALLOWED_SYMBOLS + ["b" + c for c in ALLOWED_SYMBOLS]


def is_probability(value):
    """
    A function to check if a value is a valid probability.
    """
    if not isinstance(value, (int, float)):
        raise TypeError("value must be a float")
    if value < 0:
        raise ValueError("value must be non-negative")
    if value > 1:
        raise ValueError("value must be less than or equal to 1")

    return True


def get_key_probs(key_prob_path="constants/key_probabilities.yaml"):
    """
    A function to load the key probabilities from a yaml file.
    """

    with open(key_prob_path, "r") as f:
        key_probs = yaml.safe_load(f)

    # check that keys are C-B in order
    keys = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    for key in keys:
        if not key in key_probs:
            raise KeyError(f"key {key} not found in key probabilities")
    # check that all values are non-negative floats
    for key in keys:
        if not isinstance(key_probs[key], (int, float)):
            raise TypeError(f"key {key} must be a float")
        if key_probs[key] < 0:
            raise ValueError(f"key {key} must be non-negative")

    return keys, key_probs


def get_CC_probs(cc_prob_path="constants/chord_change_probs.yaml"):
    """
    A function to load the chord change probabilities from a yaml file.
    """

    with open(cc_prob_path, "r") as f:
        cc_probs = yaml.safe_load(f)

    # replace "start" key with None
    cc_probs[None] = cc_probs.pop("start")

    # set the prob for all over chords to 0
    for key in cc_probs.keys():
        for k in ALLOWED_SYMBOLS:
            if k not in cc_probs[key]:
                cc_probs[key][k] = 0

    return cc_probs


class ExtensionSelector:
    def __init__(self, ext_path="constants/chord_extensions.yaml"):
        """
        A class to select chord extensions based on a dictionary of weights.
        The dictionary is loaded from a yaml file.
        """

        self.__ext_dict = dict()

        with open(ext_path, "r") as f:
            proposed_extensions = yaml.safe_load(f)

        # check that all keys are valid
        for key in proposed_extensions.keys():
            if not key in ALLOWED_SYMBOLS:
                raise ValueError(
                    "key must be one of I, II, III, IV, V, VI, VII, i, ii, iii, iv, v, vi, vii, optionally with a prefix of 'b'"
                )

            # check that value is a dictionary, where keys are strings and values are floats in [0,1]
            if not isinstance(proposed_extensions[key], dict):
                raise TypeError("value must be a dictionary")
            if not all(isinstance(k, str) for k in proposed_extensions[key].keys()):
                raise TypeError("keys of value must be strings")
            if not all(
                isinstance(v, (int, float)) for v in proposed_extensions[key].values()
            ):
                raise TypeError("values of value must be floats")
            if not all(v >= 0 for v in proposed_extensions[key].values()):
                raise ValueError("values of value must be >= 0")
            if not all(v <= 1 for v in proposed_extensions[key].values()):
                raise ValueError("values of value must be <= 1")

        for chord in proposed_extensions:
            # add extension weights to dictionary
            for extension, weight in proposed_extensions[chord].items():
                self.add_extension(chord, extension, weight)

        # for each key in the dictionary, add the empty extension with weight 1
        for chord in self.__ext_dict.keys():
            if "" not in self.__ext_dict[chord]:
                self.__ext_dict[chord][""] = 1

    def add_extension(self, chord, extension, weight):
        if chord not in self.__ext_dict:
            self.__ext_dict[chord] = {}
        self.__ext_dict[chord][extension] = weight

    def get_ext(self, chord):
        possible_exts = list(self.__ext_dict[chord].keys())
        ext_weights = [self.__ext_dict[chord][k] for k in possible_exts]

        ext = choices(possible_exts, weights=ext_weights)[0]

        return ext


class FamousCPSelector:
    def __init__(self, cp_path="constants/famous_chord_progressions.yaml"):
        """
        A class to select famous chord progressions based on a dictionary of weights.
        The dictionary is loaded from a yaml file.
        """

        self.__cp_dict = dict()

        with open(cp_path, "r") as f:
            cp_candidates = yaml.safe_load(f)

        for cp in cp_candidates:
            progression, weight = cp["progression"], cp["weight"]
            blues = cp.get("blues", False)  # Default to False if not specified
            self.add_progression(progression, weight, blues)

    def add_progression(self, progression, weight, blues=False):
        # check that progression is list of allowable chords
        if not isinstance(progression, list):
            raise TypeError("progression must be a list")

        for elt in progression:
            if not (elt in ALLOWED_SYMBOLS):
                raise ValueError("chord progression must contain chords!")

        if not isinstance(weight, (int, float)):
            raise TypeError("weight must be a real number >=0")

        if weight < 0:
            raise ValueError("weights cannot be negative")

        # get CP length
        n = len(progression)

        # if it's 12 bar blues, the key is '12 bar blues'
        if blues:
            n = "12 bar blues"

        new_data = (progression, weight)

        if not n in self.__cp_dict:
            self.__cp_dict[n] = []

        self.__cp_dict[n].append(new_data)

    def get_prog(self, key):
        if not key in self.__cp_dict:
            raise KeyError("key must be one of 3,4,'12 bar blues'")

        possible_CPs = self.__cp_dict[key]

        CPs, w = [x[0] for x in possible_CPs], [x[1] for x in possible_CPs]

        this_CP = choices(CPs, weights=w)[0]

        return this_CP


def load_params(structure_parameter_path="constants/structure_params.yaml"):
    """
    A function to load the variables from a yaml file.
    """

    with open(structure_parameter_path, "r") as f:
        params = yaml.safe_load(f)

    # check any keys ending in "_prob" are valid probabilities
    for key in params.keys():
        if key.endswith("_prob"):
            if not is_probability(params[key]):
                raise ValueError(f"{key} must be a probability")

    return params


CHORD_CHANGE_PROBS = get_CC_probs()
CHORD_EXTENSIONS = ExtensionSelector()
FAMOUS_CHORD_PROGRESSIONS = FamousCPSelector()
KEYS, KEY_PROBABILITIES = get_key_probs()
STRUCTURE_PARAMS = load_params()
