Created [the corrected review](endpoint-calibration-corrected-review.json) and the generated-only [PCM analysis script](analyze-endpoint-audio.py). The prior review remains unchanged.

The corrected evidence separates the base-only black samples at frames 199/200 from the later overlay samples: the overlay is visible at local 199 and black at 200. For generated audio, rendered frame 9198 correlates with bed source frame 198; rendered frame 9199 is silent while source frame 199 is nonzero. No other enabled generated audio extends past getter value 9199.

Fractional getter precision remains **untested**, not an API failure. The 50% source frame/time values remain recorded separately and unresolved. JSON validity and preservation of the prior review’s hash were verified.