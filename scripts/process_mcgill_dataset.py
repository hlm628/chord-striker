#!/usr/bin/env python3

import requests
from collections import defaultdict
from pathlib import Path
import yaml
import tarfile
from chord_striker.load_constants import KEYS
from pychord import Chord
import click
import pandas as pd

MODE_MAP = {
    "ionian": ["I", "ii", "iii", "IV", "V", "vi", "vii"],
    "aeolian": ["i", "ii", "bIII", "iv", "v", "bVI", "bVII"],
    "mixolydian": ["I", "ii", "iii", "IV", "v", "vi", "bVII"],
    "dorian": ["i", "ii", "bIII", "IV", "v", "vi", "bVII"],
    "lydian": ["I", "II", "iii", "bv", "V", "vi", "vii"],
    "phrygian": ["i", "bII", "bIII", "iv", "v", "bVI", "bvii"],
    "locrian": ["i", "bII", "biii", "iv", "bV", "bVI", "bvii"],
}

MODE_SEMITONE_MAP = {
    "ionian": 0,
    "dorian": 2,
    "phrygian": 3,
    "lydian": 4,
    "mixolydian": 5,
    "aeolian": 7,
    "locrian": 9,
}


def download_mcgill_dataset(output_dir):
    """Download the Billboard dataset and metadata."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download metadata if it doesn't exist
    metadata_path = Path("data/billboard-2.0-index.csv")
    if not metadata_path.exists():
        print("Downloading Billboard metadata...")
        metadata_url = (
            "https://www.dropbox.com/s/o0olz0uwl9z9stb/billboard-2.0-index.csv?dl=1"
        )
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(metadata_url)
        with open(metadata_path, "wb") as f:
            f.write(response.content)

    # Download and extract the chord dataset
    url = "https://www.dropbox.com/s/2lvny9ves8kns4o/billboard-2.0-salami_chords.tar.gz?dl=1"
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

        # Convert enharmonic spellings to standard form
        root = standardise_note(root)

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

        # If ext is "maj" or "maj6", drop the "maj"
        if ext in ["maj", "maj6"]:
            ext = ext.replace("maj", "")

        # If ext contains "min", replace with "m"
        if "min" in ext:
            ext = ext.replace("min", "m")

    except Exception:
        print(f"Warning: Invalid chord format: {chord_str}")
        return None, None

    try:
        # Parse to PyChord
        _ = Chord(root + ext)  # Verify parsing works
    except Exception:
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


def analyse_chords(data_dir, output_dir, valid_ids=None):
    """Analyze chord transitions from the dataset.

    Args:
        data_dir: Directory containing the McGill Billboard dataset
        output_dir: Directory to save the processed data
        valid_ids: Set of valid IDs to process. If None, process all files.
    """
    data_dir = Path(data_dir)

    # Init dictionaries to store transitions, extensions and chord progressions
    transitions = {}
    extensions = {}
    progressions = []  # Changed to list to match YAML format
    mode_stats = {mode: 0 for mode in MODE_MAP.keys()}  # Track statistics for all modes
    key_stats = {key: 0 for key in KEYS}  # Track statistics for all keys

    # Initialize song structure statistics
    section_counts = defaultdict(int)
    section_lengths = defaultdict(list)
    sections_per_song = defaultdict(lambda: defaultdict(int))  # Track sections per song
    valid_sections = {"intro", "verse", "chorus", "outro", "bridge"}

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
    # Handle both direct structure (data_dir/*/salami_chords.txt) and
    # nested structure (data_dir/McGill-Billboard/*/salami_chords.txt)
    chord_files = list(data_dir.glob("*/salami_chords.txt"))
    # If no files found, check for nested McGill-Billboard directory
    if len(chord_files) == 0:
        nested_dir = data_dir / "McGill-Billboard"
        if nested_dir.exists():
            chord_files = list(nested_dir.glob("*/salami_chords.txt"))
            print(
                f"Found {len(chord_files)} chord files in nested directory: "
                f"{nested_dir}"
            )
        else:
            print(f"Found {len(chord_files)} chord files to analyse")
    else:
        print(f"Found {len(chord_files)} chord files to analyse")

    # Filter files by valid_ids if provided
    if valid_ids is not None:
        chord_files = [f for f in chord_files if f.parent.name in valid_ids]
        print(f"Filtered to {len(chord_files)} files in the specified year range")

    for file in chord_files:
        print(f"Processing {file}...")
        sections, section_modes, first_key, song_structure, sections_original = (
            parse_salami(file)
        )

        # Track the first key of each song
        if first_key is not None:
            key_stats[first_key] += 1

        # Track song structure statistics
        for section_type, num_measures in song_structure:
            if section_type.lower() in valid_sections:
                section_counts[section_type.lower()] += 1
                section_lengths[section_type.lower()].append(num_measures)
                sections_per_song[file.parent.name][section_type.lower()] += 1

        for section_idx, (section, mode) in enumerate(zip(sections, section_modes)):
            # Track mode statistics
            mode_stats[mode] += 1

            # Get original (non-deduplicated) section for extension counting
            section_original = (
                sections_original[section_idx]
                if section_idx < len(sections_original)
                else section
            )

            # look for famous chord progressions
            if len(section) >= 3 and (None, None) not in section:
                # Check for repeated 3 or 4 chord sequences
                for seq_len in [3, 4]:
                    if len(section) >= seq_len * 2:  # Need at least 2 repetitions
                        for i in range(len(section) - seq_len + 1):
                            # Get the sequence
                            seq = tuple(c[0] for c in section[i : i + seq_len])
                            # Skip if it's just alternating between two chords
                            if seq_len == 3 and seq[0] == seq[2] and seq[0] != seq[1]:
                                continue
                            if seq_len == 4 and seq[0] == seq[2] and seq[1] == seq[3]:
                                continue
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
                                    # Stop looking for more repetitions of
                                    # this sequence
                                    break

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

            # and extensions (use original section to count all occurrences,
            # not just unique ones)
            for c in section_original:
                if c != (None, None) and c[1] != "":
                    if c[0] not in extensions:
                        extensions[c[0]] = {}
                    if c[1] not in extensions[c[0]]:
                        extensions[c[0]][c[1]] = 0
                    extensions[c[0]][c[1]] += 1

    # Print mode statistics
    total_sections = sum(mode_stats.values())
    print("\nMode Statistics:")
    print(f"Total sections analyzed: {total_sections}")
    if total_sections > 0:
        for mode, count in sorted(mode_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"{mode}: {count} ({count / total_sections * 100:.1f}%)")

    # Print key statistics
    total_songs = sum(key_stats.values())
    print("\nKey Statistics:")
    print(f"Total songs analyzed: {total_songs}")
    if total_songs > 0:
        for key, count in sorted(key_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"{key}: {count} ({count / total_songs * 100:.1f}%)")

    # Calculate and print song structure statistics
    print("\nSong Structure Statistics:")
    total_sections = sum(section_counts.values())
    print(f"Total sections analyzed: {total_sections}")
    if total_sections == 0:
        print("Warning: No sections found to analyze!")
        return

    # Calculate section counts per song
    choruses_per_song = defaultdict(int)
    for song_sections in sections_per_song.values():
        choruses_per_song[song_sections["chorus"]] += 1

    # Create song structure statistics dictionary
    structure_stats = {
        "measure_distributions": {
            section.capitalize(): {
                2**i: sum(
                    1 for length_val in lengths if 2**i <= length_val < 2 ** (i + 1)
                )
                for i in range(6)  # This will cover lengths 1, 2, 4, 8, 16, 32
            }
            for section, lengths in section_lengths.items()
        },
        "num_choruses_probs": {
            num: count
            for num, count in sorted(choruses_per_song.items())
            if 2 <= num <= 7
        },
    }

    # Filter out measures < 4 and > 32 for verses and choruses
    for section in ["Verse", "Chorus"]:
        if section in structure_stats["measure_distributions"]:
            # Only keep powers of 2 between 4 and 32
            structure_stats["measure_distributions"][section] = {
                k: v
                for k, v in structure_stats["measure_distributions"][section].items()
                if 4 <= k <= 32
            }

    # Load default structure parameters
    default_params_path = Path("constants/defaults/structure_params.yaml")
    with open(default_params_path, "r") as f:
        default_params = yaml.safe_load(f)

    # Update only the relevant fields in default_params
    for key in structure_stats["measure_distributions"].keys():
        default_params["measure_distributions"][key] = structure_stats[
            "measure_distributions"
        ][key]
    default_params["num_choruses_probs"] = structure_stats["num_choruses_probs"]

    # Save the results
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_yaml(transitions, output_dir / "chord_change_probs.yaml")
    save_yaml(extensions, output_dir / "chord_extensions.yaml")
    save_yaml(progressions, output_dir / "famous_chord_progressions.yaml")
    save_yaml(key_stats, output_dir / "key_probs.yaml")
    save_yaml(default_params, output_dir / "structure_params.yaml")


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


def detect_mode(chords):
    """Detect the mode of a chord progression.

    Args:
        chords: List of chords
    """
    # init dictionary to count chords, using keys from MODE_MAP
    chord_counts = {mode: 0 for mode in MODE_MAP.keys()}
    for chord in chords:
        for mode in MODE_MAP.keys():
            if chord[0] in MODE_MAP[mode]:
                chord_counts[mode] += 1
                break
    # return the mode with the most chords
    return max(chord_counts, key=chord_counts.get)


def parse_salami(file):
    """Parse a salami file into a list of chords and key."""
    with open(file, "r") as f:
        content = f.readlines()

    # Collapse all spaces to single spaces and remove the first word
    content = [" ".join(line.split()[1:]) for line in content]

    tonic_lines = [idx for idx, line in enumerate(content) if line.startswith("tonic:")]
    if len(tonic_lines) == 0:
        raise ValueError("No tonic line found")
    # convert into dict with line number and tonic
    tonic_dict = {
        idx: standardise_note(content[idx].split("tonic:")[1].strip())
        for idx in tonic_lines
    }

    # lines where sections begin contain a pipe, but do not start with them
    section_lines = [
        idx
        for idx, line in enumerate(content)
        if "|" in line and not line.startswith("|")
    ]

    # init a list of sections
    sections = []
    # Store original (non-deduplicated) sections for extension counting
    sections_original_all = []
    section_modes = []  # Track the original mode of each section
    first_key = None  # Track the first key of the song
    song_structure = []

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
                chords_line = [line_part.split() for line_part in chords_line]
                # flatten
                chords_line = sum(chords_line, [])
                # filter out empty strings, dots, and pauses
                chords_line = [
                    c.strip()
                    for c in chords_line
                    if c.strip() and c.strip() != "." and c.strip() != "&pause"
                ]
                chords.extend(chords_line)

        # also save the section type and the number of measures
        section_type = content[section_line].split("|")[0].split(", ")[1]
        # get the number of measures by counting the number of "|" in the section lines
        num_measures = sum(
            line.count("|") - 1 for line in content[section_line:last_section_line]
        )

        # Ensure verse and chorus lengths are between 4 and 32 measures
        if section_type.lower() in ["verse", "chorus"]:
            # Round to nearest power of 2 between 4 and 32
            if num_measures < 4:
                num_measures = 4
            elif num_measures > 32:
                num_measures = 32
            else:
                # Find nearest power of 2
                powers = [4, 8, 16, 32]
                num_measures = min(powers, key=lambda x: abs(x - num_measures))

        song_structure.append((section_type, num_measures))

        # Parse the chords relative to the tonic
        nashville_chords = [parse_chord(c, tonic) for c in chords]

        # Detect the mode before any transposition
        mode = detect_mode(nashville_chords)
        section_modes.append(mode)

        # Convert mode to semitone offset
        semitone_offset = MODE_SEMITONE_MAP[mode]
        if semitone_offset != 0:
            # Transpose the tonic
            tonic_index = KEYS.index(tonic)
            new_tonic = KEYS[(tonic_index + semitone_offset) % 12]
            # Reparse the chords relative to the new tonic
            nashville_chords = [parse_chord(c, new_tonic) for c in chords]
        else:
            new_tonic = tonic

        # Track the first key of the song
        if first_key is None:
            first_key = new_tonic

        # Store original chords (before deduplication) for extension counting.
        # We need to count all occurrences of chord+extension pairs,
        # not just unique ones
        sections_original = nashville_chords.copy()

        # drop list entries which repeat the previous entry
        # (Only deduplicate for transitions - we want to track actual chord changes)
        nashville_chords = [
            c
            for i, c in enumerate(nashville_chords)
            if i == 0 or c[0] != nashville_chords[i - 1][0]
        ]

        sections.append(nashville_chords)
        sections_original_all.append(sections_original)

    return sections, section_modes, first_key, song_structure, sections_original_all


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
                        # Sort the inner dictionary by value (weight) in
                        # descending order
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
    type=click.Path(),
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
@click.option(
    "--first-year",
    type=int,
    default=None,
    help="First year to include in the dataset (inclusive)",
)
@click.option(
    "--last-year",
    type=int,
    default=None,
    help=(
        "Last year to include in the dataset (inclusive). If None, "
        "includes all years up to present."
    ),
)
def main(input_dir, output_dir, download, first_year, last_year):
    """
    Process the McGill Billboard dataset and save the results.

    Args:
        input_dir: Directory containing the McGill Billboard dataset
        output_dir: Directory to save the processed data
        download: Whether to download the dataset if it doesn't exist
        first_year: First year to include in the dataset (inclusive)
        last_year: Last year to include in the dataset (inclusive).
            If None, includes all years up to present.
    """
    input_dir = Path(input_dir)
    if download:
        download_mcgill_dataset(input_dir)
    elif not input_dir.exists():
        raise FileNotFoundError(
            f"Input directory '{input_dir}' does not exist. "
            "Use --download to download the dataset."
        )

    # Load metadata
    metadata_path = Path("data/billboard-2.0-index.csv")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {metadata_path}")

    # Read metadata and convert chart_date to datetime
    metadata = pd.read_csv(metadata_path)
    metadata["chart_date"] = pd.to_datetime(metadata["chart_date"])
    metadata["year"] = metadata["chart_date"].dt.year

    if first_year is None:
        first_year = metadata["year"].min()

    # Filter by year
    if last_year is None:
        last_year = metadata["year"].max()

    year_mask = (metadata["year"] >= first_year) & (metadata["year"] <= last_year)
    filtered_metadata = metadata[year_mask]

    # Get list of valid IDs for the year range, formatted as 4-digit strings
    valid_ids = set(filtered_metadata["id"].astype(int).astype(str).str.zfill(4))

    # Analyze progressions, transitions and extensions
    analyse_chords(input_dir, output_dir, valid_ids)

    print(f"Analysis complete! Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
