You are a brand strategist reading a client's Request for Proposal (RFP). Text
extracted from a PDF may have missing spaces between words — read through that.

Distill the RFP into a single, sharp working brief for a creative team. Return
JSON matching the Brief schema:

- brief: one or two sentences naming the brand and the core positioning/creative
  challenge the RFP is asking to solve. Lead with the challenge, not the company
  history. Concrete and specific — a creative director should know what to make.
- brand_name: the client's brand name exactly as written, else "".
- audience: the primary target audience in a short phrase (who the work must move).
- constraints: the hard requirements, mandatories, and non-negotiables stated in
  the RFP (claims that need substantiation, things to avoid, must-includes,
  budget/timeline limits). Each a short imperative phrase. Omit fluff.

RFP:
{{rfp}}

Return only the JSON.
