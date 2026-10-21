using System.Text.Json;
using SynthesiaClone;
using Note = SynthesiaClone.Note;

namespace Visualization_engine.Tests;

/// <summary>
/// The TEMPO panel's map: how it times a song, where it is stored, and what it does when the song
/// it was set on is converted again.
/// </summary>
public sealed class TempoTests
{
    // --- Timing ------------------------------------------------------------------------------

    [Fact]
    public void AStartTempoAndBarChangesTimeTheSongIncludingADottedQuarterIn12Over8()
    {
        // "Beyond This Station" in miniature: two 4/4 bars at ♩ = 110, two 12/8 bars at ♩. = 110
        // (♩ = 165), then 4/4 at ♩ = 186.
        SongPerformance performance = Performance([4, 4, 6, 6, 4]);
        SongTempoMap map = new(new TempoMark(110, BeatUnit.Quarter),
            [new BarTempo(2, 0, new TempoMark(110, BeatUnit.DottedQuarter)), new BarTempo(4, 0, new TempoMark(186, BeatUnit.Quarter))],
            OmrEngine.Homr480, 5, DateTimeOffset.UtcNow);

        List<Note> notes = SongTimeline.BuildNotes(performance, new SongTimelineOptions(Tempo: SongTempoMaps.Override(map, performance)));

        double[] expected = [0, 240.0 / 110, 480.0 / 110, 480.0 / 110 + 360.0 / 165, 480.0 / 110 + 720.0 / 165];
        Assert.Equal(expected.Select(seconds => Math.Round(seconds, 9)), Starts(notes));
        // The last note is half a beat at ♩ = 186.
        Assert.Equal(Math.Round(30.0 / 186, 9), Math.Round(notes[^1].Duration, 9));
    }

    [Fact]
    public void AChangePlaysOnEveryPassAndHoldsBackAcrossTheRepeat()
    {
        // The rule printed marks already follow: measure 1 at 60 slows measure 0's second pass too.
        SongPerformance performance = Performance([2, 2, 2], playOrder: [0, 1, 0, 1, 2]);
        TempoOverride tempo = new(120, [new TempoOverride.Change(1, 0, 60)]);
        Assert.Equal([0.0, 1.0, 3.0, 5.0, 7.0],
            Starts(SongTimeline.BuildNotes(performance, new SongTimelineOptions(Tempo: tempo))));
    }

    [Fact]
    public void TheUserMapReplacesTheScoresMarksWhichReplaceTheDefault()
    {
        SongPerformance plain = Performance([4, 4, 4]);
        SongPerformance marked = Performance([4, 4, 4], tempos: [Mark(0, 0, "quarter", 0, 90, 90), Mark(2, 0, "quarter", 0, 200, 200)]);

        Assert.Equal([0.0, 2.0, 4.0], Starts(SongTimeline.BuildNotes(plain)));
        Assert.Equal([0.0, Math.Round(240.0 / 90, 9), Math.Round(480.0 / 90, 9)], Starts(SongTimeline.BuildNotes(marked)));
        // The map's start alone: the score's 200 at measure 2 no longer plays.
        TempoOverride user = new(100, []);
        Assert.Equal([0.0, 2.4, 4.8], Starts(SongTimeline.BuildNotes(marked, new SongTimelineOptions(Tempo: user))));
    }

    [Fact]
    public void ARetimedSessionKeepsItsPlaceInTheBar()
    {
        SongPerformance performance = Performance([4, 4, 4]);
        SongLoadResult song = new([], "Song", OmrEngine.Homr480, true, null, performance, SourceSha256: "a");
        TempoOverride slower = new(60, []);

        // Three seconds at 120 is two beats into measure 1; at 60 the same point is six seconds in.
        Assert.Equal(6.0, ExpressionPlayback.MapPosition(song, new ExpressionOptions(), new ExpressionOptions(), 3.0,
            null, slower), 9);
        Assert.Equal(3.0, ExpressionPlayback.MapPosition(song, new ExpressionOptions(), new ExpressionOptions(), 6.0,
            slower, null), 9);
        // Nothing changed, nothing moves.
        Assert.Equal(3.0, ExpressionPlayback.MapPosition(song, new ExpressionOptions(), new ExpressionOptions(), 3.0,
            slower, new TempoOverride(60, [])), 9);
    }

