#!/usr/bin/env python3
"""
Script to generate multiple songs and collect statistical information.

Generates songs with a fixed seed for reproducibility and collects:
- Song length (total measures)
- Number of sections
- Key changes
- Non-diatonic chords
- Section types and counts
"""

import sys
from pathlib import Path
import random
from numpy import random as np_random
from collections import Counter
import re
import statistics

try:
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("Agg")  # Use non-interactive backend
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Add chord-striker directory to path
SCRIPT_DIR = Path(__file__).parent
CHORD_STRIKER_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(CHORD_STRIKER_DIR))

from chord_striker.song_structure import (  # noqa: E402
    generate_song_structure,
    get_tempo,
)
from chord_striker.load_constants import (  # noqa: E402
    load_constants,
)  # noqa: E402
from chord_striker.chorder import ChordProgressionSelector  # noqa: E402
from pychord import Chord  # noqa: E402


def set_seed(seed):
    """Set the random seed for reproducibility."""
    if seed is not None:
        random.seed(seed)
        np_random.seed(seed)


def get_chord_symbols_from_selector(selector: ChordProgressionSelector):
    """
    Extract Nashville notation chord symbols from a ChordProgressionSelector.

    Uses reflection to access the private __chords_nashville attribute.
    """
    # Access private attribute via name mangling
    chords_nashville = selector._ChordProgressionSelector__chords_nashville
    return chords_nashville


def is_diatonic_to_key(chord_symbol: str) -> bool:
    """
    Check if a chord symbol is diatonic to a major key.

    In a major key, diatonic chords are:
    - I (major)
    - ii (minor)
    - iii (minor)
    - IV (major)
    - V (major)
    - vi (minor)
    - vii° (diminished, represented as 'vii')

    Non-diatonic chords include:
    - Any chord starting with 'b' (bI, bII, etc.)
    - Uppercase versions of chords that should be minor (II, III, VI)
    - Uppercase VII (when used as major instead of diminished)
    """
    if not chord_symbol:
        return False

    # Flat chords are always non-diatonic
    if chord_symbol.startswith("b"):
        return False

    # In major key, diatonic chords are:
    diatonic_symbols = {"I", "ii", "iii", "IV", "V", "vi", "vii"}

    return chord_symbol in diatonic_symbols


def parse_song_structure_with_symbols(song_structure, initial_key=None):
    """
    Modified version of parse_song_structure that also tracks chord symbols.

    Returns sections with chord_symbols included in each section data.
    """
    from chord_striker.song_structure import (
        SongKey,
        measures_assign,
        base_section_length,
        variation_assign,
        section_variation,
        STRUCTURE_PARAMS,
    )
    from chord_striker.section import Section
    from random import choices
    from chord_striker.helper_fns import bernoulli_trial

    song_key = SongKey(initial_key)
    song_section_lengths = measures_assign()
    sections = []
    generators = {}

    # Find final section
    final_section = song_structure[
        max(
            [
                i
                for i in range(len(song_structure))
                if song_structure[i][1]["event_type"] == "section"
            ]
        )
    ]

    # First pass: create sections and generators
    for elt in song_structure:
        if elt[1]["event_type"] == "modulation":
            song_key.key_change()
        elif elt[1]["event_type"] == "section":
            section_name = elt[0].split(" ")[0]

            if section_name not in generators:
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
                "chord_symbols": [],  # Will be populated
            }

            sections.append(section_data)

    # Second pass: generate sections and extract chord symbols
    section_numbers = {sec["name"]: sec["number"] for sec in sections}

    for section in sections:
        section_name = section["name"]

        if section["number"] > 1:
            variation_prob = 2 ** (
                -2 - (section_numbers[section_name] - section["number"])
            )
            if choices([True, False], weights=[variation_prob, 1 - variation_prob])[0]:
                generators[section_name]["variations"] = section_variation(
                    generators[section_name]["variations"]
                )

        variations = generators[section_name]["variations"]

        # Get chord symbols from the generator
        try:
            chord_symbols = get_chord_symbols_from_selector(
                generators[section_name]["generator"]
            )
            # Multiply by number of variations
            # (each variation uses the same base progression)
            section["chord_symbols"] = chord_symbols * len(variations)
        except Exception:
            section["chord_symbols"] = []

        section_components = [
            generators[section_name]["generator"].get_variation(var, key=section["key"])
            for var in variations
        ]

        this_section = section_components[0]
        for next_section in section_components[1:]:
            this_section = this_section.concat(next_section)

        # Handle special cases (halve, double, etc.)
        if (
            section_name == "Verse"
            and section["number"] == section_numbers["Verse"]
            and this_section.num_measures % 2 == 0
        ):
            if bernoulli_trial(STRUCTURE_PARAMS["halve_final_verse_prob"]):
                this_section.halve(half=1)
                # Adjust chord symbols if halved
                if section["chord_symbols"]:
                    section["chord_symbols"] = section["chord_symbols"][
                        : len(section["chord_symbols"]) // 2
                    ]

        if section_name == "Chorus" and section["number"] == section_numbers["Chorus"]:
            if bernoulli_trial(STRUCTURE_PARAMS["double_final_chorus_prob"]):
                this_section = this_section.concat(this_section)
                # Double chord symbols
                if section["chord_symbols"]:
                    section["chord_symbols"] = section["chord_symbols"] * 2

        if section["final_section"]:
            this_section.make_final_section()

        section["section"] = this_section

    return sections


