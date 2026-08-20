# Narrative security boundary

The E6 narrative layer is offline and provider-free. It accepts structured
reports only, rejects unbounded output, preserves source references, and does
not transmit research or user notes. The disabled optional LLM renderer makes
no external call.

Any future model-backed renderer must receive an explicit threat-model review
for prompt injection in filings/notes, secret handling, data exfiltration,
output provenance, and historical outcome separation before implementation.
