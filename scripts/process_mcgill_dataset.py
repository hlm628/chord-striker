#!/usr/bin/env python3

import os
import json
import requests
import zipfile
from collections import defaultdict
from pathlib import Path
import yaml
import tarfile
from chord_striker.load_constants import KEYS
from pychord import Chord
from chord_striker.chorder import chord_parser
import re
import click


def download_mcgill_dataset(output_dir):
    """Download the Billboard dataset."""
    url = "https://www.dropbox.com/s/2lvny9ves8kns4o/billboard-2.0-salami_chords.tar.gz?dl=1"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tar_path = output_dir / "billboard-2.0-salami_chords.tar.gz"
    data_dir_path = output_dir / "McGill-Billboard"
    if not data_dir_path.exists():
        print("Downloading Billboard dataset...")
        response = requests.get(url)
        with open(tar_path, "wb") as f:
            f.write(response.content)

    # Extract the tar.gz file
    print("Extracting dataset...")
    with tarfile.open(tar_path, "r:gz") as tar_ref:
        tar_ref.extractall(output_dir)


def parse_chord(chord_str, key):
    """Parse a chord string into Nashville notation and extension.

    Args:
        chord_str: String in format "root:extension"
        key: Key to convert to Nashville notation.
    """
    # All chords should be in the format "root:extension"
    try:
        root, ext = chord_str.split(":")
        root = root.strip()
        ext = ext.strip()

        # there may also be an inversion
        if "/" in ext:
            ext, inversion = ext.split("/")

        # Validate root is a valid note
        if root not in KEYS:
            print(f"Warning: Invalid root note: {root}")
            return None, None

        # Validate key
        if key not in KEYS:
            print(f"Warning: Invalid key: {key}")
            return None, None

        # Drop anything at the end of ext in brackets (print warning)
        if "(" in ext:
            print(f"Warning: Dropping anything after first bracket in {chord_str}")
            ext = ext.split("(")[0]

        # If ext is "maj", "maj6" or "maj13", drop the "maj"
        if ext in ["maj", "maj6", "maj13"]:
            ext = ext.replace("maj", "")

        # If ext contains "min", replace with "m"
        if "min" in ext:
            ext = ext.replace("min", "m")

    except:
        print(f"Warning: Invalid chord format: {chord_str}")
        return None, None

    try:
        # Parse to PyChord
        chord = Chord(root + ext)
    except:
        print(f"Warning: Extension not recognised by PyChord: {chord_str}")
        return None, None

    try:
        # Get the scale degree (1-7) relative to the key
        key_index = KEYS.index(key)
        root_index = KEYS.index(root)
        semitones = (root_index - key_index) % 12

        # Convert semitones to scale degree (1-7)
        semitone_to_degree = {
            0: "I",
            1: "bII",
            2: "II",
            3: "bIII",
            4: "III",
            5: "IV",
            6: "bV",
            7: "V",
            8: "bVI",
            9: "VI",
            10: "bVII",
            11: "VII",
        }

        nashville = semitone_to_degree[semitones]

        # If it's a minor chord, make it lowercase
        if (len(ext) > 0 and ext[0] == "m" and ext[:3] != "maj") or ext == "dim":
            nashville = nashville.lower()

        # for lower case chords, drop the "m" from the start of an extension
        if nashville.islower() and len(ext) > 0 and ext[0] == "m":
            ext = ext[1:]

        return nashville, ext

    except ValueError:
        print(f"Warning: Could not convert chord to Nashville notation: {chord_str}")
        return None, None


