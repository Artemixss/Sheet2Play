using System.ComponentModel;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Color = Raylib_cs.Color;

namespace SynthesiaClone;

/// <summary>
/// A song's performance as <c>Bridge/song_model.py</c> derives it from the song's MusicXML
/// (schema 3). Positions are quarter notes: a note or mark sits <c>offset</c> beats after the
/// start of its measure, and playback walks <see cref="PlayOrder"/>, advancing by each measure's
/// <see cref="SongMeasure.LengthBeats"/>.
/// </summary>
/// <remarks>
/// Read strictly, like the bridge's schema 2 JSON: an unknown field is an error, because a
/// field this reader ignores would be a feature the app silently fails to play.
/// <see cref="Features"/> is the one open-ended part; it holds counts for diagnostics only.
/// </remarks>
public sealed record SongPerformance(
    int SchemaVersion,
    string Kind,
    IReadOnlyList<SongSource> Sources,
    bool TimingCorrection,
    IReadOnlyList<SongPart> Parts,
    IReadOnlyList<SongPage> Pages,
    IReadOnlyList<SongMeasure> Measures,
    IReadOnlyList<int> PlayOrder,
    IReadOnlyList<SongNote> Notes,
    IReadOnlyList<SongPedal> Pedals,
    IReadOnlyList<SongDynamic> Dynamics,
    IReadOnlyList<SongWedge> Wedges,
    IReadOnlyList<SongTempo> Tempos,
    JsonElement Features,
    IReadOnlyList<string> Warnings)
{
    public const int CurrentSchemaVersion = 3;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
    };

    /// <summary>Parses and checks a performance document; throws <see cref="InvalidDataException"/>.</summary>
    public static SongPerformance Parse(string json)
    {
        SongPerformance performance;
        try
        {
            performance = JsonSerializer.Deserialize<SongPerformance>(json, JsonOptions)
                ?? throw new InvalidDataException("The performance document is empty.");
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException($"The performance document is invalid: {exception.Message}", exception);
        }
        performance.Validate();
        return performance;
    }

    private void Validate()
    {
        if (SchemaVersion != CurrentSchemaVersion)
        {
            throw new InvalidDataException($"Performance schema {SchemaVersion}; expected {CurrentSchemaVersion}.");
        }
        if (Kind is not ("omr-pages" or "musicxml"))
        {
            throw new InvalidDataException($"Unknown performance kind '{Kind}'.");
        }
        if (Measures is null || Measures.Count == 0 || PlayOrder is null || Notes is null || Pedals is null ||
            Dynamics is null || Wedges is null || Tempos is null || Sources is null || Parts is null ||
            Pages is null || Warnings is null)
        {
            throw new InvalidDataException("The performance document is missing a section.");
        }
        for (int index = 0; index < Measures.Count; index++)
        {
            SongMeasure measure = Measures[index] ?? throw new InvalidDataException($"Measure {index} is null.");
            if (measure.Index != index || !double.IsFinite(measure.StartBeat) || !double.IsFinite(measure.LengthBeats))
            {
                throw new InvalidDataException($"Measure {index} has an invalid index or position.");
            }
        }
        foreach (int index in PlayOrder)
        {
            CheckMeasure(index, "The play order");
        }
        foreach (SongNote note in Notes)
        {
            if (note is null || note.Midi is < 0 or > 127 || !double.IsFinite(note.Offset) ||
                !double.IsFinite(note.Duration) || note.Duration < 0 || (!note.Grace && note.Duration <= 0))
            {
                throw new InvalidDataException("A note has an invalid pitch, offset or duration.");
            }
            CheckMeasure(note.Measure, "A note");
        }
        foreach (SongPedal pedal in Pedals)
        {
            CheckMark(pedal?.Measure, pedal?.Offset, "A pedal");
        }
        foreach (SongDynamic dynamic in Dynamics)
        {
            CheckMark(dynamic?.Measure, dynamic?.Offset, "A dynamic");
        }
        foreach (SongTempo tempo in Tempos)
        {
            CheckMark(tempo?.Measure, tempo?.Offset, "A tempo mark");
            if (tempo!.QuarterBpm is double bpm && (!double.IsFinite(bpm) || bpm <= 0))
            {
                throw new InvalidDataException($"A tempo mark has an invalid BPM {bpm}.");
            }
        }
        foreach (SongWedge wedge in Wedges)
        {
            CheckMark(wedge?.StartMeasure, wedge?.StartOffset, "A hairpin");
            CheckMark(wedge!.EndMeasure, wedge.EndOffset, "A hairpin");
        }
    }

    private void CheckMeasure(int index, string what)
    {
        if (index < 0 || index >= Measures.Count)
        {
            throw new InvalidDataException($"{what} refers to measure {index}, outside the score.");
        }
    }

    private void CheckMark(int? measure, double? offset, string what)
    {
        if (measure is null || offset is null || !double.IsFinite(offset.Value))
        {
            throw new InvalidDataException($"{what} has no valid position.");
        }
        CheckMeasure(measure.Value, what);
    }
}

