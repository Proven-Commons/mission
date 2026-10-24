/-
  Axiom check for the headline theorems. Building this file prints the
  axioms each proof depends on. The expected output is only the three
  standard Lean axioms: `propext`, `Classical.choice`, `Quot.sound`,
  or a subset of them. Any other name here breaks the verified bar.
-/

import TarPilot.Archive

#print axioms TarPilot.gate_sound
#print axioms TarPilot.cleanComponents_sound
#print axioms TarPilot.extractAll_safe
#print axioms TarPilot.extractArchive_safe