def load_famous_progressions():
    """Load famous chord progressions once and return lookup structures."""
    try:
        import yaml
        from chord_striker.load_constants import get_constants_dir

        constants_dir = get_constants_dir()
        cp_path = constants_dir / "famous_chord_progressions.yaml"
        with open(cp_path, "r") as f:
            cp_candidates = yaml.safe_load(f)

        # Build lookup sets for fast membership testing
        famous_3 = set()
        famous_4 = set()
        blues_progs = [
            ["I", "IV", "I", "V", "IV", "I"],
            ["I", "IV", "I", "V", "IV", "I", "V"],
        ]
        blues_set = {tuple(prog) for prog in blues_progs}

        for cp in cp_candidates:
            prog = cp["progression"]
            prog_tuple = tuple(prog)
            if len(prog) == 3:
                famous_3.add(prog_tuple)
            elif len(prog) == 4:
                famous_4.add(prog_tuple)

        return famous_3, famous_4, blues_set
    except Exception:
        return set(), set(), set()


def analyze_song(
    seed: int, song_index: int, famous_3=None, famous_4=None, blues_set=None
):
    """
    Generate a single song and return statistics.

    Returns:
        dict with statistics about the song
    """
    # Set seed for this song
    set_seed(seed + song_index)

    # Generate tempo for this song
    tempo = get_tempo()

    # Generate song structure
    ss = generate_song_structure(print_graph=False, output_dir=None)

    # Parse song structure to get sections (with chord symbols)
    sections = parse_song_structure_with_symbols(ss, initial_key=None)

    # Collect statistics
    stats = {
        "song_index": song_index,
        "seed": seed + song_index,
        "tempo": tempo,
        "total_measures": 0,
        "num_sections": len(sections),
        "section_types": Counter(),
        "section_lengths": [],
        "keys": [],
        "key_changes": 0,
        "non_diatonic_chords": 0,
        "total_chords": 0,
        "chord_symbols_used": Counter(),
        "diatonic_chords": 0,
        "runtime_seconds": 0.0,
        "extensions_used": Counter(),
        "famous_progressions_used": Counter(),
        "blues_progressions_used": 0,
    }

    previous_key = None

    for section_data in sections:
        section_name = section_data["name"]
        section_key = section_data["key"]
        section_measures = section_data["num_measures"]
        chord_symbols = section_data.get("chord_symbols", [])

        # Update statistics
        stats["total_measures"] += section_measures
        stats["section_types"][section_name] += 1
        stats["section_lengths"].append(section_measures)
        stats["keys"].append(section_key)

        # Track key changes
        if previous_key is not None and section_key != previous_key:
            stats["key_changes"] += 1
        previous_key = section_key

        # Analyze chord symbols
        if chord_symbols:
            stats["total_chords"] += len(chord_symbols)
            stats["chord_symbols_used"].update(chord_symbols)

            # Count diatonic vs non-diatonic
            for symbol in chord_symbols:
                if is_diatonic_to_key(symbol):
                    stats["diatonic_chords"] += 1
                else:
                    stats["non_diatonic_chords"] += 1

        # Extract extensions from section's chord objects
        # Only sample a subset to avoid performance issues
        section_obj = section_data.get("section")
        if section_obj:
            # Sample every 4th chord to speed up processing
            chord_progression = section_obj.chord_progression
            for idx in range(0, len(chord_progression), 4):
                chord = chord_progression[idx]
                if chord is not None and isinstance(chord, Chord):
                    # Get chord components to extract extension
                    chord_str = str(chord)
                    # Check for common extension patterns
                    extension = ""
                    chord_lower = chord_str.lower()
                    if "sus" in chord_lower:
                        extension = "sus"
                    elif "dim" in chord_lower:
                        extension = "dim"
                    elif "aug" in chord_lower:
                        extension = "aug"
                    else:
                        # Look for numbers (7, 9, 11, 13, etc.)
                        numbers = re.findall(r"\d+", chord_str)
                        if numbers:
                            # Filter out common non-extension numbers
                            ext_numbers = [n for n in numbers if int(n) >= 7]
                            if ext_numbers:
                                extension = ext_numbers[-1]  # Take the highest
                    if extension:
                        stats["extensions_used"][extension] += 1

        # Check if chord symbols match famous progressions
        if chord_symbols and (famous_3 is not None or blues_set is not None):
            # Check for blues progressions (12-bar)
            # Blues progressions are only used in 12-measure sections
            if blues_set and section_measures == 12:
                for blues_prog in blues_set:
                    # Blues progressions can match at the start
                    # Also check anywhere in the sequence
                    if len(chord_symbols) >= len(blues_prog):
                        # Check if progression starts with blues pattern
                        if tuple(chord_symbols[: len(blues_prog)]) == blues_prog:
                            stats["blues_progressions_used"] += 1
                            stats["famous_progressions_used"]["blues"] += 1
                            break
                        # Check if blues pattern appears anywhere in the sequence
                        for i in range(len(chord_symbols) - len(blues_prog) + 1):
                            seq = tuple(chord_symbols[i : i + len(blues_prog)])
                            if seq == blues_prog:
                                stats["blues_progressions_used"] += 1
                                stats["famous_progressions_used"]["blues"] += 1
                                break
                        else:
                            continue
                        break

            # Check for 3-chord and 4-chord famous progressions
            if famous_3 and len(chord_symbols) >= 3:
                for i in range(len(chord_symbols) - 2):
                    seq = tuple(chord_symbols[i : i + 3])
                    if seq in famous_3:
                        stats["famous_progressions_used"]["3-chord"] += 1
                        break

            if famous_4 and len(chord_symbols) >= 4:
                for i in range(len(chord_symbols) - 3):
                    seq = tuple(chord_symbols[i : i + 4])
                    if seq in famous_4:
                        stats["famous_progressions_used"]["4-chord"] += 1
                        break

    # Calculate runtime: (measures * 4 beats/measure) / (tempo beats/minute)
    # * 60 seconds/minute
    # Time signature is 4/4, so 4 beats per measure
    beats_per_measure = 4
    total_beats = stats["total_measures"] * beats_per_measure
    runtime_minutes = total_beats / tempo
    stats["runtime_seconds"] = runtime_minutes * 60

    return stats


