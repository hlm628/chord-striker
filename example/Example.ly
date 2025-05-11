\version "2.22.1"

\include "../lilypond_assets/slash_symbol.ly"

\include "../lilypond_assets/chord_extensions.ly"

\header {
  title = "Example"
  tagline = ""
}

\paper {
  oddFooterMarkup = \markup { \small \fill-line { \null \right-align { "Example.pdf" } } }
  evenFooterMarkup = \markup { \small \fill-line { \null \right-align { "Example.pdf" } } }
}
tempo = 164

tempoBlock = {
  \tempo 4 = 164
  \override Score.MetronomeMark.padding = #-6
}

% Create a tempo marking with the tempo value directly in the file
\markup {
  \hspace #9  % Add horizontal space to indent and align with chords
  \line {
    \normal-text {  
      \note-by-number #2 #0 #1  
      \hspace #0.4 = \hspace #0.4 164
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
    piece = "Verse 1"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsB}
  }

  \header {
    piece = "Chorus 1"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBA}
  }

  \header {
    piece = "Postchorus 1"
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
    piece = "Postchorus 2"
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
    piece = "Postchorus 3"
  }

  \include "../lilypond_assets/chord_chart_bar_lines.ly"

}

\score {

  {
    \chords {\chordsBAAA}
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
  }

  \midi {
    \tempo 4 = 164

  \context {
      \Score
      midiChannelMapping = #'instrument
    }
  }
}