# Required decoration gate

POD inclusion requires product-level evidence of printed or engraved text or an
image. Plain products, uncertain classifications, undecorated shapes, embroidery
alone, printing blanks and printing equipment are excluded from POD reports.
Generic custom/design/gift terms, category names, seller profiles and URLs cannot
supply the required evidence. Printing or engraving on packaging does not count.

This gate reads listing titles and descriptions; it does not inspect pixels.
Missing or ambiguous evidence is excluded conservatively. It is an inclusion
policy, not proof of how a manufacturer fulfills orders. False exclusions remain
possible when only the product photo shows the decoration.

The gate also applies when old cached POD fields are loaded. Unknown/maybe is no
longer included by `pod_allowed`. Existing retail-brand exclusions still apply.
Raw scan records remain available; non-POD inclusion can still be explicitly
requested for all-product reports. This does not label them POD.

Validation: classifier tests cover direct decoration, seller/category leakage,
packaging, blanks, embroidery and cached labels. Parser, offline scan, scoring
and report tests cover propagation to downstream outputs.