def collect_statistics(num_songs: int = 100, base_seed: int = 42):
    """
    Generate multiple songs and collect aggregate statistics.

    Args:
        num_songs: Number of songs to generate
        base_seed: Base seed for reproducibility

    Returns:
        dict with aggregate statistics
    """
    # Load famous progressions once before processing songs
    famous_3, famous_4, blues_set = load_famous_progressions()

    print(f"Generating {num_songs} songs with base seed {base_seed}...", flush=True)

    all_stats = []

    for i in range(num_songs):
        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1}/{num_songs} songs...", flush=True)

        try:
            stats = analyze_song(base_seed, i, famous_3, famous_4, blues_set)
            all_stats.append(stats)
        except Exception as e:
            print(f"  Error generating song {i + 1}: {e}", flush=True)
            continue

    # Check if we have any successful songs
    if not all_stats:
        print("Error: No songs were successfully generated!", flush=True)
        return {}, []

    # Aggregate statistics
    aggregate = {
        "num_songs": len(all_stats),
        "total_measures": {
            "mean": sum(s["total_measures"] for s in all_stats) / len(all_stats),
            "min": min(s["total_measures"] for s in all_stats),
            "max": max(s["total_measures"] for s in all_stats),
            "distribution": Counter(s["total_measures"] for s in all_stats),
        },
        "num_sections": {
            "mean": sum(s["num_sections"] for s in all_stats) / len(all_stats),
            "min": min(s["num_sections"] for s in all_stats),
            "max": max(s["num_sections"] for s in all_stats),
            "distribution": Counter(s["num_sections"] for s in all_stats),
        },
        "key_changes": {
            "total": sum(s["key_changes"] for s in all_stats),
            "songs_with_key_changes": sum(1 for s in all_stats if s["key_changes"] > 0),
            "mean_per_song": sum(s["key_changes"] for s in all_stats) / len(all_stats),
            "distribution": Counter(s["key_changes"] for s in all_stats),
        },
        "section_types": Counter(),
        "keys_used": Counter(),
        "section_lengths": [],
        "chord_symbols": Counter(),
        "extensions": Counter(),
        "famous_progressions": Counter(),
        "blues_progressions": 0,
        "non_diatonic_stats": {
            "total": 0,
            "songs_with_non_diatonic": 0,
            "mean_per_song": 0,
        },
        "tempo": {
            "mean": 0.0,
            "min": 0,
            "max": 0,
            "distribution": Counter(),
        },
        "runtime": {
            "mean_seconds": 0.0,
            "mean_minutes": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
            "distribution": Counter(),
        },
    }

    # Aggregate section types
    for stats in all_stats:
        aggregate["section_types"].update(stats["section_types"])
        aggregate["keys_used"].update(stats["keys"])
        aggregate["section_lengths"].extend(stats["section_lengths"])
        aggregate["chord_symbols"].update(stats["chord_symbols_used"])
        aggregate["extensions"].update(stats["extensions_used"])
        aggregate["famous_progressions"].update(stats["famous_progressions_used"])
        aggregate["blues_progressions"] += stats["blues_progressions_used"]
        aggregate["non_diatonic_stats"]["total"] += stats["non_diatonic_chords"]
        if stats["non_diatonic_chords"] > 0:
            aggregate["non_diatonic_stats"]["songs_with_non_diatonic"] += 1

    aggregate["non_diatonic_stats"]["mean_per_song"] = aggregate["non_diatonic_stats"][
        "total"
    ] / len(all_stats)

    # Aggregate tempo statistics
    tempos = [s["tempo"] for s in all_stats]
    aggregate["tempo"]["mean"] = sum(tempos) / len(tempos)
    aggregate["tempo"]["median"] = statistics.median(tempos)
    aggregate["tempo"]["min"] = min(tempos)
    aggregate["tempo"]["max"] = max(tempos)
    aggregate["tempo"]["distribution"] = Counter(tempos)

    # Aggregate runtime statistics
    runtimes = [s["runtime_seconds"] for s in all_stats]
    aggregate["runtime"]["mean_seconds"] = sum(runtimes) / len(runtimes)
    aggregate["runtime"]["mean_minutes"] = aggregate["runtime"]["mean_seconds"] / 60
    aggregate["runtime"]["min_seconds"] = min(runtimes)
    aggregate["runtime"]["max_seconds"] = max(runtimes)
    # Round runtime to nearest 5 seconds for distribution
    aggregate["runtime"]["distribution"] = Counter(round(r / 5) * 5 for r in runtimes)

    aggregate["section_lengths"] = {
        "mean": sum(aggregate["section_lengths"]) / len(aggregate["section_lengths"]),
        "min": min(aggregate["section_lengths"]),
        "max": max(aggregate["section_lengths"]),
        "distribution": Counter(aggregate["section_lengths"]),
    }

    return aggregate, all_stats


