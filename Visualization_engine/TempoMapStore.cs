using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynthesiaClone;

/// <summary>The note a tempo counts. Stored as entered, so "♩. = 110" reads back as it was typed.</summary>
public enum BeatUnit
{
    Quarter,
    DottedQuarter,
    Half,
    DottedHalf,
    Eighth
}

public static class BeatUnits
{
    /// <summary>How many quarter notes one beat of <paramref name="unit"/> lasts.</summary>
    public static double Quarters(this BeatUnit unit) => unit switch
    {
        BeatUnit.Quarter => 1.0,
        BeatUnit.DottedQuarter => 1.5,
        BeatUnit.Half => 2.0,
        BeatUnit.DottedHalf => 3.0,
        BeatUnit.Eighth => 0.5,
        _ => throw new ArgumentOutOfRangeException(nameof(unit), unit, "Unknown beat unit.")
    };

    /// <summary>The unit after <paramref name="unit"/> in the TEMPO panel's cycle.</summary>
    public static BeatUnit Next(this BeatUnit unit) => unit == BeatUnit.Eighth ? BeatUnit.Quarter : unit + 1;

    /// <summary>
    /// A score mark's unit as <c>song_model.py</c> records it, or null for one the panel has no
    /// symbol for (a whole note, a sixteenth, or a bare <c>&lt;sound tempo&gt;</c>).
    /// </summary>
    public static BeatUnit? FromScore(string? beatUnit, int dots) => (beatUnit, dots) switch
    {
        ("quarter", 0) => BeatUnit.Quarter,
        ("quarter", 1) => BeatUnit.DottedQuarter,
        ("half", 0) => BeatUnit.Half,
        ("half", 1) => BeatUnit.DottedHalf,
        ("eighth", 0) => BeatUnit.Eighth,
        _ => null
    };
}

/// <summary>A tempo as the user enters it: <paramref name="Bpm"/> beats of <paramref name="Unit"/> per minute.</summary>
public sealed record TempoMark(double Bpm, BeatUnit Unit)
{
    [JsonIgnore]
    public double QuarterBpm => Bpm * Unit.Quarters();
}

/// <summary>A tempo that takes over where a measure starts, every time that measure plays.</summary>
/// <param name="Measure">
/// The measure's index in the performance, not its printed number: HOMR numbers measures per page,
/// so a PDF conversion has a "bar 3" on every page.
/// </param>
/// <param name="Offset">Beats into the measure. The panel adds changes at 0; a mark taken over from the score keeps its own.</param>
public sealed record BarTempo(int Measure, double Offset, TempoMark Tempo);

/// <summary>A song's tempo as the user set it in the TEMPO panel.</summary>
/// <param name="Engine">The conversion the bar changes were set on, named when another conversion of the same file differs.</param>
/// <param name="MeasureCount">
/// How many measures that conversion has. Another conversion of the same PDF can read a different
/// number of bars, and its bar 40 is then not this bar 40, so changes play only where the counts match.
/// </param>
public sealed record SongTempoMap(
    TempoMark Start,
    IReadOnlyList<BarTempo> Changes,
    OmrEngine Engine,
    int MeasureCount,
    DateTimeOffset UpdatedUtc);