public sealed record SongSource(string Name, string Sha256);

public sealed record SongPart(int Index, int Staves, string Name);

public sealed record SongPage(
    int Index,
    string Name,
    int FirstMeasure,
    int Measures,
    double StartBeat,
    double DecodedBeats,
    double AdvanceBeats,
    string Timing);

public sealed record SongMeasure(
    int Index,
    int Page,
    string Number,
    double StartBeat,
    double LengthBeats,
    double BarBeats,
    IReadOnlyList<int>? TimeSignature,
    bool Pickup,
    bool RepeatStart,
    int RepeatEnd,
    IReadOnlyList<int>? Ending,
    bool EndingStop,
    IReadOnlyDictionary<string, JsonElement>? Jumps);

public sealed record SongNote(
    string Pitch,
    int Midi,
    int Measure,
    double Offset,
    double Duration,
    int Part,
    int Staff,
    string Voice,
    bool Grace,
    bool GraceSlash,
    bool Tied,
    IReadOnlyList<string> Articulations,
    IReadOnlyList<string> Slurs);

public sealed record SongPedal(
    int Measure,
    double Offset,
    int Part,
    int Staff,
    string? Type,
    string Source,
    string? SoundValue = null);

public sealed record SongDynamic(int Measure, double Offset, int Part, int Staff, string? Mark, double? SoundDynamics);

public sealed record SongWedge(
    string Kind,
    int Part,
    int Staff,
    int StartMeasure,
    double StartOffset,
    int EndMeasure,
    double EndOffset);

public sealed record SongTempo(
    int Measure,
    double Offset,
    int Part,
    int Staff,
    string? BeatUnit,
    int Dots,
    double? PerMinute,
    double? QuarterBpm,
    string Source);

/// <summary>How a performance becomes the notes the player plays.</summary>
/// <param name="ExpandRepeats">Walk the play order; otherwise every measure once, in order.</param>
/// <param name="IncludeGraceNotes">Grace notes need a playing rule before they sound; until then they are left out, as the bridge leaves them out.</param>
/// <param name="DefaultTempoBpm">The tempo until the score's first mark, in quarter notes per minute.</param>
public sealed record SongTimelineOptions(
    bool ExpandRepeats = true,
    bool IncludeGraceNotes = false,
    double DefaultTempoBpm = 120);

/// <summary>Turns a <see cref="SongPerformance"/> into timed notes.</summary>
public static class SongTimeline
{
    private const int DefaultVelocity = 80;

    /// <summary>Measure indices in the order they play.</summary>
    public static IReadOnlyList<int> Order(SongPerformance performance, SongTimelineOptions options) =>
        options.ExpandRepeats ? performance.PlayOrder : Enumerable.Range(0, performance.Measures.Count).ToArray();

