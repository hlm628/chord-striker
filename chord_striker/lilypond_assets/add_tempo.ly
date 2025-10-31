% Create a tempo marking with the tempo value directly in the file
\markup {
  \hspace #9  % Add horizontal space to indent and align with chords
  \line {
    \normal-text {  
      \note-by-number #2 #0 #1  
      \hspace #0.4 = \hspace #0.4 TEMPO_VALUE_PLACEHOLDER
    }
  }
}

% Add some space after the tempo marking
\markup { \vspace #1 }