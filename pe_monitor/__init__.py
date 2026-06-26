"""PE-multiples monitoring agent.

Reads the diversified-financials forward-P/E dashboard API, flags meaningful
disconnects between each name's current multiple and (1) its own historic PE
average and (2) the average of relative-value pair trades, then emails a
digestible HTML summary (with charts) via the Brevo transactional API.
"""

__version__ = "1.0.0"
