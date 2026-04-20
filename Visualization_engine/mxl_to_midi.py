import sys
from music21 import converter, bar, repeat

input_mxl = sys.argv[1]
output_mid = sys.argv[2]

# 1. Read the dirty Audiveris XML
parsed_score = converter.parse(input_mxl)

# 2. The Sanitizer: Strip out all broken repeat loops
for element in parsed_score.recurse():
    if isinstance(element, (bar.Repeat, repeat.RepeatExpression)):
        # Delete the broken element from its parent container
        element.activeSite.remove(element)

# 3. Export the clean MIDI
parsed_score.write('midi', fp=output_mid)