    [Fact]
    public void OverridesAreEqualWhenTheyTimeASongTheSameWay()
    {
        TempoOverride first = new(110, [new TempoOverride.Change(2, 0, 165)]);
        TempoOverride second = new(110, new List<TempoOverride.Change> { new(2, 0, 165) });
        Assert.Equal(first, second);
        Assert.Equal(new SongTimelineOptions(Tempo: first), new SongTimelineOptions(Tempo: second));
        Assert.NotEqual(first, new TempoOverride(110, [new TempoOverride.Change(3, 0, 165)]));
        Assert.NotEqual(new SongTimelineOptions(Tempo: first), new SongTimelineOptions());
    }

    // --- Another conversion of the same file --------------------------------------------------

    [Fact]
    public void BarChangesPlayOnlyOnAConversionWithTheSameNumberOfBars()
    {
        SongPerformance performance = Performance([4, 4, 4, 4, 4]);
        BarTempo change = new(3, 0, new TempoMark(90, BeatUnit.Quarter));
        SongTempoMap elsewhere = new(new TempoMark(100, BeatUnit.Quarter), [change], OmrEngine.Homr465, 7, DateTimeOffset.UtcNow);

        TempoOverride startOnly = SongTempoMaps.Override(elsewhere, performance)!;
        Assert.False(SongTempoMaps.ChangesApply(elsewhere, performance));
        Assert.Equal(100, startOnly.StartQuarterBpm);
        Assert.Empty(startOnly.Changes);

        TempoOverride both = SongTempoMaps.Override(elsewhere with { MeasureCount = 5 }, performance)!;
        Assert.Equal([new TempoOverride.Change(3, 0, 90)], both.Changes);
        Assert.Null(SongTempoMaps.Override(null, performance));
    }

    // --- Starting from the score -------------------------------------------------------------

    [Fact]
    public void AFirstMapHoldsTheScoresMarksSoNothingChangesUntilTheUserEditsIt()
    {
        SongPerformance performance = Performance([4, 4, 4, 4], kind: "musicxml", tempos:
        [
            Mark(0, 0, "quarter", 1, 80, 120),
            // A <sound tempo> that disagrees with the printed metronome is what plays.
            Mark(1, 0, "quarter", 0, 100, 96),
            Mark(2, 1, "quarter", 0, 100, 100),
            Mark(3, 0, null, 0, null, 150)
        ]);

        SongTempoMap seeded = SongTempoMaps.FromScore(performance, OmrEngine.MusicXml);

        Assert.Equal(new TempoMark(80, BeatUnit.DottedQuarter), seeded.Start);
        Assert.Equal(
        [
            new BarTempo(1, 0, new TempoMark(96, BeatUnit.Quarter)),
            new BarTempo(2, 1, new TempoMark(100, BeatUnit.Quarter)),
            new BarTempo(3, 0, new TempoMark(150, BeatUnit.Quarter))
        ], seeded.Changes);
        Assert.Equal(4, seeded.MeasureCount);
        Assert.Equal(Starts(SongTimeline.BuildNotes(performance)),
            Starts(SongTimeline.BuildNotes(performance, new SongTimelineOptions(Tempo: SongTempoMaps.Override(seeded, performance)))));
    }

    [Fact]
    public void AScoreWithoutMarksStartsAt120AndTheTempoAtABarIsTheLastChangeBeforeIt()
    {
        SongTempoMap seeded = SongTempoMaps.FromScore(Performance([4, 4, 4]), OmrEngine.Homr480);
        Assert.Equal(SongTempoMaps.Fallback, seeded.Start);
        Assert.Empty(seeded.Changes);

        SongTempoMap map = seeded with
        {
            Changes = [new BarTempo(1, 0, new TempoMark(140, BeatUnit.Quarter)), new BarTempo(2, 0, new TempoMark(70, BeatUnit.Half))]
        };
        Assert.Equal(SongTempoMaps.Fallback, SongTempoMaps.TempoAt(map, 0));
        Assert.Equal(new TempoMark(140, BeatUnit.Quarter), SongTempoMaps.TempoAt(map, 1));
        Assert.Equal(new TempoMark(70, BeatUnit.Half), SongTempoMaps.TempoAt(map, 2));
    }

