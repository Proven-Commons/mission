import Resp

/-! Axiom check. Each main theorem should depend only on the standard Lean
axioms `propext`, `Classical.choice`, and `Quot.sound`, or a subset. -/

#print axioms Resp.decode_encode
#print axioms Resp.decode_sound
#print axioms Resp.parseValue_encode
#print axioms Resp.parseValue_sound
#print axioms Resp.encode_injective
#print axioms Resp.decode_suffix
#print axioms Resp.parseNat_encNat
#print axioms Resp.encNat_of_parseNat
#print axioms Resp.Store.get_set_self
#print axioms Resp.Store.get_set_other
#print axioms Resp.Store.get_del_self
#print axioms Resp.Store.get_del_other
#print axioms Resp.Store.keys_set_nodup
#print axioms Resp.get_after_set
#print axioms Resp.get_after_set_other
#print axioms Resp.get_after_del
#print axioms Resp.parseRequest_encodeRequest
#print axioms Resp.serve_encodeAll
#print axioms Resp.wire_set_get
#print axioms Resp.wire_del_get
