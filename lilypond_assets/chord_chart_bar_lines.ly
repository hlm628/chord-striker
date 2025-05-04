\layout {
  % Global layout settings
  indent = 0                  % No initial indent
  short-indent = 0            % No short indent
  ragged-right = ##t          % Allow flexible right margin
  
  % Chord name context
  \context {
    \ChordNames
    % Bar line settings (preserved from original)
    \override BarLine.bar-extent = #'(-1.1 . 2.8)
    \consists "Bar_engraver"
    
    % Alignment settings
    \override ChordName.font-size = #1
    \override ChordName.extra-spacing-width = #'(-2 . 2) % Extra space between notes
    \consists "Instrument_name_engraver"
    \override InstrumentName.stencil = ##f
    \override InstrumentName.width = #0
    
    % Control alignment at start of system
    \override ChordName.self-alignment-X = #LEFT
    \override ChordName.X-offset = #2    % Fixed indent for all sections
    
    % Alignment for line breaks within sections
    \override BreakAlignment.break-align-orders = 
      #(make-vector 3 '(left-edge instrument-name))
  }
  
  % Score context
  \context {
    \Score
    \remove "Bar_number_engraver"
  }
}