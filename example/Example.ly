\version "2.22.1"

\include "../lilypond_assets/slash_symbol.ly"

\header {
  title = "Example"
  tagline = ""
}

\paper {
  oddFooterMarkup = \markup { \small \fill-line { \null \right-align { "Example.pdf" } } }
  evenFooterMarkup = \markup { \small \fill-line { \null \right-align { "Example.pdf" } } }
}
tempo = 131

tempoBlock = {
  \tempo 4 = 131
  \override Score.MetronomeMark.padding = #-6
}

% Create a tempo marking with the tempo value directly in the file
\markup {
  \hspace #9  % Add horizontal space to indent and align with chords
  \line {
    \normal-text {  
      \note-by-number #2 #0 #1  
      \hspace #0.4 = \hspace #0.4 131
    }
  }
}

% Add some space after the tempo marking
\markup { \vspace #1 }

\include "Example_chords.ly"

\score {

  {
    \chords {\chordsA}
  }

  \header {
    piece = "Intro"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsB}
  }

  \header {
    piece = "Verse 1"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBA}
  }

  \header {
    piece = "Chorus 1"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBB}
  }

  \header {
    piece = "Verse 2"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBAA}
  }

  \header {
    piece = "Chorus 2"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBAB}
  }

  \header {
    piece = "Verse 3"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBBA}
  }

  \header {
    piece = "Chorus 3"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBBB}
  }

  \header {
    piece = "Verse 4"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBAAA}
  }

  \header {
    piece = "Chorus 4"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBAAB}
  }

  \header {
    piece = "Outro"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {
  {
    \chords {\chordsA}
    \chords {\chordsB}
    \chords {\chordsBA}
    \chords {\chordsBB}
    \chords {\chordsBAA}
    \chords {\chordsBAB}
    \chords {\chordsBBA}
    \chords {\chordsBBB}
    \chords {\chordsBAAA}
    \chords {\chordsBAAB}
  }

  \midi {
    \tempo 4 = 131

  \context {
      \Score
      midiChannelMapping = #'instrument
    }
  }
}