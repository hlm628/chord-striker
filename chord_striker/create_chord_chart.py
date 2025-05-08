from chord_striker.section import Section
from subprocess import run
from pychord import Chord
from numpy import diff
import os
import shutil


def lilypond_accidental(sharp_or_flat: str) -> str:
    """
    A helper function to convert '#' or 'b' into corresponding
    Lilypond syntax.

    Args:
        sharp_or_flat: '#' or 'b'.
    Returns:
        'es' or 'is'.
    """

    if sharp_or_flat == "b":
        return "es"
    elif sharp_or_flat == "#":
        return "is"
    else:
        return ValueError('Input to lilypond_accidental must be "#" or "b"')


def chord_converter(chord: Chord, note_duration: int = None) -> str:
    """
    A function which converts Chord objects from pychord into
    strings which are recognized by Lilypond.

    Args:
        chord: A Pychord object.
        note_duration: (Optional) How long the chord should last, in
        Lilypond format.

    Returns:
        A string which can be interpreted as a chord in Lilypond.

    """

    # get relevant attributes
    chord_root = chord.root.lower()
    chord_quality = str(chord.quality)

    # root
    lilypond_chord = chord_root[0]

    # apply accidentals
    if len(chord_root) > 1:
        lilypond_chord += lilypond_accidental(chord_root[1])

    # add duration if necessary
    if note_duration is not None:
        lilypond_chord += str(note_duration)

    # add modifier
    if len(chord_quality) > 0:
        lilypond_chord += ":" + chord_quality

    # add slash chord root
    if chord.on is not None:
        chord_slash_root = chord.on.lower()
        lilypond_chord += "/" + chord_slash_root[0]

        if len(chord_slash_root) > 1:
            lilypond_chord += lilypond_accidental(chord_slash_root[1])

    return lilypond_chord


def AB_binary_encoding(n: int) -> str:
    """
    A helpful function for converting a positive integer n into
    a "binary" string, where '0' and '1' are replaced by
    'A' and 'B'.

    Args:
        n: The positive integer to be encoded.

    Returns:
        The "binary AB" string which encodes n.

    """

    return format(n, "b").replace("0", "A").replace("1", "B")