/// <summary>
/// Per-song tempo maps, in <c>tempo-maps.json</c> beside the settings, keyed by the SHA-256 of the
/// song's source file so a map follows the song across engines, the timing fix and re-runs.
/// </summary>
/// <remarks>
/// The maps are typed in by the user, so a file that cannot be read is moved aside rather than
/// overwritten, and one bad entry is dropped without losing the others.
/// </remarks>
public static class TempoMapStore
{
    private const int FileVersion = 1;
    private static readonly object Gate = new();
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters =
        {
            new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase),
            new JsonStringEnumConverter<BeatUnit>(JsonNamingPolicy.SnakeCaseLower)
        }
    };

    private sealed record TempoMapFile(int Version, Dictionary<string, SongTempoMap> Songs);

    public static string DefaultPath => Path.Combine(
        Path.GetDirectoryName(AppSettingsStore.GetSettingsPath())!,
        "tempo-maps.json");

    public static SongTempoMap? Get(string sourceSha256, string? storePath = null)
    {
        lock (Gate)
        {
            return Read(storePath ?? DefaultPath).GetValueOrDefault(sourceSha256);
        }
    }

    /// <summary>Every stored map, for the library's durations.</summary>
    public static IReadOnlyDictionary<string, SongTempoMap> LoadAll(string? storePath = null)
    {
        lock (Gate)
        {
            return Read(storePath ?? DefaultPath);
        }
    }

    public static void Save(string sourceSha256, SongTempoMap map, string? storePath = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceSha256);
        ArgumentNullException.ThrowIfNull(map);
        if (!IsValid(map))
        {
            throw new ArgumentException("The tempo map has a tempo out of range or a negative measure.", nameof(map));
        }
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            Dictionary<string, SongTempoMap> songs = Read(path);
            songs[sourceSha256] = map;
            Write(path, songs);
        }
    }

    public static void Remove(string sourceSha256, string? storePath = null)
    {
        string path = storePath ?? DefaultPath;
        lock (Gate)
        {
            Dictionary<string, SongTempoMap> songs = Read(path);
            if (songs.Remove(sourceSha256))
            {
                Write(path, songs);
            }
        }
    }

    internal static bool IsValid(SongTempoMap map) =>
        map.Start is not null && TempoRules.IsInRange(map.Start.Bpm) && Enum.IsDefined(map.Start.Unit) &&
        map.MeasureCount > 0 && map.Changes is not null &&
        map.Changes.All(static change => change?.Tempo is not null && change.Measure >= 0 &&
            double.IsFinite(change.Offset) && change.Offset >= 0 &&
            TempoRules.IsInRange(change.Tempo.Bpm) && Enum.IsDefined(change.Tempo.Unit));

    private static Dictionary<string, SongTempoMap> Read(string path)
    {
        if (!File.Exists(path))
        {
            return [];
        }
        TempoMapFile? file;
        try
        {
            file = JsonSerializer.Deserialize<TempoMapFile>(File.ReadAllText(path), JsonOptions);
        }
        catch (JsonException exception)
        {
            SetAside(path, exception.Message);
            return [];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[TEMPO] Could not read {path}: {exception.Message}");
            return [];
        }
        if (file?.Songs is null || file.Version != FileVersion)
        {
            SetAside(path, $"unexpected version {file?.Version}");
            return [];
        }
        Dictionary<string, SongTempoMap> valid = new(StringComparer.Ordinal);
        foreach ((string source, SongTempoMap map) in file.Songs)
        {
            if (map is not null && IsValid(map))
            {
                valid[source] = map;
            }
            else
            {
                Console.Error.WriteLine($"[TEMPO] Dropped an invalid tempo map for {source}.");
            }
        }
        return valid;
    }

    /// <summary>Keeps an unreadable file under another name, so a repair never destroys typed-in maps.</summary>
    private static void SetAside(string path, string reason)
    {
        string kept = $"{path}.unreadable-{DateTime.UtcNow:yyyyMMddHHmmss}";
        try
        {
            File.Move(path, kept, overwrite: true);
            Console.Error.WriteLine($"[TEMPO] {path} could not be read ({reason}); kept as {kept}.");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[TEMPO] {path} could not be read ({reason}) or set aside: {exception.Message}");
        }
    }

    private static void Write(string path, Dictionary<string, SongTempoMap> songs)
    {
        string directory = Path.GetDirectoryName(path)
            ?? throw new InvalidOperationException("The tempo map path has no parent directory.");
        Directory.CreateDirectory(directory);
        string temporaryPath = Path.Combine(directory, $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporaryPath, JsonSerializer.Serialize(new TempoMapFile(FileVersion, songs), JsonOptions));
            File.Move(temporaryPath, path, overwrite: true);
        }
        finally
        {
            try
            {
                if (File.Exists(temporaryPath))
                {
                    File.Delete(temporaryPath);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }
}

/// <summary>Between a stored map, a song's score and the timeline.</summary>
public static class SongTempoMaps
{
    /// <summary>The tempo a song without marks plays at: <see cref="SongTimelineOptions.DefaultTempoBpm"/>, a quarter.</summary>
    public static readonly TempoMark Fallback = new(120, BeatUnit.Quarter);

    /// <summary>
    /// The number the TEMPO panel shows for a measure. For a PDF conversion that is its place in
    /// the song, which is also the number in its exported MusicXML; an imported score keeps the
    /// numbers printed in it.
    /// </summary>
    public static string BarName(SongPerformance performance, int measure)
    {
        ArgumentNullException.ThrowIfNull(performance);
        string printed = performance.Measures[measure].Number;
        return performance.Kind == "omr-pages" || string.IsNullOrWhiteSpace(printed)
            ? (measure + 1).ToString(System.Globalization.CultureInfo.InvariantCulture)
            : printed;
    }

    /// <summary>Whether a map's bar changes belong to this conversion (see <see cref="SongTempoMap.MeasureCount"/>).</summary>
    public static bool ChangesApply(SongTempoMap map, SongPerformance performance) =>
        map.MeasureCount == performance.Measures.Count;

    /// <summary>
    /// What the timeline plays for a stored map: its start always, its bar changes only where they
    /// belong to this conversion. Null without a map, so the score's own marks play.
    /// </summary>
    public static TempoOverride? Override(SongTempoMap? map, SongPerformance? performance)
    {
        if (map is null || performance is null)
        {
            return null;
        }
        IEnumerable<BarTempo> changes = ChangesApply(map, performance)
            ? map.Changes.Where(change => change.Measure < performance.Measures.Count)
            : [];
        return new TempoOverride(map.Start.QuarterBpm,
            changes.Select(static change => new TempoOverride.Change(change.Measure, change.Offset, change.Tempo.QuarterBpm))
                .ToArray());
    }

    /// <summary>
    /// A first map for a song, holding what it plays now: its score's marks, or 120. Editing then
    /// starts from what the user hears, and since a map replaces the marks, nothing changes until
    /// the user changes it.
    /// </summary>
    public static SongTempoMap FromScore(SongPerformance performance, OmrEngine engine)
    {
        ArgumentNullException.ThrowIfNull(performance);
        // The same rule as the timeline: the last mark at a position wins.
        Dictionary<(int Measure, double Offset), SongTempo> marks = [];
        foreach (SongTempo tempo in performance.Tempos.Where(static tempo => tempo.QuarterBpm is not null))
        {
            marks[(tempo.Measure, tempo.Offset)] = tempo;
        }
        TempoMark start = Fallback;
        List<BarTempo> changes = [];
        foreach (((int measure, double offset), SongTempo tempo) in marks.OrderBy(static pair => pair.Key.Measure)
                     .ThenBy(static pair => pair.Key.Offset))
        {
            TempoMark mark = Mark(tempo);
            if (measure == 0 && offset <= 0)
            {
                start = mark;
            }
            else
            {
                changes.Add(new BarTempo(measure, Math.Max(0, offset), mark));
            }
        }
        return new SongTempoMap(start, changes, engine, performance.Measures.Count, DateTimeOffset.UtcNow);
    }

    /// <summary>
    /// A score mark as the panel shows it: in its own unit when the panel has one, otherwise in
    /// quarters. A <c>&lt;sound tempo&gt;</c> that disagrees with the printed metronome is what
    /// plays, so then the quarters are kept rather than the printed figure.
    /// </summary>
    private static TempoMark Mark(SongTempo tempo)
    {
        double quarterBpm = tempo.QuarterBpm!.Value;
        return BeatUnits.FromScore(tempo.BeatUnit, tempo.Dots) is BeatUnit unit &&
            tempo.PerMinute is double perMinute && Math.Abs(perMinute * unit.Quarters() - quarterBpm) < 1e-6
                ? new TempoMark(perMinute, unit)
                : new TempoMark(quarterBpm, BeatUnit.Quarter);
    }

    /// <summary>The tempo in force at the start of <paramref name="measure"/>, in the map's own terms.</summary>
    public static TempoMark TempoAt(SongTempoMap map, int measure)
    {
        TempoMark current = map.Start;
        foreach (BarTempo change in map.Changes.OrderBy(static change => change.Measure)
                     .ThenBy(static change => change.Offset))
        {
            if (change.Measure > measure)
            {
                break;
            }
            current = change.Tempo;
        }
        return current;
    }
}