    public static List<Note> BuildNotes(SongPerformance performance, SongTimelineOptions? options = null)
    {
        options ??= new SongTimelineOptions();
        IReadOnlyList<int> order = Order(performance, options);
        Dictionary<int, List<SongNote>> notesByMeasure = performance.Notes
            .Where(note => options.IncludeGraceNotes || !note.Grace)
            .GroupBy(static note => note.Measure)
            .ToDictionary(static group => group.Key, static group => group.ToList());
        double[] starts = MeasureStarts(performance, order);
        TempoMap tempo = BuildTempoMap(performance, order, starts, options.DefaultTempoBpm);

        List<Note> notes = [];
        for (int occurrence = 0; occurrence < order.Count; occurrence++)
        {
            if (!notesByMeasure.TryGetValue(order[occurrence], out List<SongNote>? measureNotes))
            {
                continue;
            }
            foreach (SongNote note in measureNotes)
            {
                int keyIndex = note.Midi - 21;
                if (keyIndex is < 0 or >= 88)
                {
                    continue;
                }
                double startBeat = starts[occurrence] + note.Offset;
                double startSeconds = tempo.SecondsAt(startBeat);
                double endSeconds = tempo.SecondsAt(startBeat + note.Duration);
                Color color = keyIndex >= 39 ? Color.SkyBlue : Color.Lime;
                notes.Add(new Note(keyIndex, startSeconds, Math.Max(0, endSeconds - startSeconds), DefaultVelocity, color));
            }
        }
        notes.Sort(static (left, right) =>
        {
            int startComparison = left.StartTime.CompareTo(right.StartTime);
            return startComparison != 0 ? startComparison : left.TargetKeyIndex.CompareTo(right.TargetKeyIndex);
        });
        return notes;
    }

    /// <summary>The beat at which each entry of <paramref name="order"/> starts.</summary>
    /// <remarks>
    /// The first measure keeps its own start, and each later one starts where the one before it
    /// ends. Read in order this reproduces the measure starts exactly, so a song without repeats
    /// plays where the bridge placed it.
    /// </remarks>
    public static double[] MeasureStarts(SongPerformance performance, IReadOnlyList<int> order)
    {
        double[] starts = new double[order.Count];
        double position = performance.Measures[0].StartBeat;
        for (int occurrence = 0; occurrence < order.Count; occurrence++)
        {
            starts[occurrence] = position;
            position += performance.Measures[order[occurrence]].LengthBeats;
        }
        return starts;
    }

    private static TempoMap BuildTempoMap(SongPerformance performance, IReadOnlyList<int> order, double[] starts,
        double defaultBpm)
    {
        // A mark sounds every time its measure plays; the tempo then holds until the next mark,
        // including back across a repeat, as it does in a score played through.
        Dictionary<int, List<SongTempo>> marksByMeasure = performance.Tempos
            .Where(static tempo => tempo.QuarterBpm is not null)
            .GroupBy(static tempo => tempo.Measure)
            .ToDictionary(static group => group.Key, static group => group.ToList());
        SortedDictionary<double, double> byBeat = [];
        for (int occurrence = 0; occurrence < order.Count; occurrence++)
        {
            if (marksByMeasure.TryGetValue(order[occurrence], out List<SongTempo>? marks))
            {
                foreach (SongTempo mark in marks)
                {
                    byBeat[Math.Max(0, starts[occurrence] + mark.Offset)] = mark.QuarterBpm!.Value;
                }
            }
        }
        if (!byBeat.ContainsKey(0))
        {
            byBeat[0] = defaultBpm;
        }
        return new TempoMap(byBeat);
    }

    private sealed class TempoMap
    {
        private readonly double[] beats;
        private readonly double[] bpms;
        private readonly double[] seconds;

        public TempoMap(SortedDictionary<double, double> byBeat)
        {
            List<(double Beat, double Bpm)> changes = [];
            foreach ((double beat, double bpm) in byBeat)
            {
                if (changes.Count == 0 || Math.Abs(changes[^1].Bpm - bpm) > 1e-9)
                {
                    changes.Add((beat, bpm));
                }
            }
            beats = changes.Select(static change => change.Beat).ToArray();
            bpms = changes.Select(static change => change.Bpm).ToArray();
            seconds = new double[changes.Count];
            for (int index = 1; index < changes.Count; index++)
            {
                seconds[index] = seconds[index - 1] + (beats[index] - beats[index - 1]) * 60.0 / bpms[index - 1];
            }
        }

        public double SecondsAt(double beat)
        {
            int index = Array.BinarySearch(beats, beat);
            if (index < 0)
            {
                index = Math.Max(0, ~index - 1);
            }
            return seconds[index] + (beat - beats[index]) * 60.0 / bpms[index];
        }
    }
}

/// <summary>Identity and running of <c>song_model.py</c>, the interpreter beside the bridge.</summary>
public static class SongInterpreter
{
    private static readonly TimeSpan DefaultTimeout = TimeSpan.FromMinutes(10);