    // --- Bar numbers -------------------------------------------------------------------------

    [Fact]
    public void APdfConversionCountsBarsThroughTheSongWhileAnImportKeepsItsPrintedNumbers()
    {
        // HOMR numbers each page's measures from 1.
        SongPerformance pages = Performance([4, 4, 4, 4], numbers: ["1", "2", "1", "2"]);
        Assert.Equal(["1", "2", "3", "4"], Enumerable.Range(0, 4).Select(index => SongTempoMaps.BarName(pages, index)));
        SongOverlay overlay = SongOverlay.For(pages, new SongTimelineOptions(), []);
        Assert.Equal([0, 1, 2, 3], overlay.Bars.Select(bar => bar.Measure));
        Assert.Equal("Bar 3", overlay.BarLabel(4.1));

        SongPerformance imported = Performance([1, 4, 4], kind: "musicxml", numbers: ["0", "1", "2"]);
        Assert.Equal(["0", "1", "2"], Enumerable.Range(0, 3).Select(index => SongTempoMaps.BarName(imported, index)));
    }

    // --- The store ---------------------------------------------------------------------------

    [Fact]
    public void AMapIsStoredBySourceAndReadsBackAsEntered()
    {
        using TemporaryDirectory temporary = new();
        string path = Path.Combine(temporary.Path, "tempo-maps.json");
        SongTempoMap map = new(new TempoMark(110, BeatUnit.Quarter),
            [new BarTempo(16, 0, new TempoMark(110, BeatUnit.DottedQuarter)), new BarTempo(24, 0, new TempoMark(186.5, BeatUnit.Quarter))],
            OmrEngine.Homr480, 214, new DateTimeOffset(2026, 10, 21, 12, 0, 0, TimeSpan.Zero));

        Assert.Null(TempoMapStore.Get("abc", path));
        TempoMapStore.Save("abc", map, path);
        SongTempoMap read = TempoMapStore.Get("abc", path)!;
        Assert.Equal(map.Start, read.Start);
        Assert.Equal(map.Changes, read.Changes);
        Assert.Equal((map.Engine, map.MeasureCount, map.UpdatedUtc), (read.Engine, read.MeasureCount, read.UpdatedUtc));
        Assert.Contains("\"dotted_quarter\"", File.ReadAllText(path));
        Assert.Empty(Directory.GetFiles(temporary.Path, "*.tmp"));

        TempoMapStore.Remove("abc", path);
        Assert.Null(TempoMapStore.Get("abc", path));
        Assert.Throws<ArgumentException>(() => TempoMapStore.Save("abc", map with { Start = new TempoMark(9999, BeatUnit.Quarter) }, path));
    }

    [Fact]
    public void AnUnreadableStoreIsKeptAsideAndOneBadEntryDoesNotCostTheOthers()
    {
        using TemporaryDirectory temporary = new();
        string path = Path.Combine(temporary.Path, "tempo-maps.json");
        File.WriteAllText(path, "{ not json");
        Assert.Empty(TempoMapStore.LoadAll(path));
        string kept = Assert.Single(Directory.GetFiles(temporary.Path, "tempo-maps.json.unreadable-*"));
        Assert.Equal("{ not json", File.ReadAllText(kept));

        static string Entry(int bpm) =>
            $$"""{"start":{"bpm":{{bpm}},"unit":"half"},"changes":[],"engine":"homr465","measure_count":3,"updated_utc":"2026-10-21T00:00:00+00:00"}""";
        File.WriteAllText(path, "{\"version\":1,\"songs\":{\"good\":" + Entry(90) + ",\"bad\":" + Entry(9000) + "}}");
        IReadOnlyDictionary<string, SongTempoMap> loaded = TempoMapStore.LoadAll(path);
        Assert.Equal(["good"], loaded.Keys);
        Assert.Equal(new TempoMark(90, BeatUnit.Half), loaded["good"].Start);
    }

