from chord_striker.song_structure import (
    get_tempo,
    generate_song_structure,
    parse_song_structure,
)
from chord_striker.create_chord_chart import ChordChart
from chord_striker.load_constants import load_constants
import random
from numpy import random as np_random
import click
import sys


def set_seed(seed):
    """
    Set the random seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)
        np_random.seed(seed)


def create_song(
    key,
    tempo,
    seed,
    song_name,
    output_dir="output",
    print_graph=False,
    constants_dir=None,
):
    """
    Create a song with the given key, tempo, and seed.

    Args:
        key: The key of the song
        tempo: The tempo of the song
        seed: Random seed for reproducibility
        song_name: Name of the song
        output_dir: Directory to save the output
        print_graph: Whether to print the song structure graph
        constants_dir: Directory containing custom YAML files for constants
    """
    # Set the random seed if provided
    set_seed(seed)

    # Load custom constants if provided
    if constants_dir:
        load_constants(constants_dir)
        # Reload modules that import from load_constants to get new references
        import importlib
        import chord_striker.song_structure
        import chord_striker.helper_fns
        import chord_striker.chorder
        importlib.reload(chord_striker.song_structure)
        importlib.reload(chord_striker.helper_fns)
        importlib.reload(chord_striker.chorder)
        # Re-import functions to get updated references
        from chord_striker.song_structure import (
            get_tempo,
            generate_song_structure,
            parse_song_structure,
        )
        # Update the module-level references
        sys.modules[__name__].get_tempo = get_tempo
        sys.modules[__name__].generate_song_structure = generate_song_structure
        sys.modules[__name__].parse_song_structure = parse_song_structure

    # Generate a random tempo if not provided
    if tempo is None:
        tempo = get_tempo()

    # Create song structure
    ss = generate_song_structure(print_graph=print_graph, output_dir=output_dir)

    # Add chords
    sections = parse_song_structure(ss, key)

    # Create a chord chart; generate PDF and MIDI files in 'output_dir'
    # with the song name
    chord_chart = ChordChart(sections, tempo, song_name, output_dir)
    chord_chart.generate_pdf_midi()


def create_album(num_songs, seeds=[], parent_dir="output", constants_dir=None):
    """
    Create an album with the specified number of songs and seeds.
    """
    for i in range(num_songs):
        song_name = f"{i + 1}"
        seed = seeds[i] if i < len(seeds) else None
        create_song(
            key=None,
            tempo=None,
            seed=seed,
            song_name=song_name,
            output_dir=f"{parent_dir}/{song_name}",
            constants_dir=constants_dir,
        )


@click.command()
@click.option(
    "--num_songs",
    default=1,
    type=int,
    help=(
        "Number of songs to generate (default: 1); if this is greater "
        "than 1, an album will be created, and following arguments "
        "will be ignored"
    ),
)
@click.option(
    "--key",
    default=None,
    help="Key for the chord chart; randomly generated if not supplied (default: None)",
)
@click.option(
    "--tempo",
    default=None,
    type=int,
    help=(
        "Tempo for the chord chart; randomly generated if not suppplied (default: None)"
    ),
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help=(
        "Seed for the random number generators; randomly generated if "
        "not suppplied (default: None)"
    ),
)
@click.option(
    "--song_name", default="Random Song", help="Name of the song (default: Random Song)"
)
@click.option(
    "--output_dir",
    default="output",
    help="Directory to save the generated song or album (default: output)",
)
@click.option(
    "--print_graph",
    default=False,
    help="Print the graph of the song structure (default: False)",
)
@click.option(
    "--constants_dir",
    default=None,
    help="Directory containing custom YAML files for constants (default: None)",
)
def main(
    num_songs, key, tempo, seed, song_name, output_dir, print_graph, constants_dir
):
    """
    Main function to create a song or an album.
    """
    if num_songs > 1:
        create_album(num_songs, parent_dir=output_dir, constants_dir=constants_dir)
    else:
        create_song(key, tempo, seed, song_name, output_dir, print_graph, constants_dir)


if __name__ == "__main__":
    main()