    /// <summary>
    /// The interpretation key <c>song_model.interpretation_key</c> computes: the schema, the
    /// interpreter's SHA-256 and, when the timing fix is on, the fix's. A performance is valid
    /// only under the key it was written for.
    /// </summary>
    public static string InterpretationKey(string bridgeDirectory, bool timingCorrection)
    {
        string interpreter = FileSha256(Path.Combine(bridgeDirectory, OmrPipeline.SongModelScriptName),
            "song interpreter");
        string timing = timingCorrection
            ? FileSha256(Path.Combine(bridgeDirectory, OmrPipeline.TimingCorrectionScriptName), "timing correction")
            : "off";
        string text = $"schema={SongPerformance.CurrentSchemaVersion}\nsong_model={interpreter}\ntiming_correction={timing}\n";
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    }

    private static string FileSha256(string path, string description)
    {
        if (!File.Exists(path))
        {
            throw new OmrPipelineException($"The {description} ({Path.GetFileName(path)}) is missing from the Bridge folder.",
                errorCode: "RUNTIME_MISSING", stage: "runtime_start");
        }
        return Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));
    }

    /// <summary>Interprets stored MusicXML into <paramref name="outputDirectory"/>. No OMR runs.</summary>
    /// <param name="sources">HOMR's pages in order, or the one imported score.</param>
    public static void Run(string bridgeDirectory, OmrEngine engine, IReadOnlyList<string> sources, bool imported,
        bool timingCorrection, string outputDirectory, CancellationToken cancellationToken = default)
    {
        string script = Path.Combine(bridgeDirectory, OmrPipeline.SongModelScriptName);
        if (!File.Exists(script))
        {
            throw new OmrPipelineException("The song interpreter is missing from the Bridge folder.",
                errorCode: "RUNTIME_MISSING", stage: "runtime_start");
        }
        string python = OmrPipeline.ResolveEnginePythonExecutable(Path.Combine(bridgeDirectory, "bridge.py"), engine);
        if (!File.Exists(python))
        {
            throw new OmrPipelineException($"The {OmrPipeline.GetEngineName(engine)} Python runtime was not found at " +
                $"'{python}'. {OmrPipeline.GetRuntimeSetupInstruction(engine)}", errorCode: "RUNTIME_MISSING",
                stage: "runtime_start");
        }
        ProcessStartInfo startInfo = new()
        {
            FileName = python,
            WorkingDirectory = bridgeDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add(script);
        startInfo.ArgumentList.Add("--output");
        startInfo.ArgumentList.Add(outputDirectory);
        if (timingCorrection && !imported)
        {
            startInfo.ArgumentList.Add("--timing-correction");
        }
        if (imported)
        {
            startInfo.ArgumentList.Add("--score");
        }
        foreach (string source in sources)
        {
            startInfo.ArgumentList.Add(source);
        }
        startInfo.Environment["PYTHONUNBUFFERED"] = "1";

        using Process process = new() { StartInfo = startInfo };
        try
        {
            process.Start();
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            throw new OmrPipelineException($"Could not start the song interpreter: {exception.Message}", exception,
                errorCode: "RUNTIME_MISSING", stage: "runtime_start");
        }
        Task<string> output = process.StandardOutput.ReadToEndAsync(CancellationToken.None);
        Task<string> errors = process.StandardError.ReadToEndAsync(CancellationToken.None);
        using CancellationTokenSource timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(DefaultTimeout);
        try
        {
            process.WaitForExitAsync(timeout.Token).GetAwaiter().GetResult();
        }
        catch (OperationCanceledException)
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch (Exception exception) when (exception is InvalidOperationException or Win32Exception)
            {
            }
            cancellationToken.ThrowIfCancellationRequested();
            throw new TimeoutException($"The song interpreter exceeded {DefaultTimeout}.");
        }
        Task.WaitAll(output, errors);
        if (process.ExitCode != 0)
        {
            string detail = errors.Result.Trim();
            throw new OmrPipelineException(
                $"The song interpreter failed with exit code {process.ExitCode}: " +
                (detail.Length > 2_000 ? detail[^2_000..] : detail),
                errorCode: "NORMALIZATION_FAILED", stage: "interpretation", exitCode: process.ExitCode,
                standardError: errors.Result);
        }
    }
}