class ChordChart:
    """
    A class which creates a Lilypond file which allows the results of the generated
    chord structure to be viewed in a readable PDF.

    Args:
        song_sections: A list of song sections, as returned by the parse_song_structure function.
        song_tempo: The tempo of the song.
        song_name: The name of the song, to be used in output Lilypond file.
        display_format: The manner in which song sections should be displayed in the score.
        output_dir: Directory to save output files (default: 'tmp')
        ly_path: Custom path for the Lilypond file (overrides output_dir and song_name)
    """

    def __init__(
        self,
        song_sections: list,
        song_tempo: int = 120,
        song_name: str = "default",
        output_dir: str = "tmp",
        display_format: str = "inline",
        ly_path: str = None,
    ):
        self.__song_sections = song_sections
        self.__tempo = song_tempo
        self.__format = display_format
        self.__song_name = song_name

        # check valid format supplied
        if not self.__format in ["inline"]:
            raise ValueError(f"{self.__format} is not a valid format")

        # Set up file paths
        if ly_path:
            self.__lilypond_filename = ly_path
            # Extract just the filename without extension for derived outputs
            base_name = os.path.splitext(os.path.basename(ly_path))[0]
            base_dir = os.path.dirname(ly_path)

            # Set chords file path in same directory as main lily file
            self.__lilypond_chords_filename = os.path.join(
                base_dir, f"{base_name}_chords.ly"
            )
        else:
            # Default behavior using song_name and optional output_dir
            self.__lilypond_filename = os.path.join(output_dir, f"{song_name}.ly")
            self.__lilypond_chords_filename = os.path.join(
                output_dir, f"{song_name}_chords.ly"
            )

        # Ensure output directory exists
        os.makedirs(
            os.path.dirname(os.path.abspath(self.__lilypond_filename)), exist_ok=True
        )

        # open files
        self.__lilypond_file = open(self.__lilypond_filename, "w+")
        self.__lilypond_chords_file = open(self.__lilypond_chords_filename, "w+")

        # Store path to reference files
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.__ref_files_dir = "lilypond_assets"

        # add file header
        self.__add_file_header()

        # add sections
        self.__add_sections()

        # add midi
        self.__add_midi()

        # close files
        self.__lilypond_file.close()
        self.__lilypond_chords_file.close()

    def __get_lilypond_version(self) -> str:
        """
        A helper function to extract the current version of Lilypond.

        Returns:
            The version of Lilypond currently installed.
        """
        # call the version via system command
        lilypond_response = run(["lilypond", "-v"], capture_output=True)

        # convert to string and extract version
        lilypond_version = str(lilypond_response).split("\\n")[0].split(" ")[-1]

        return lilypond_version

    def __add_file_header(self):
        """
        Add header to Lilypond file, with basic song info and configuration.
        """
        # add lilypond version
        lilypond_version = self.__get_lilypond_version()
        version_specification = "\\version" + ' "' + lilypond_version + '"'
        self.__lilypond_file.writelines([version_specification])

        # Calculate relative path to reference files from the lily file location
        rel_path_to_ref = os.path.relpath(
            self.__ref_files_dir,
            os.path.dirname(os.path.abspath(self.__lilypond_filename)),
        )

        # allow slash symbol to be included inline
        self.__lilypond_file.writelines(
            [f'\n\n\\include "{os.path.join(rel_path_to_ref, "slash_symbol.ly")}"']
        )

        # Add song name as title in the header
        self.__lilypond_file.writelines(
            [
                "\n\n\\header {",
                f'\n  title = "{self.__song_name}"',  # Add song name as title
                '\n  tagline = ""',  # Remove LilyPond watermark
                "\n}",
            ]
        )

        # Add paper block with PDF filename in footer (right-aligned)
        pdf_filename = os.path.basename(self.__lilypond_filename).replace(".ly", ".pdf")
        self.__lilypond_file.writelines(
            [
                "\n\n\\paper {",
                # Right-align both odd and even footers
                f'\n  oddFooterMarkup = \\markup {{ \\small \\fill-line {{ \\null \\right-align {{ "{pdf_filename}" }} }} }}',
                f'\n  evenFooterMarkup = \\markup {{ \\small \\fill-line {{ \\null \\right-align {{ "{pdf_filename}" }} }} }}',
                "\n}",
            ]
        )

        # Define tempo variable (will be available globally)
        self.__lilypond_file.writelines([f"\ntempo = {self.__tempo}"])

        # add tempo information
        self.__add_tempo(rel_path_to_ref)

    def __add_tempo(self, rel_path_to_ref=None):
        """
        Helper method to add tempo to file header.
        """
        # add tempo block for MIDI
        self.__lilypond_file.writelines(
            [
                "\n\ntempoBlock = {",
                f"\n  \\tempo 4 = {self.__tempo}",
                "\n  \\override Score.MetronomeMark.padding = #-6",
                "\n}",
            ]
        )

        # Find path to add_tempo.ly
        if rel_path_to_ref is None:
            rel_path_to_ref = os.path.relpath(
                self.__ref_files_dir,
                os.path.dirname(os.path.abspath(self.__lilypond_filename)),
            )

        # Read the template file
        tempo_path = os.path.join(self.__ref_files_dir, "add_tempo.ly")
        with open(tempo_path, "r") as f:
            tempo_template = f.read()

        # Replace placeholder with actual tempo
        tempo_content = tempo_template.replace(
            "TEMPO_VALUE_PLACEHOLDER", str(self.__tempo)
        )

        # Write directly to the LilyPond file
        self.__lilypond_file.writelines([f"\n\n{tempo_content}"])

    def __get_section_counts(self):
        """
        A helpful function to figure how many of each section are in the song.
        This can be used to remove the "1" from sui generis sections, for example, in the printed score.
        """
        section_names = {section["name"] for section in self.__song_sections}

        return {
            name: max(
                [
                    section["number"]
                    for section in self.__song_sections
                    if section["name"] == name
                ]
            )
            for name in section_names
        }

    def __add_sections(self):
        """
        Populate the Lilypond chords file and add sections to main Lilypond file.
        """
        # Calculate relative path to chords file from the lily file
        rel_path_to_chords = os.path.basename(self.__lilypond_chords_filename)

        # tell main file to include chord progressions
        self.__lilypond_file.writelines([f'\n\n\\include "{rel_path_to_chords}"'])

        # populate
        for section_idx in range(len(self.__song_sections)):
            self.__generate_section_chord_progression(section_idx)
            self.__add_section(section_idx)

    def __generate_section_chord_progression(self, section_idx: int):
        """
        A function which takes a section and adds the corresponding chord progression to the
        Lilypond chords file, with the name "chords" + section_encoding.

        Args:
            section_idx: The index of the section in self.__song_sections.
        """
        # check index
        if not section_idx in list(range(len(self.__song_sections))):
            raise ValueError("Provided section index not valid")

        # encode index in 'A/B binary' format
        section_encoding = AB_binary_encoding(section_idx)

        # extract section
        section = self.__song_sections[section_idx]["section"]

        # open new progression
        self.__lilypond_chords_file.writelines(
            ["\n\n" * (section_idx > 0) + f"chords{section_encoding} = \\chords" + "{"]
        )

        # add opening bar line
        self.__lilypond_chords_file.writelines(['\n  \\bar "|"'])

        ## add chords

        # get the chord changes
        chord_changes = section.changes()

        # figure out what the smallest unit is
        beats_per_measure = int(section.time_signature.split("/")[0])
        units_per_beat = section.units_per_beat
        units_per_measure = beats_per_measure * units_per_beat

        # get indices of either chord changes or 'slashes', and the lengths of these changes
        chord_change_positions = [
            i for i in range(len(chord_changes)) if chord_changes[i] is not None
        ]
        chord_lengths = diff(chord_change_positions + [section.total_units]).tolist()

        # add chords to file
        for i in range(len(chord_change_positions)):
            # initialize new line
            chord_line = "\n  "

            # get index of ith chord change
            CC_index = chord_change_positions[i]

            new_chord, chord_length = chord_changes[CC_index], chord_lengths[i]

            # handle the slashes specially
            if new_chord is not None and not isinstance(new_chord, Chord):
                if new_chord != "/":
                    raise ValueError(
                        "There is something strange in the chord progression"
                    )
                # use the chord from last time
                new_chord = chord
                # print slash in output
                chord_line += "\\chordSlash "
            else:
                chord = new_chord

            # get Lilypond chord length
            lilypond_chord_length = units_per_measure // chord_length

            # this should have required no rounding
            if lilypond_chord_length != (units_per_measure / chord_length):
                raise ValueError(
                    "Something has gone wrong with chord lengths \n Check the way slashes are being added"
                )

            # get chord in Lilypond format
            new_chord_lilypond = chord_converter(chord, lilypond_chord_length)

            # write to file
            chord_line += new_chord_lilypond
            self.__lilypond_chords_file.writelines([chord_line])

        # add closing bar line
        if section.final_section:
            self.__lilypond_chords_file.writelines(['\n  \\bar "|."'])
        else:
            self.__lilypond_chords_file.writelines(['\n  \\bar "|"'])

        # close progression
        self.__lilypond_chords_file.writelines(["\n}"])

    def __add_section(self, section_idx: str):
        """
        Add a new song section to Lilypond file.

        Args:
            section_idx: The index of the section in self.__song_sections.
        """
        # check index
        if not section_idx in list(range(len(self.__song_sections))):
            raise ValueError("Provided section index not valid")

        # encode index in 'A/B binary' format
        section_encoding = AB_binary_encoding(section_idx)

        # get type of section (e.g 'Verse')
        section_title = self.__song_sections[section_idx]["name"]

        # see if there are more than one of these in the song
        section_count = self.__get_section_counts()[section_title]

        if section_count > 1:
            section_number = self.__song_sections[section_idx]["number"]
            section_title += f" {section_number}"

        if self.__format == "inline":
            # Calculate relative path to reference files
            rel_path_to_ref = os.path.relpath(
                self.__ref_files_dir,
                os.path.dirname(os.path.abspath(self.__lilypond_filename)),
            )

            # open new score
            self.__lilypond_file.writelines(["\n\n\\score {"])

            ## add chord progression
            self.__lilypond_file.writelines(
                [
                    "\n\n  {",
                    f"\n    \\chords {{\\chords{section_encoding}}}",
                    "\n  }",
                ]
            )

            # add section title
            self.__lilypond_file.writelines(
                [
                    "\n\n  \\header {",
                    f'\n    piece = "{section_title}"',
                    "\n  }",
                ]
            )

            # add bar line rendering instructions
            self.__lilypond_file.writelines(
                [
                    f'\n\n  \\include "{os.path.join(rel_path_to_ref, "chord_chart_bar_lines.ly")}"'
                ]
            )

            # close score
            self.__lilypond_file.writelines(["\n\n}"])

    def __add_midi(self):
        """
        Add the lines which generate MIDI to the Lilypond file.
        """
        # open new 'score'
        self.__lilypond_file.writelines(["\n\n\\score {", "\n  {"])

        # insert chords
        for section_idx in range(len(self.__song_sections)):
            section_encoding = AB_binary_encoding(section_idx)

            self.__lilypond_file.writelines(
                [
                    f"\n    \\chords {{\\chords{section_encoding}}}",
                ]
            )

        self.__lilypond_file.writelines(["\n  }"])

        # specify MIDI (with tempo)
        self.__lilypond_file.writelines(
            [
                "\n\n  \\midi {",
                f"\n    \\tempo 4 = {self.__tempo}",
                # ensure only a single MIDI instrument is used
                "\n\n  \\context {",
                "\n      \\Score",
                "\n      midiChannelMapping = #'instrument",
                "\n    }",
                "\n  }",
            ]
        )

        # close score
        self.__lilypond_file.writelines(["\n}"])

    def generate_pdf_midi(self):
        """
        Run Lilypond and generate PDF and MIDI files in the output directory.

        Returns:
            tuple: (lilypond_result, pdf_path, midi_path) containing the command result
                and the paths to the generated files
        """
        # Get the output directory and base filename
        output_dir = os.path.dirname(self.__lilypond_filename)
        base_name = os.path.splitext(os.path.basename(self.__lilypond_filename))[0]

        # Calculate expected output paths
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
        midi_path = os.path.join(output_dir, f"{base_name}.midi")

        # Save current directory
        original_dir = os.getcwd()

        try:
            # Change to the output directory
            os.chdir(output_dir)

            # Run lilypond with just the filename (not the full path)
            result = run(
                ["lilypond", os.path.basename(self.__lilypond_filename)],
                capture_output=True,
            )

            return result, pdf_path, midi_path
        finally:
            # Always restore the original working directory
            os.chdir(original_dir)
