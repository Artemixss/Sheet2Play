using System.ComponentModel;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

/// <summary>One mark as <c>tempo_marks.py</c> read it: where it is printed and what OCR saw.</summary>
/// <param name="PageMeasure">The measure the mark sits over, counted from the top of its page.</param>
/// <param name="Bpm">The number after "=", or null for a tempo word on its own ("Andante").</param>
/// <param name="Unit">The beat unit's name ("quarter", "dotted_quarter", ...), as the reader classified the glyph.</param>
/// <param name="Suggestion">A tempo word found in the text, offered as a hint only: words fix no BPM.</param>
public sealed record DetectedMark(int Page, int System, int? PageMeasure, double? Bpm, string? Unit, string Text,
    string? Words, string? Suggestion)
{
    /// <summary>What IGNORE remembers the mark by, the same for every conversion of the PDF.</summary>
    [JsonIgnore]
    public string Key => FormattableString.Invariant($"{Page}:{PageMeasure}:{Bpm}:{Unit}:{Text}");
}

public sealed record DetectedPage(int Systems, int Measures);

/// <summary>What <c>tempo_marks.py</c> wrote for one PDF.</summary>
public sealed record DetectedTempos(int SchemaVersion, string ReaderSha256, string SourceSha256,
    IReadOnlyList<DetectedPage> Pages, IReadOnlyList<DetectedMark> Marks);

/// <summary>A printed mark placed in a song's measures, as the TEMPO panel lists it.</summary>
/// <param name="Measure">The song measure, or null when the conversion's pages do not match the PDF's.</param>
/// <param name="Tempo">The tempo, or null for a word on its own or a beat unit the panel has no symbol for.</param>
public sealed record PrintedMark(DetectedMark Source, int? Measure, TempoMark? Tempo)
{
    public bool Usable => Measure is not null && Tempo is not null;

    /// <summary>
    /// The words printed with the mark ("Calmando"), or for a word on its own, that word. OCR reads
    /// the note glyph itself as "J" or "√", which is not a word, so text with fewer than two letters
    /// is left out.
    /// </summary>
    public string? Words => (Source.Bpm is null ? Source.Suggestion : Source.Words) is string words &&
        words.Count(char.IsLetter) >= 2
            ? words
            : null;
}

public sealed class TempoDetectionException(string message, Exception? inner = null) : Exception(message, inner);

/// <summary>
/// Reading the tempo marks printed in a song's PDF (Phase 3 of the per-song tempo plan). The bridge's
/// <c>tempo_marks.py</c> reads them; the result is kept per source PDF in <c>songs/tempo-marks</c>,
/// valid only for the reader that wrote it, and the TEMPO panel offers each mark with USE and IGNORE.
/// Nothing here changes what a song plays until the user takes a mark into its tempo map.
/// </summary>
public static class TempoDetection
{
    public const string ScriptName = "tempo_marks.py";
    public const int SchemaVersion = 1;
    private const string ProgressPrefix = "SHEET2PLAY_TEMPO_PROGRESS:";
    private static readonly TimeSpan Timeout = TimeSpan.FromMinutes(20);

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    public static string StorePath(string applicationDirectory, string sourceSha256) =>
        Path.Combine(applicationDirectory, "songs", "tempo-marks", sourceSha256 + ".json");

