\score{
  {
    \new Staff \with {
    \remove "Staff_symbol_engraver"
    \remove "Clef_engraver" 
    \override TimeSignature.color = #white
    }

    \chords {\tempoBlock} 
  }
}