def analyse_chords(data_dir, output_dir):
    """Analyze chord transitions from the dataset."""
    data_dir = Path(data_dir)

    # Init dictionaries to store transitions, extensions and chord progressions
    transitions = {}
    extensions = {}
    progressions = []  # Changed to list to match YAML format

    # Add the blues progressions from defaults
    progressions.extend(
        [
            {
                "progression": ["I", "IV", "I", "V", "IV", "I"],
                "weight": 2,
                "tag": "twelve-bar blues",
                "blues": True,
            },
            {
                "progression": ["I", "IV", "I", "V", "IV", "I", "V"],
                "weight": 2,
                "tag": "twelve-bar blues",
                "blues": True,
            },
        ]
    )

    # Find all salami-chords.txt files in numbered subdirectories
    chord_files = list(data_dir.glob("*/salami_chords.txt"))
    print(f"Found {len(chord_files)} chord files to analyze")

    for file in chord_files:
        print(f"Processing {file}...")
        sections = parse_salami(file)

        for section in sections:
            # look for famous chord progressions
            if len(section) >= 3 and not (None, None) in section:
                # Check for repeated 3 or 4 chord sequences
                for seq_len in [3, 4]:
                    if len(section) >= seq_len * 2:  # Need at least 2 repetitions
                        for i in range(len(section) - seq_len + 1):
                            # Get the sequence
                            seq = tuple(c[0] for c in section[i : i + seq_len])
                            # Check if this sequence repeats
                            for j in range(i + seq_len, len(section) - seq_len + 1):
                                next_seq = tuple(c[0] for c in section[j : j + seq_len])
                                if seq == next_seq:
                                    # Found a repeated sequence, add it to progressions
                                    found = False
                                    for p in progressions:
                                        if p["progression"] == list(seq):
                                            p["weight"] += 1
                                            found = True
                                            break
                                    if not found:
                                        progressions.append(
                                            {"progression": list(seq), "weight": 1}
                                        )
                                    break  # Stop looking for more repetitions of this sequence

            # now look for transitions
            first_chord = section[0]
            if first_chord[0] is not None:
                if "start" not in transitions:
                    transitions["start"] = {}
                if first_chord[0] not in transitions["start"]:
                    transitions["start"][first_chord[0]] = 0
                transitions["start"][first_chord[0]] += 1

            for i in range(len(section) - 1):
                current_chord = section[i]
                next_chord = section[i + 1]
                if (
                    current_chord[0] is not None
                    and next_chord[0] is not None
                    and current_chord[0] != next_chord[0]
                ):
                    if current_chord[0] not in transitions:
                        transitions[current_chord[0]] = {}
                    if next_chord[0] not in transitions[current_chord[0]]:
                        transitions[current_chord[0]][next_chord[0]] = 0
                    transitions[current_chord[0]][next_chord[0]] += 1

            # and extensions
            for c in section:
                if c != (None, None) and c[1] != "":
                    if c[0] not in extensions:
                        extensions[c[0]] = {}
                    if c[1] not in extensions[c[0]]:
                        extensions[c[0]][c[1]] = 0
                    extensions[c[0]][c[1]] += 1

    # Save the results
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_yaml(transitions, output_dir / "chord_change_probs.yaml")
    save_yaml(extensions, output_dir / "chord_extensions.yaml")
    save_yaml(progressions, output_dir / "famous_chord_progressions.yaml")


def standardise_note(note):
    """Convert enharmonic spellings to standard form.

    Args:
        note: A note name (e.g. "Db", "D#", etc.)

    Returns:
        The standardised note name (e.g. "C#", "Eb", etc.)
    """
    enharmonic_map = {
        "Cb": "B",
        "Db": "C#",
        "D#": "Eb",
        "Gb": "F#",
        "G#": "Ab",
        "A#": "Bb",
    }
    return enharmonic_map.get(note, note)