    /// <summary>The SHA-256 of the bridge's reader; a stored result from any other is out of date.</summary>
    public static string? ReaderSha256(string bridgeDirectory)
    {
        string script = Path.Combine(bridgeDirectory, ScriptName);
        try
        {
            return File.Exists(script) ? Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(script))) : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[TEMPO] Could not hash {script}: {exception.Message}");
            return null;
        }
    }

    /// <summary>The stored marks for a PDF, or null when there are none for this reader and file.</summary>
    public static DetectedTempos? Load(string applicationDirectory, string sourceSha256, string? readerSha256)
    {
        string path = StorePath(applicationDirectory, sourceSha256);
        if (readerSha256 is null || !File.Exists(path))
        {
            return null;
        }
        try
        {
            DetectedTempos? detected = JsonSerializer.Deserialize<DetectedTempos>(File.ReadAllText(path), JsonOptions);
            return detected is { SchemaVersion: SchemaVersion, Pages: not null, Marks: not null } &&
                detected.ReaderSha256 == readerSha256 &&
                string.Equals(detected.SourceSha256, sourceSha256, StringComparison.OrdinalIgnoreCase)
                    ? detected
                    : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"[TEMPO] Could not read the printed marks in {path}: {exception.Message}");
            return null;
        }
    }

    /// <summary>
    /// The marks in the song's measures. A PDF conversion has one HOMR page per PDF page, so a mark's
    /// measure is its page's first measure plus its place on the page. HOMR may read a page with fewer
    /// bars than the reader counted, so the place is held within the page.
    /// </summary>
    public static IReadOnlyList<PrintedMark> Place(DetectedTempos detected, SongPerformance performance)
    {
        ArgumentNullException.ThrowIfNull(detected);
        ArgumentNullException.ThrowIfNull(performance);
        bool pagesMatch = performance.Kind == "omr-pages" && performance.Pages.Count == detected.Pages.Count;
        List<PrintedMark> placed = [];
        foreach (DetectedMark mark in detected.Marks.OrderBy(static mark => mark.Page)
                     .ThenBy(static mark => mark.PageMeasure ?? 0).ThenBy(static mark => mark.System))
        {
            if (mark.Bpm is null && mark.Suggestion is null)
            {
                continue;
            }
            int? measure = null;
            if (pagesMatch && mark.PageMeasure is int onPage && mark.Page >= 0 && mark.Page < performance.Pages.Count &&
                performance.Pages[mark.Page].Measures > 0)
            {
                SongPage page = performance.Pages[mark.Page];
                measure = page.FirstMeasure + Math.Clamp(onPage, 0, page.Measures - 1);
            }
            TempoMark? tempo = mark.Bpm is double bpm && TempoRules.IsInRange(bpm) && UnitFrom(mark.Unit) is BeatUnit unit
                ? new TempoMark(bpm, unit)
                : null;
            // OCR can read one mark twice in overlapping strips; one row is enough.
            if (tempo is not null && placed.Any(other => other.Measure == measure && other.Tempo == tempo))
            {
                continue;
            }
            placed.Add(new PrintedMark(mark, measure, tempo));
        }
        return placed;
    }

    public static BeatUnit? UnitFrom(string? unit) => unit switch
    {
        "quarter" => BeatUnit.Quarter,
        "dotted_quarter" => BeatUnit.DottedQuarter,
        "half" => BeatUnit.Half,
        "dotted_half" => BeatUnit.DottedHalf,
        "eighth" => BeatUnit.Eighth,
        _ => null
    };

    /// <summary>Whether the map already plays the mark where it is printed.</summary>
    public static bool InUse(SongTempoMap map, PrintedMark mark) =>
        mark.Usable && (mark.Measure == 0
            ? map.Start == mark.Tempo
            : map.Changes.Any(change => change.Measure == mark.Measure && change.Tempo == mark.Tempo));

    /// <summary>
    /// The map with the mark taken in: at the first measure it is the start tempo, elsewhere a change
    /// at the start of its measure, replacing a change the map had there.
    /// </summary>
    public static SongTempoMap Use(SongTempoMap map, PrintedMark mark)
    {
        if (!mark.Usable)
        {
            return map;
        }
        int measure = mark.Measure!.Value;
        TempoMark tempo = mark.Tempo!;
        if (measure == 0)
        {
            return map with { Start = tempo };
        }
        BarTempo change = new(measure, 0, tempo);
        return map with
        {
            Changes = map.Changes.Where(existing => existing.Measure != measure).Append(change)
                .OrderBy(static existing => existing.Measure).ThenBy(static existing => existing.Offset).ToArray()
        };
    }

    /// <summary>
    /// What a PDF conversion plays when the user has set no tempo of their own: its printed marks,
    /// all but the ones the user ignored, each taken in as USE would. A song whose PDF prints a
    /// change but no starting tempo starts at 120. Null when no mark can be used.
    /// </summary>
    public static SongTempoMap? PrintedMap(IReadOnlyList<PrintedMark> marks, IReadOnlySet<string> ignored,
        SongPerformance performance, OmrEngine engine)
    {
        ArgumentNullException.ThrowIfNull(marks);
        ArgumentNullException.ThrowIfNull(ignored);
        ArgumentNullException.ThrowIfNull(performance);
        List<PrintedMark> usable = marks.Where(mark => mark.Usable && !ignored.Contains(mark.Source.Key)).ToList();
        return usable.Count == 0
            ? null
            : usable.Aggregate(new SongTempoMap(SongTempoMaps.Fallback, [], engine, performance.Measures.Count,
                DateTimeOffset.UnixEpoch), Use);
    }

    /// <summary>The printed map for a stored song, read from the store; null without usable marks.</summary>
    public static SongTempoMap? PrintedMap(string applicationDirectory, string? readerSha256, string sourceSha256,
        SongPerformance performance, OmrEngine engine, IReadOnlySet<string> ignored)
    {
        if (performance.Kind != "omr-pages" ||
            Load(applicationDirectory, sourceSha256, readerSha256) is not DetectedTempos detected)
        {
            return null;
        }
        return PrintedMap(Place(detected, performance), ignored, performance, engine);
    }

    /// <summary>
    /// Reads the PDF's marks into the store and returns them. Runs <c>tempo_marks.py</c> in the HOMR
    /// runtime; <paramref name="background"/> lowers its priority so playback keeps the CPU.
    /// </summary>
    public static DetectedTempos Detect(string applicationDirectory, string bridgeDirectory, string pdfPath,
        string sourceSha256, IProgress<(int Page, int Pages)>? progress, bool background,
        CancellationToken cancellationToken = default)
    {
        string script = Path.Combine(bridgeDirectory, ScriptName);
        if (!File.Exists(script))
        {
            throw new TempoDetectionException($"The tempo reader ({ScriptName}) is missing from the Bridge folder.");
        }
        string python = OmrPipeline.ResolveEnginePythonExecutable(Path.Combine(bridgeDirectory, "bridge.py"),
            OmrEngine.Homr480);
        if (!File.Exists(python))
        {
            throw new TempoDetectionException($"The HOMR Python runtime was not found at '{python}'.");
        }
        string output = StorePath(applicationDirectory, sourceSha256);
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        ProcessStartInfo startInfo = new()
        {
            FileName = python,
            WorkingDirectory = bridgeDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("-I");
        startInfo.ArgumentList.Add(script);
        startInfo.ArgumentList.Add("--output");
        startInfo.ArgumentList.Add(output);
        startInfo.ArgumentList.Add(pdfPath);
        startInfo.Environment["PYTHONUNBUFFERED"] = "1";

        using Process process = new() { StartInfo = startInfo };
        List<string> errors = [];
        process.ErrorDataReceived += (_, line) =>
        {
            if (line.Data is not string text)
            {
                return;
            }
            if (text.StartsWith(ProgressPrefix, StringComparison.Ordinal))
            {
                try
                {
                    using JsonDocument document = JsonDocument.Parse(text[ProgressPrefix.Length..]);
                    progress?.Report((document.RootElement.GetProperty("page").GetInt32(),
                        document.RootElement.GetProperty("pages").GetInt32()));
                }
                catch (Exception exception) when (exception is JsonException or KeyNotFoundException or InvalidOperationException)
                {
                }
                return;
            }
            lock (errors)
            {
                errors.Add(text);
            }
        };
        process.OutputDataReceived += static (_, _) => { };
        try
        {
            process.Start();
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            throw new TempoDetectionException($"Could not start the tempo reader: {exception.Message}", exception);
        }
        if (background)
        {
            try
            {
                process.PriorityClass = ProcessPriorityClass.BelowNormal;
            }
            catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
            {
            }
        }
        process.BeginErrorReadLine();
        process.BeginOutputReadLine();
        using CancellationTokenSource timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(Timeout);
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
            throw new TempoDetectionException($"The tempo reader took longer than {Timeout.TotalMinutes:0} minutes.");
        }
        process.WaitForExit();
        if (process.ExitCode != 0)
        {
            string detail;
            lock (errors)
            {
                detail = string.Join('\n', errors.TakeLast(6)).Trim();
            }
            throw new TempoDetectionException($"The tempo reader failed with exit code {process.ExitCode}: {detail}");
        }
        return Load(applicationDirectory, sourceSha256, ReaderSha256(bridgeDirectory))
            ?? throw new TempoDetectionException("The tempo reader wrote no readable result.");
    }
}
