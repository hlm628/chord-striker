slashSymbol = \markup {
    \translate #'(0 . -0.5)  % Adjust vertical position (y value)
    \fontsize #4 "/"  % Simple but effective slash character
}

chordSlash = \once \override ChordNames.ChordName.text = #slashSymbol