def parse_salami(file):
    """Parse a salami file into a list of chords and key."""
    with open(file, "r") as f:
        content = f.readlines()

    # Collapse all spaces to single spaces and remove the first word
    content = [" ".join(l.split()[1:]) for l in content]

    tonic_lines = [idx for idx, l in enumerate(content) if l.startswith("tonic:")]
    if len(tonic_lines) == 0:
        raise ValueError("No tonic line found")
    # convert into dict with line number and tonic
    tonic_dict = {
        idx: standardise_note(content[idx].split("tonic:")[1].strip())
        for idx in tonic_lines
    }

    # lines where sections begin contain a pipe, but do not start with them
    section_lines = [
        idx for idx, l in enumerate(content) if "|" in l and not l.startswith("|")
    ]

    # init a list of sections
    sections = []

    # figure out the chords in each section, and the key
    for section_line in section_lines:
        last_key_idx = max([idx for idx in tonic_lines if idx < section_line])
        tonic = tonic_dict[last_key_idx]

        # now figure out the chords
        last_section_line = min(
            [idx for idx in section_lines if idx > section_line] + [len(content)]
        )

        chords = []
        for line in content[section_line:last_section_line]:
            if "|" in line:
                chords_line = line.split("|")[1:-1]
                # also split on spaces
                chords_line = [l.split() for l in chords_line]
                # flatten
                chords_line = sum(chords_line, [])
                # filter out empty strings, dots, and pauses
                chords_line = [
                    c.strip()
                    for c in chords_line
                    if c.strip() and c.strip() != "." and c.strip() != "&pause"
                ]
                chords.extend(chords_line)

        # Parse the chords relative to the tonic
        nashville_chords = [parse_chord(c, tonic) for c in chords]
        # drop list entries which repeat the previous entry
        nashville_chords = [
            c
            for i, c in enumerate(nashville_chords)
            if i == 0 or c[0] != nashville_chords[i - 1][0]
        ]

        # Figure out whether the tonic is major or minor, by comparing chords
        tonic_major_count = 0
        tonic_minor_count = 0
        for c in nashville_chords:
            if c[0] in ["I", "ii", "iii", "IV", "V", "vi", "vii"]:
                tonic_major_count += 1
            elif c[0] in ["i", "II", "bIII", "iv", "v", "bVI", "bVII"]:
                tonic_minor_count += 1

        if tonic_major_count > tonic_minor_count:
            key = tonic
        else:
            key = KEYS[(KEYS.index(tonic) + 3) % 12]

            # reparse the chords relative to the key
            nashville_chords = [parse_chord(c, key) for c in chords]
            nashville_chords = [
                c
                for i, c in enumerate(nashville_chords)
                if i == 0 or c[0] != nashville_chords[i - 1][0]
            ]

        sections.append(nashville_chords)

    return sections


def save_yaml(data, filename):
    """Save data to a YAML file."""

    # create parent directory if it doesn't exist
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    # For chord progressions, format each entry as a string
    if "famous_chord_progressions.yaml" in str(filename):
        # Sort progressions: non-blues by weight (descending), blues at the bottom
        non_blues = [p for p in data if not p.get("blues", False)]
        blues = [p for p in data if p.get("blues", False)]
        sorted_data = sorted(non_blues, key=lambda x: x["weight"], reverse=True) + blues

        formatted_data = []
        for entry in sorted_data:
            # Format progression as a single line
            progression_str = f"[{', '.join(entry['progression'])}]"
            # Build the entry string
            entry_str = f"- progression: {progression_str}\n  weight: {entry['weight']}"
            if "tag" in entry:
                entry_str += f"\n  tag: {entry['tag']}"
            if "blues" in entry:
                entry_str += f"\n  blues: {str(entry['blues']).lower()}"
            formatted_data.append(entry_str)
        # Join with newlines and write
        with open(filename, "w") as f:
            f.write("\n".join(formatted_data))
    else:
        # For other files, sort dictionaries by weight
        if "chord_extensions.yaml" in str(filename) or "chord_change_probs.yaml" in str(
            filename
        ):
            # Create a new dictionary with sorted values
            sorted_data = {}
            # For chord_change_probs, put 'start' first
            if "chord_change_probs.yaml" in str(filename):
                if "start" in data:
                    sorted_data["start"] = dict(
                        sorted(data["start"].items(), key=lambda x: x[1], reverse=True)
                    )
            # Sort remaining keys alphabetically
            for key in sorted(data.keys()):
                if key != "start":  # Skip 'start' as it's already handled
                    value = data[key]
                    if isinstance(value, dict):
                        # Sort the inner dictionary by value (weight) in descending order
                        sorted_data[key] = dict(
                            sorted(value.items(), key=lambda x: x[1], reverse=True)
                        )
                    else:
                        sorted_data[key] = value
            data = sorted_data

        # Use standard YAML dump
        with open(filename, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


@click.command()
@click.option(
    "--input-dir",
    type=click.Path(exists=True),
    default="data/McGill-Billboard",
    help="Directory containing the McGill Billboard dataset",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="constants/mcgill_billboard",
    help="Directory to save the generated YAML files",
)
@click.option(
    "--download/--no-download",
    default=True,
    help="Whether to download the dataset if it doesn't exist",
)
def main(input_dir, output_dir, download):
    """Process the McGill Billboard dataset to generate chord transition and extension data."""
    if download:
        download_mcgill_dataset(input_dir)

    # Analyze progressions, transitions and extensions
    analyse_chords(input_dir, output_dir)

    print(f"Analysis complete! Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
