% Configuration for chord extensions
\layout {
  \context {
    \ChordNames
    % Override how chord extensions are displayed
    \override ChordName.chord-name-exceptions = #'(
      (13 . ((9 . #f) (11 . #f)))  % Don't show 9th or 11th in 13th chords
    )
    % Set the chord name format to be more explicit
    \override ChordName.chord-name-separator = " "
  }
} 