def print_statistics(aggregate: dict, all_stats: list):
    """Print collected statistics in a readable format."""
    print("\n" + "=" * 60)
    print("SONG GENERATION STATISTICS")
    print("=" * 60)

    print(f"\nTotal songs analyzed: {aggregate['num_songs']}")

    print("\n--- Song Length (Total Measures) ---")
    measures = aggregate["total_measures"]
    print(f"  Mean: {measures['mean']:.1f} measures")
    print(f"  Min: {measures['min']} measures")
    print(f"  Max: {measures['max']} measures")
    print("  Distribution:")
    for length, count in sorted(measures["distribution"].items()):
        pct = 100 * count / aggregate["num_songs"]
        print(f"    {length} measures: {count} songs ({pct:.1f}%)")

    print("\n--- Number of Sections ---")
    sections = aggregate["num_sections"]
    print(f"  Mean: {sections['mean']:.1f} sections")
    print(f"  Min: {sections['min']} sections")
    print(f"  Max: {sections['max']} sections")
    print("  Distribution:")
    for num, count in sorted(sections["distribution"].items()):
        pct = 100 * count / aggregate["num_songs"]
        print(f"    {num} sections: {count} songs ({pct:.1f}%)")

    print("\n--- Section Types ---")
    for section_type, count in aggregate["section_types"].most_common():
        print(f"  {section_type}: {count} occurrences")

    print("\n--- Section Lengths ---")
    lengths = aggregate["section_lengths"]
    print(f"  Mean: {lengths['mean']:.1f} measures per section")
    print(f"  Min: {lengths['min']} measures")
    print(f"  Max: {lengths['max']} measures")
    print("  Distribution:")
    for length, count in sorted(lengths["distribution"].items())[:10]:  # Top 10
        print(f"    {length} measures: {count} sections")

    print("\n--- Key Changes ---")
    key_changes = aggregate["key_changes"]
    print(f"  Total key changes: {key_changes['total']}")
    print(
        f"  Songs with key changes: {key_changes['songs_with_key_changes']} "
        f"({100 * key_changes['songs_with_key_changes'] / aggregate['num_songs']:.1f}%)"
    )
    print(f"  Mean key changes per song: {key_changes['mean_per_song']:.2f}")
    print("  Distribution:")
    for num, count in sorted(key_changes["distribution"].items()):
        pct = 100 * count / aggregate["num_songs"]
        print(f"    {num} key changes: {count} songs ({pct:.1f}%)")

    print("\n--- Keys Used ---")
    for key, count in aggregate["keys_used"].most_common():
        total_sections = sum(aggregate["keys_used"].values())
        pct = 100 * count / total_sections
        print(f"  {key}: {count} sections ({pct:.1f}%)")

    print("\n--- Chord Symbols Used ---")
    print(f"  Total unique chord symbols: {len(aggregate['chord_symbols'])}")
    print("  Most common chord symbols:")
    for symbol, count in aggregate["chord_symbols"].most_common(10):
        print(f"    {symbol}: {count} occurrences")

    print("\n--- Non-Diatonic Chords ---")
    non_diatonic = aggregate["non_diatonic_stats"]
    print(f"  Total non-diatonic chords: {non_diatonic['total']}")
    songs_with_nd = non_diatonic["songs_with_non_diatonic"]
    pct = 100 * songs_with_nd / aggregate["num_songs"]
    print(f"  Songs with non-diatonic chords: {songs_with_nd} ({pct:.1f}%)")
    print(f"  Mean non-diatonic chords per song: {non_diatonic['mean_per_song']:.2f}")

    print("\n--- Tempo (BPM) ---")
    tempo_stats = aggregate["tempo"]
    print(f"  Mean: {tempo_stats['mean']:.1f} BPM")
    print(f"  Median: {tempo_stats['median']:.1f} BPM")
    print(f"  Min: {tempo_stats['min']} BPM")
    print(f"  Max: {tempo_stats['max']} BPM")
    print("  Distribution (top 10):")
    for tempo_val, count in tempo_stats["distribution"].most_common(10):
        pct = 100 * count / aggregate["num_songs"]
        print(f"    {tempo_val} BPM: {count} songs ({pct:.1f}%)")

    print("\n--- Runtime ---")
    runtime_stats = aggregate["runtime"]
    mean_min = runtime_stats["mean_minutes"]
    mean_sec = runtime_stats["mean_seconds"]
    print(f"  Mean: {mean_min:.2f} minutes ({mean_sec:.1f} seconds)")
    min_min = runtime_stats["min_seconds"] / 60
    min_sec = runtime_stats["min_seconds"]
    print(f"  Min: {min_min:.2f} minutes ({min_sec:.1f} seconds)")
    max_min = runtime_stats["max_seconds"] / 60
    max_sec = runtime_stats["max_seconds"]
    print(f"  Max: {max_min:.2f} minutes ({max_sec:.1f} seconds)")
    print("  Distribution (rounded to 5-second intervals):")
    for runtime_val, count in sorted(runtime_stats["distribution"].items())[:10]:
        pct = 100 * count / aggregate["num_songs"]
        minutes = runtime_val / 60
        print(f"    {minutes:.1f} min ({runtime_val:.0f}s): {count} songs ({pct:.1f}%)")

    print("\n" + "=" * 60)


