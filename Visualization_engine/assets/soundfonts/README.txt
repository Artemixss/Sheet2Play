Soundfonts for the built-in synthesiser
=======================================

Drop a SoundFont2 (.sf2) file in this folder and the app will play through it.
The filename does not matter - the folder is globbed, newest file wins.

The app also looks in %LOCALAPPDATA%\Sheet2Play\soundfonts, and that location is
checked FIRST. Prefer it: this folder is inside dist\, which the release script
wipes and rebuilds on every publish.

To install the default piano:

    powershell -ExecutionPolicy Bypass -File scripts\install-soundfont.ps1

Only .sf2 is supported. MeltySynth, the synthesiser this app embeds, does not
read .sf3 (compressed) or .sfz (text-based sample maps). Converting an SFZ set
to SF2 with Polyphone works if you want to bring your own.

If no soundfont is found the app falls back to an external MIDI device such as
VirtualMIDISynth and says so on the landing page, rather than playing silently.
