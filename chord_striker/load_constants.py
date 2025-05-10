from random import choices
import yaml
import os
from pathlib import Path

ALLOWED_SYMBOLS = ["I", "II", "III", "IV", "V", "VI", "VII"]
ALLOWED_SYMBOLS = ALLOWED_SYMBOLS + [c.lower() for c in ALLOWED_SYMBOLS]
ALLOWED_SYMBOLS = ALLOWED_SYMBOLS + ["b" + c for c in ALLOWED_SYMBOLS]

# Constants will be loaded into these global variables
STRUCTURE_PARAMS = {}
CHORD_CHANGE_PROBS = {}
KEY_PROBABILITIES = {}
KEYS = []


def load_constants(constants_dir=None):
    """
    Load constants from YAML files. If constants_dir is provided, it will look for files there,
    otherwise uses constants/defaults.

    Args:
        constants_dir: Optional directory containing custom YAML files. If None, uses constants/defaults.
    """
    global STRUCTURE_PARAMS, CHORD_CHANGE_PROBS, KEY_PROBABILITIES, KEYS

    # Determine the constants directory to use
    if constants_dir is None:
        constants_dir = Path("constants/defaults")
    else:
        constants_dir = Path(constants_dir)

    # Load structure parameters
    structure_params_path = constants_dir / "structure_params.yaml"
    with open(structure_params_path, "r") as f:
        STRUCTURE_PARAMS = yaml.safe_load(f)

    # Load chord change probabilities
    chord_change_probs_path = constants_dir / "chord_change_probs.yaml"
    with open(chord_change_probs_path, "r") as f:
        CHORD_CHANGE_PROBS = yaml.safe_load(f)
        # replace "start" key with None
        CHORD_CHANGE_PROBS[None] = CHORD_CHANGE_PROBS.pop("start")
        # set the prob for all over chords to 0
        for key in CHORD_CHANGE_PROBS.keys():
            for k in ALLOWED_SYMBOLS:
                if k not in CHORD_CHANGE_PROBS[key]:
                    CHORD_CHANGE_PROBS[key][k] = 0

    # Load key probabilities
    key_probs_path = constants_dir / "key_probs.yaml"
    with open(key_probs_path, "r") as f:
        KEY_PROBABILITIES = yaml.safe_load(f)
        # check that keys are C-B in order
        KEYS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        for key in KEYS:
            if not key in KEY_PROBABILITIES:
                raise KeyError(f"key {key} not found in key probabilities")
            if not isinstance(KEY_PROBABILITIES[key], (int, float)):
                raise TypeError(f"key {key} must be a float")
            if KEY_PROBABILITIES[key] < 0:
                raise ValueError(f"key {key} must be non-negative")


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


class ExtensionSelector:
    def __init__(self, constants_dir=None):
        """
        A class to select chord extensions based on a dictionary of weights.
        The dictionary is loaded from a yaml file.
        """
        self.__ext_dict = dict()

        # Determine the constants directory to use
        if constants_dir is None:
            constants_dir = Path("constants/defaults")
        else:
            constants_dir = Path(constants_dir)

        # Load extensions
        ext_path = constants_dir / "chord_extensions.yaml"
        if not ext_path.exists():
            raise FileNotFoundError(f"Chord extensions file not found at {ext_path}")

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

        # Initialize all allowed symbols with default extensions
        for symbol in ALLOWED_SYMBOLS:
            if symbol.startswith("b"):
                # For flat chords, use the same extensions as their non-flat counterparts
                base_symbol = symbol[1:]
                if base_symbol in proposed_extensions:
                    # Filter out power chords
                    self.__ext_dict[symbol] = {
                        ext: weight
                        for ext, weight in proposed_extensions[base_symbol].items()
                        if ext != "5"
                    }
                else:
                    # Default extensions for flat chords (excluding power chords)
                    self.__ext_dict[symbol] = {
                        "7": 1000,
                        "maj7": 300,
                        "sus4": 200,
                        "9": 100,
                    }
            else:
                # For non-flat chords, use extensions from YAML or defaults
                if symbol in proposed_extensions:
                    # Filter out power chords
                    self.__ext_dict[symbol] = {
                        ext: weight
                        for ext, weight in proposed_extensions[symbol].items()
                        if ext != "5"
                    }
                else:
                    # Default extensions for non-flat chords (excluding power chords)
                    self.__ext_dict[symbol] = {
                        "7": 1000,
                        "maj7": 300,
                        "sus4": 200,
                        "9": 100,
                    }

    def add_extension(self, chord, extension, weight):
        if chord not in self.__ext_dict:
            self.__ext_dict[chord] = {}
        self.__ext_dict[chord][extension] = weight

    def get_ext(self, chord):
        possible_exts = list(self.__ext_dict[chord].keys())
        if not possible_exts:  # If no extensions defined, return empty string
            return ""
        ext_weights = [self.__ext_dict[chord][k] for k in possible_exts]
        ext = choices(possible_exts, weights=ext_weights)[0]
        return ext


class FamousCPSelector:
    def __init__(self, constants_dir=None):
        """
        A class to select famous chord progressions based on a dictionary of weights.
        The dictionary is loaded from a yaml file.
        """
        self.__cp_dict = dict()

        # Determine the constants directory to use
        if constants_dir is None:
            user_constants = Path("constants/user")
            if user_constants.exists() and any(user_constants.iterdir()):
                constants_dir = user_constants
            else:
                constants_dir = Path("constants/defaults")
        else:
            constants_dir = Path(constants_dir)

        # Load famous chord progressions
        cp_path = constants_dir / "famous_chord_progressions.yaml"
        if not cp_path.exists():
            cp_path = Path("constants/defaults/famous_chord_progressions.yaml")

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


# Initialize global variables
CHORD_EXTENSIONS = ExtensionSelector()
FAMOUS_CHORD_PROGRESSIONS = FamousCPSelector()

# Load constants on module import
load_constants()
