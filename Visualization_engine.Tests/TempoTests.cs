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

    // --- Printed marks -----------------------------------------------------------------------

    [Fact]
    public void APrintedMarkLandsOnItsPagesFirstBarPlusItsPlaceAndStaysWithinThePage()
    {
        // Two HOMR pages of 3 and 4 bars, as the PDF's two pages; the reader counted 5 bars on page 2.
        SongPerformance performance = Performance([4, 4, 4, 4, 4, 4, 4], pageSizes: [3, 4]);
        DetectedTempos detected = Detected([new DetectedPage(1, 3), new DetectedPage(1, 5)],
            Printed(0, 0, 110, "quarter"), Printed(1, 1, 110, "dotted_quarter", "Calmando"), Printed(1, 4, 186, "quarter"),
            Printed(1, 2, null, null, "a tempo"), Printed(1, 3, 72, "eighth+dot"));

        IReadOnlyList<PrintedMark> placed = TempoDetection.Place(detected, performance);

        Assert.Equal([0, 4, 5, 6, 6], placed.Select(mark => mark.Measure));
        Assert.Equal(new TempoMark(110, BeatUnit.Quarter), placed[0].Tempo);
        Assert.Equal(new TempoMark(110, BeatUnit.DottedQuarter), placed[1].Tempo);
        // A tempo word is a hint without a tempo, and a unit the panel has no symbol for cannot be used.
        Assert.Null(placed[2].Tempo);
        Assert.Equal("a tempo", placed[2].Source.Suggestion);
        Assert.False(placed[3].Usable);
        Assert.Equal(new TempoMark(186, BeatUnit.Quarter), placed[4].Tempo);
        // Words are what the panel shows beside a mark; the note glyph read as "J" or "√" is not one.
        Assert.Equal(["Calmando", "a tempo"], placed.Select(static mark => mark.Words).OfType<string>());
        Assert.Null(new PrintedMark(Printed(0, 0, 186, "quarter", "√"), 0, new TempoMark(186, BeatUnit.Quarter)).Words);
    }

    [Fact]
    public void PrintedMarksAreNotPlacedOnAConversionWhosePagesDifferFromThePdfs()
    {
        SongPerformance performance = Performance([4, 4, 4], pageSizes: [3]);
        DetectedTempos detected = Detected([new DetectedPage(1, 2), new DetectedPage(1, 1)], Printed(1, 0, 90, "half"));
        PrintedMark mark = Assert.Single(TempoDetection.Place(detected, performance));
        Assert.Null(mark.Measure);
        Assert.False(mark.Usable);
        DetectedTempos onePage = Detected([new DetectedPage(1, 3)], Printed(0, 0, 90, "half"));
        Assert.Null(Assert.Single(TempoDetection.Place(onePage, Performance([4, 4, 4], kind: "musicxml"))).Measure);
    }

    [Fact]
    public void UseTakesAMarkIntoTheMapAtItsBarAndTheFirstBarsSetsTheStart()
    {
        SongPerformance performance = Performance([4, 4, 4, 4]);
        SongTempoMap map = SongTempoMaps.FromScore(performance, OmrEngine.Homr480);
        PrintedMark start = new(Printed(0, 0, 110, "quarter"), 0, new TempoMark(110, BeatUnit.Quarter));
        PrintedMark change = new(Printed(0, 2, 165, "quarter"), 2, new TempoMark(165, BeatUnit.Quarter));
        PrintedMark corrected = change with { Tempo = new TempoMark(110, BeatUnit.DottedQuarter) };

        Assert.False(TempoDetection.InUse(map, start));
        map = TempoDetection.Use(TempoDetection.Use(map, start), change);
        Assert.Equal(new TempoMark(110, BeatUnit.Quarter), map.Start);
        Assert.Equal([new BarTempo(2, 0, new TempoMark(165, BeatUnit.Quarter))], map.Changes);
        Assert.True(TempoDetection.InUse(map, start) && TempoDetection.InUse(map, change));
        // Using another mark at the same bar replaces the change rather than stacking a second one.
        map = TempoDetection.Use(map, corrected);
        Assert.Equal([new BarTempo(2, 0, new TempoMark(110, BeatUnit.DottedQuarter))], map.Changes);
        Assert.False(TempoDetection.InUse(map, change));
        PrintedMark unplaced = change with { Measure = null };
        Assert.Same(map, TempoDetection.Use(map, unplaced));
    }

    [Fact]
    public void StoredMarksCountOnlyForTheReaderAndPdfTheyWereReadWith()
    {
        using TemporaryDirectory temporary = new();
        string source = new('a', 64);
        string path = TempoDetection.StorePath(temporary.Path, source);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        // As tempo_marks.py writes it, with the fields the app does not read.
        File.WriteAllText(path, $$"""
            {"schema_version": 1, "reader_sha256": "reader-1", "frozen_reader_sha256": "x", "ocr": {"engine": "rapidocr"},
             "dpi": 300, "source_name": "song.pdf", "source_sha256": "{{source}}",
             "pages": [{"systems": 7, "measures": 43, "light_ink": false}],
             "marks": [{"page": 0, "system": 0, "box": [1, 2, 3, 4], "text": "Andantino J= 140", "source": "ocr", "bpm": 140.0,
                        "unit": "quarter", "unit_source": "glyph", "words": "Andantino", "suggestion": "andantino",
                        "page_measure": 0, "measure": 0}],
             "seconds": 3.9}
            """);

        DetectedTempos read = TempoDetection.Load(temporary.Path, source, "reader-1")!;
        DetectedMark mark = Assert.Single(read.Marks);
        Assert.Equal((0, 140.0, "quarter", "Andantino"), (mark.PageMeasure!.Value, mark.Bpm!.Value, mark.Unit, mark.Words));
        Assert.Equal([new DetectedPage(7, 43)], read.Pages);
        Assert.Null(TempoDetection.Load(temporary.Path, source, "reader-2"));
        Assert.Null(TempoDetection.Load(temporary.Path, source, null));
        Assert.Null(TempoDetection.Load(temporary.Path, new string('b', 64), "reader-1"));
    }

    [Fact]
    public void IgnoredMarksAreStoredPerSongAndAFileWithoutAnyIsWrittenAsBefore()
    {
        using TemporaryDirectory temporary = new();
        string path = Path.Combine(temporary.Path, "tempo-maps.json");
        SongTempoMap map = new(new TempoMark(90, BeatUnit.Half), [], OmrEngine.Homr480, 3, DateTimeOffset.UnixEpoch);
        TempoMapStore.Save("song", map, path);
        Assert.DoesNotContain("ignored", File.ReadAllText(path));

        TempoMapStore.SetIgnoredMarks("song", ["0:3:72:quarter:J=72", "1:0:60:half:d=60"], path);
        Assert.Equal(new HashSet<string> { "0:3:72:quarter:J=72", "1:0:60:half:d=60" }, TempoMapStore.GetIgnoredMarks("song", path));
        Assert.Empty(TempoMapStore.GetIgnoredMarks("other", path));
        Assert.Equal(map.Start, TempoMapStore.Get("song", path)!.Start);
        TempoMapStore.Save("song", map with { Start = new TempoMark(100, BeatUnit.Half) }, path);
        Assert.Equal(2, TempoMapStore.GetIgnoredMarks("song", path).Count);

        TempoMapStore.SetIgnoredMarks("song", [], path);
        Assert.Empty(TempoMapStore.GetIgnoredMarks("song", path));
        Assert.DoesNotContain("ignored", File.ReadAllText(path));
    }

    private static DetectedMark Printed(int page, int pageMeasure, double? bpm, string? unit, string? words = null) =>
        new(page, 0, pageMeasure, bpm, unit, $"{words} = {bpm}", words, bpm is null ? words : null);

    private static DetectedTempos Detected(DetectedPage[] pages, params DetectedMark[] marks) =>
        new(TempoDetection.SchemaVersion, "reader", new string('0', 64), pages, marks);

    // --- Helpers -----------------------------------------------------------------------------

    private static double[] Starts(IEnumerable<Note> notes) =>
        notes.Select(note => Math.Round(note.StartTime, 9)).ToArray();

    private static object Mark(int measure, double offset, string? unit, int dots, double? perMinute, double quarterBpm) => new
    {
        measure, offset, part = 0, staff = 0, beat_unit = unit, dots, per_minute = perMinute, quarter_bpm = quarterBpm,
        source = unit is null ? "sound" : "metronome"
    };

    /// <summary>A performance with one short note at the start of each measure, so note starts are bar starts.</summary>
    /// <param name="pageSizes">Measures per HOMR page; one page holds them all by default.</param>
    private static SongPerformance Performance(double[] lengths, string kind = "omr-pages", int[]? playOrder = null,
        string[]? numbers = null, object[]? tempos = null, int[]? pageSizes = null)
    {
        double[] starts = new double[lengths.Length];
        for (int index = 1; index < lengths.Length; index++)
        {
            starts[index] = starts[index - 1] + lengths[index - 1];
        }
        int[] sizes = pageSizes ?? [lengths.Length];
        int[] firsts = sizes.Select((_, page) => sizes.Take(page).Sum()).ToArray();
        int PageOf(int measure) => Array.FindLastIndex(firsts, first => first <= measure);
        var document = new
        {
            schema_version = 3,
            kind,
            sources = new[] { new { name = "page-0001.musicxml", sha256 = new string('0', 64) } },
            timing_correction = false,
            parts = new[] { new { index = 0, staves = 1, name = "Piano" } },
            pages = sizes.Select((size, page) => new { index = page, name = $"page-{page + 1:0000}.musicxml",
                first_measure = firsts[page], measures = size, start_beat = starts[firsts[page]],
                decoded_beats = lengths.Skip(firsts[page]).Take(size).Sum(), advance_beats = lengths.Skip(firsts[page]).Take(size).Sum(),
                timing = "off" }),
            measures = lengths.Select((length, index) => new
            {
                index, page = PageOf(index), number = numbers?[index] ?? (index + 1).ToString(), start_beat = starts[index],
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
