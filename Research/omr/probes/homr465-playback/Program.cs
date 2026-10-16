using System.Reflection;
using System.Text.Json;
using SynthesiaClone;

return Probe.Run(args);

internal static class Probe
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static int Run(string[] arguments)
    {
        try
        {
            if (arguments.Length != 2)
                throw new ArgumentException("Expected manifest and exclusive output directory.");
            using JsonDocument manifest = JsonDocument.Parse(File.ReadAllText(arguments[0]));
            string destination = Path.GetFullPath(arguments[1]);
            if (Directory.Exists(destination))
                throw new IOException("Probe output already exists: " + destination);
            Directory.CreateDirectory(destination);
            string bridge = manifest.RootElement.GetProperty("bridge").GetString()!;
            string python = manifest.RootElement.GetProperty("python").GetString()!;
            List<object> results = [];
            foreach (JsonElement row in manifest.RootElement.GetProperty("inputs").EnumerateArray())
                results.Add(CheckInput(row, bridge, python, destination));
            File.WriteAllText(Path.Combine(destination, "results.json"), JsonSerializer.Serialize(results, JsonOptions));
            Console.WriteLine($"Bridge/C# MIDI/playback inputs passed: {results.Count}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static object CheckInput(JsonElement row, string bridge, string python, string destination)
    {
        string id = row.GetProperty("id").GetString()!;
        string input = row.GetProperty("input").GetString()!;
        OmrResult expected = row.GetProperty("expected").Deserialize<OmrResult>()
            ?? throw new InvalidDataException("Missing expected result.");
        OmrResult actual = OmrPipeline.Run(input, OmrEngine.MusicXml, bridge, python, TimeSpan.FromSeconds(60));
        AssertBridge(expected, actual, id);
        File.WriteAllText(Path.Combine(destination, id + ".json"), JsonSerializer.Serialize(actual, JsonOptions));
        string midi = Path.Combine(destination, id + ".mid");
        InvokeCache("WriteMidiForTesting", midi, actual);
        List<Note> notes = (List<Note>)InvokeCache("ReadMidiForTesting", midi)!;
        var expectedNotes = actual.Notes.OrderBy(n => n.MidiPitch).ThenBy(n => n.StartSeconds).ThenBy(n => n.DurationSeconds).ToArray();
        var restored = notes.OrderBy(n => n.MidiPitch).ThenBy(n => n.StartTime).ThenBy(n => n.Duration).ToArray();
        Require(restored.Length == expectedNotes.Length, id + ": MIDI count changed");
        double tolerance = 60 / actual.TempoChanges.Min(t => t.Bpm) / 480 + expectedNotes.Max(n => n.StartSeconds + n.DurationSeconds) * 1e-6;
        double maxStart = 0, maxDuration = 0;
        for (int index = 0; index < restored.Length; index++)
        {
            Require(restored[index].MidiPitch == expectedNotes[index].MidiPitch, id + ": MIDI pitch changed");
            maxStart = Math.Max(maxStart, Math.Abs(restored[index].StartTime - expectedNotes[index].StartSeconds));
            maxDuration = Math.Max(maxDuration, Math.Abs(restored[index].Duration - expectedNotes[index].DurationSeconds));
        }
        Require(maxStart <= tolerance && maxDuration <= tolerance, id + ": MIDI error exceeds tick quantization bound");
        object playback = AssertPlayback(notes, id);
        return new { id, notes = notes.Count, bridgeMatchesResearch = true, maxStartErrorSeconds = maxStart,
            maxDurationErrorSeconds = maxDuration, quantizationBoundSeconds = tolerance, playback };
    }

    private static void AssertBridge(OmrResult expected, OmrResult actual, string id)
    {
        Require(actual.SchemaVersion == 2 && actual.Engine == OmrEngine.MusicXml && actual.EngineRevision == "direct-xml", id + ": schema/revision mismatch");
        Require(actual.Notes.Count == expected.Notes.Count, id + ": Bridge count changed");
        Require(JsonSerializer.Serialize(actual.TempoChanges) == JsonSerializer.Serialize(expected.TempoChanges), id + ": tempo changed");
        for (int index = 0; index < actual.Notes.Count; index++)
        {
            MusicNote a = actual.Notes[index], e = expected.Notes[index];
            Require(a.MidiPitch == e.MidiPitch && a.Pitch == e.Pitch && a.PartIndex == e.PartIndex &&
                a.StaffIndex == e.StaffIndex && a.VoiceIdentifier == e.VoiceIdentifier, id + ": Bridge identity changed");
            Require(Math.Abs(a.StartBeat - e.StartBeat) < 1e-9 && Math.Abs(a.DurationBeats - e.DurationBeats) < 1e-9 &&
                Math.Abs(a.StartSeconds - e.StartSeconds) < 1e-9 && Math.Abs(a.DurationSeconds - e.DurationSeconds) < 1e-9, id + ": Bridge timing changed");
        }
    }

    private static object AssertPlayback(List<Note> notes, string id)
    {
        double now = 0;
        PlaybackSession session = new(notes);
        Require(session.AudioOffsetSeconds == 0.055, "Calibrated default changed");
        CaptureMidi output = new();
        PlaybackClock clock = new(() => now);
        PlaybackController controller = new(session, output, clock);
        double[] boundaries = notes.SelectMany(n => new[] { n.StartTime, n.EndTime }).Append(0).Distinct().Order().ToArray();
        double[] positions = boundaries.Zip(boundaries.Skip(1), (a, b) => (a + b) / 2).Prepend(0).Append(session.TotalDuration + 1).ToArray();
        foreach (double position in positions)
        {
            now = position;
            controller.Update();
            double horizon = position + 0.055;
            HashSet<int> expectedAudio = position >= session.TotalDuration ? [] : notes.Where(n => n.StartTime <= horizon && n.EndTime > horizon).Select(n => n.MidiPitch).ToHashSet();
            Require(output.Active.SetEquals(expectedAudio), id + ": controller audio activity differs");
            for (int key = 0; key < 88; key++)
                Require(controller.IsKeyActive(key) == notes.Any(n => n.TargetKeyIndex == key && n.StartTime <= position && n.EndTime > position), id + ": controller visual activity differs");
        }
        Require(controller.IsCompleted && output.Active.Count == 0, id + ": controller did not finish/silence");
        return new { samplePositions = positions.Length, audioOffsetSeconds = session.AudioOffsetSeconds,
            noteOnCalls = output.OnCalls, noteOffCalls = output.OffCalls, completed = true, physicalAudioTested = false };
    }

    private static object? InvokeCache(string name, params object[] values)
    {
        MethodInfo method = typeof(SongCache).GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(typeof(SongCache).FullName, name);
        return method.Invoke(null, values);
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }
}

internal sealed class CaptureMidi : IMidiOutput
{
    public HashSet<int> Active { get; } = [];
    public int OnCalls { get; private set; }
    public int OffCalls { get; private set; }
    public void NoteOn(int midiPitch, int velocity) { Active.Add(midiPitch); OnCalls++; }
    public void NoteOff(int midiPitch) { Active.Remove(midiPitch); OffCalls++; }
    public void AllNotesOff() => Active.Clear();
}