    [Theory]
    [InlineData("110", 110.0)]
    [InlineData(" 110.5 ", 110.5)]
    [InlineData("72,5", 72.5)]
    [InlineData("186 bpm", 186.0)]
    public void TypedTempiAreAccepted(string text, double expected)
    {
        Assert.True(TempoRules.TryParse(text, out double bpm, out string? error), error);
        Assert.Equal(expected, bpm);
    }

    [Theory]
    [InlineData("")]
    [InlineData("abc")]
    [InlineData("110.55")]
    [InlineData("5")]
    [InlineData("401")]
    [InlineData("1.2,3")]
    public void TypedTempiOutsideTheRulesAreRefused(string text)
    {
        Assert.False(TempoRules.TryParse(text, out _, out string? error));
        Assert.False(string.IsNullOrWhiteSpace(error));
    }

    [Fact]
    public void StepsLandOnWholeNumbersInsideTheRange()
    {
        Assert.Equal(111, TempoRules.Step(110.5, 1));
        Assert.Equal(110, TempoRules.Step(110.5, -1));
        Assert.Equal(121, TempoRules.Step(120, 1));
        Assert.Equal(TempoRules.Maximum, TempoRules.Step(TempoRules.Maximum, 1));
        Assert.Equal(TempoRules.Minimum, TempoRules.Step(TempoRules.Minimum, -1));
        Assert.Equal(BeatUnit.Quarter, BeatUnit.Eighth.Next());
        Assert.Equal(1.5, BeatUnit.DottedQuarter.Quarters());
    }

    // --- Helpers -----------------------------------------------------------------------------

    private static double[] Starts(IEnumerable<Note> notes) =>
        notes.Select(note => Math.Round(note.StartTime, 9)).ToArray();

    private static object Mark(int measure, double offset, string? unit, int dots, double? perMinute, double quarterBpm) => new
    {
        measure, offset, part = 0, staff = 0, beat_unit = unit, dots, per_minute = perMinute, quarter_bpm = quarterBpm,
        source = unit is null ? "sound" : "metronome"
    };

    /// <summary>A performance with one short note at the start of each measure, so note starts are bar starts.</summary>
    private static SongPerformance Performance(double[] lengths, string kind = "omr-pages", int[]? playOrder = null,
        string[]? numbers = null, object[]? tempos = null)
    {
        double[] starts = new double[lengths.Length];
        for (int index = 1; index < lengths.Length; index++)
        {
            starts[index] = starts[index - 1] + lengths[index - 1];
        }
        var document = new
        {
            schema_version = 3,
            kind,
            sources = new[] { new { name = "page-0001.musicxml", sha256 = new string('0', 64) } },
            timing_correction = false,
            parts = new[] { new { index = 0, staves = 1, name = "Piano" } },
            pages = new[] { new { index = 0, name = "page-0001.musicxml", first_measure = 0, measures = lengths.Length,
                start_beat = 0.0, decoded_beats = lengths.Sum(), advance_beats = lengths.Sum(), timing = "off" } },
            measures = lengths.Select((length, index) => new
            {
                index, page = 0, number = numbers?[index] ?? (index + 1).ToString(), start_beat = starts[index],
                length_beats = length, bar_beats = length, time_signature = length == 6 ? new[] { 12, 8 } : new[] { (int)length, 4 },
                pickup = false, repeat_start = false, repeat_end = 0, ending = (int[]?)null, ending_stop = false,
                jumps = (object?)null
            }),
            play_order = playOrder ?? Enumerable.Range(0, lengths.Length).ToArray(),
            notes = lengths.Select((_, index) => new
            {
                pitch = "X", midi = 60 + index, measure = index, offset = 0.0, duration = 0.5, part = 0, staff = 0,
                voice = "1", grace = false, grace_slash = false, tied = false, articulations = Array.Empty<string>(),
                slurs = Array.Empty<string>()
            }),
            pedals = Array.Empty<object>(),
            dynamics = Array.Empty<object>(),
            wedges = Array.Empty<object>(),
            tempos = tempos ?? [],
            features = new { },
            warnings = Array.Empty<string>()
        };
        return SongPerformance.Parse(JsonSerializer.Serialize(document));
    }
}