def create_visualizations(aggregate: dict, all_stats: list, output_dir: Path):
    """
    Create visualization graphs for the statistics.

    Args:
        aggregate: Aggregate statistics dictionary
        all_stats: List of individual song statistics
        output_dir: Directory to save graphs
    """
    if not HAS_MATPLOTLIB:
        msg = "\nWarning: matplotlib not available, skipping visualizations"
        print(msg, flush=True)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Set style
    style_name = "seaborn-v0_8-darkgrid"
    if style_name not in plt.style.available:
        style_name = "default"
    plt.style.use(style_name)

    # 1. Song Length Distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    measures = [s["total_measures"] for s in all_stats]
    ax.hist(measures, bins=20, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Total Measures")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Song Length (Measures)")
    ax.axvline(
        aggregate["total_measures"]["mean"],
        color="red",
        linestyle="--",
        label=f"Mean: {aggregate['total_measures']['mean']:.1f}",
    )
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "song_length_distribution.png", dpi=150)
    plt.close()

    # 2. Runtime Distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    runtimes = [s["runtime_seconds"] / 60 for s in all_stats]  # Convert to minutes
    ax.hist(runtimes, bins=20, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Runtime (minutes)")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Song Runtime")
    mean_min = aggregate["runtime"]["mean_minutes"]
    ax.axvline(mean_min, color="red", linestyle="--", label=f"Mean: {mean_min:.2f} min")
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "runtime_distribution.png", dpi=150)
    plt.close()

    # 3. Tempo Distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    tempos = [s["tempo"] for s in all_stats]
    ax.hist(tempos, bins=20, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Tempo (BPM)")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Tempo")
    mean_tempo = aggregate["tempo"]["mean"]
    ax.axvline(
        mean_tempo, color="red", linestyle="--", label=f"Mean: {mean_tempo:.1f} BPM"
    )
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "tempo_distribution.png", dpi=150)
    plt.close()

    # 4. Number of Sections Distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    num_sections = [s["num_sections"] for s in all_stats]
    ax.hist(
        num_sections,
        bins=range(min(num_sections), max(num_sections) + 2),
        edgecolor="black",
        alpha=0.7,
    )
    ax.set_xlabel("Number of Sections")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Number of Sections per Song")
    mean_sections = aggregate["num_sections"]["mean"]
    ax.axvline(
        mean_sections, color="red", linestyle="--", label=f"Mean: {mean_sections:.1f}"
    )
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "num_sections_distribution.png", dpi=150)
    plt.close()

    # 5. Key Changes Distribution (discrete bar chart)
    fig, ax = plt.subplots(figsize=(10, 6))
    key_changes = [s["key_changes"] for s in all_stats]
    key_changes_counter = Counter(key_changes)
    max_changes = max(key_changes) if key_changes else 0

    # Create discrete bar chart
    x_values = list(range(0, max_changes + 1))
    y_values = [key_changes_counter.get(x, 0) for x in x_values]

    ax.bar(x_values, y_values, edgecolor="black", alpha=0.7, width=0.8)
    ax.set_xlabel("Number of Key Changes")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Key Changes per Song")
    ax.set_xticks(x_values)

    mean_kc = aggregate["key_changes"]["mean_per_song"]
    if mean_kc > 0:
        ax.axvline(mean_kc, color="red", linestyle="--", label=f"Mean: {mean_kc:.2f}")
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_dir / "key_changes_distribution.png", dpi=150)
    plt.close()

    # 6. Non-Diatonic Chords per Song
    fig, ax = plt.subplots(figsize=(10, 6))
    non_diatonic = [s["non_diatonic_chords"] for s in all_stats]
    ax.hist(non_diatonic, bins=20, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Number of Non-Diatonic Chords")
    ax.set_ylabel("Number of Songs")
    ax.set_title("Distribution of Non-Diatonic Chords per Song")
    mean_nd = aggregate["non_diatonic_stats"]["mean_per_song"]
    ax.axvline(mean_nd, color="red", linestyle="--", label=f"Mean: {mean_nd:.1f}")
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "non_diatonic_chords_distribution.png", dpi=150)
    plt.close()

    # 7. Most Common Keys Bar Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    keys_used = aggregate["keys_used"]
    keys = list(keys_used.keys())
    counts = list(keys_used.values())
    ax.bar(keys, counts, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Key")
    ax.set_ylabel("Total Sections")
    ax.set_title("Most Common Keys")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "most_common_keys.png", dpi=150)
    plt.close()

    # 8. Most Common Chord Extensions
    fig, ax = plt.subplots(figsize=(10, 6))
    extensions = aggregate["extensions"]
    if extensions:
        top_extensions = extensions.most_common(15)
        ext_names = [ext for ext, _ in top_extensions]
        ext_counts = [count for _, count in top_extensions]
        ax.bar(ext_names, ext_counts, edgecolor="black", alpha=0.7)
        ax.set_xlabel("Extension")
        ax.set_ylabel("Total Occurrences")
        ax.set_title("Most Common Chord Extensions")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_dir / "most_common_extensions.png", dpi=150)
        plt.close()

    # 9. Famous Chord Progressions Prevalence
    fig, ax = plt.subplots(figsize=(10, 6))
    famous_progs = aggregate["famous_progressions"]
    blues_count = aggregate["blues_progressions"]

    # Prepare data
    categories = []
    counts = []

    # Always show blues category, even if zero, to indicate we're checking for it
    categories.append("Blues (12-bar)")
    counts.append(blues_count)
    if "3-chord" in famous_progs:
        categories.append("3-chord")
        counts.append(famous_progs["3-chord"])
    if "4-chord" in famous_progs:
        categories.append("4-chord")
        counts.append(famous_progs["4-chord"])

    if categories:
        ax.bar(categories, counts, edgecolor="black", alpha=0.7)
        ax.set_xlabel("Progression Type")
        ax.set_ylabel("Number of Uses")
        ax.set_title("Famous Chord Progressions Prevalence")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_dir / "famous_progressions.png", dpi=150)
        plt.close()

    # 10. Section Types Bar Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    section_types = aggregate["section_types"]
    types = list(section_types.keys())
    counts = list(section_types.values())
    ax.bar(types, counts, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Section Type")
    ax.set_ylabel("Total Occurrences")
    ax.set_title("Section Types Distribution")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "section_types.png", dpi=150)
    plt.close()

    # 11. Most Common Chords (colored by diatonic/non-diatonic)
    fig, ax = plt.subplots(figsize=(12, 6))
    chord_symbols = aggregate["chord_symbols"]
    # Get top N chords (e.g., top 20)
    top_chords = chord_symbols.most_common(20)

    chord_names = [chord for chord, _ in top_chords]
    chord_counts = [count for _, count in top_chords]

    # Color bars based on whether chord is diatonic
    colors = [
        "#2ecc71" if is_diatonic_to_key(chord) else "#e74c3c" for chord in chord_names
    ]

    ax.bar(chord_names, chord_counts, edgecolor="black", alpha=0.7, color=colors)
    ax.set_xlabel("Chord Symbol")
    ax.set_ylabel("Total Occurrences")
    ax.set_title("Most Common Chord Symbols (Green=Diatonic, Red=Non-Diatonic)")
    plt.xticks(rotation=45, ha="right")

    # Add legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="#2ecc71", label="Diatonic"),
        Patch(facecolor="#e74c3c", label="Non-Diatonic"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    plt.tight_layout()
    plt.savefig(output_dir / "most_common_chords.png", dpi=150)
    plt.close()

    print(f"\nVisualizations saved to {output_dir}/", flush=True)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate songs and collect statistical information"
    )
    parser.add_argument(
        "--num-songs",
        type=int,
        default=1000,
        help="Number of songs to generate (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for statistics (default: print to console)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("audit_output"),
        help="Output directory for graphs (default: audit_output)",
    )
    parser.add_argument(
        "--no-graphs",
        action="store_true",
        help="Skip generating graphs",
    )

    args = parser.parse_args()

    # Load constants
    load_constants()

    # Collect statistics
    aggregate, all_stats = collect_statistics(
        num_songs=args.num_songs, base_seed=args.seed
    )

    # Print statistics
    print_statistics(aggregate, all_stats)

    # Create visualizations
    if not args.no_graphs:
        create_visualizations(aggregate, all_stats, args.output_dir)

    # Save to file if requested
    if args.output:
        import json

        # Convert Counter objects to dicts for JSON serialization
        def convert_for_json(obj):
            if isinstance(obj, Counter):
                return dict(obj)
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_for_json(item) for item in obj]
            elif isinstance(obj, set):
                return list(obj)
            return obj

        output_data = {
            "aggregate": convert_for_json(aggregate),
            "individual_songs": convert_for_json(all_stats),
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nStatistics saved to {args.output}")


if __name__ == "__main__":
    main()
