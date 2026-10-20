using System.Text.Json;
using Raylib_cs;
using SynthesiaClone;
using Note = SynthesiaClone.Note;

namespace Visualization_engine.Tests;

/// <summary>
/// Phase 5 of the MusicXML songs plan: bar lines and the bar readout, the pedal lane, hand colour by
/// staff, the song's feature counts, Export MIDI, Export MusicXML and Re-convert's source lookup, and
/// the home screen offering only HOMR 480 and 465 and the two pianos.
/// </summary>
public sealed class FrontendScoreTests
{
    [Fact]
    public void BarsFollowThePlayOrderAndNameTheirPass()
    {
        SongOverlay overlay = SongOverlay.For(Score(), new SongTimelineOptions(), []);

        // 120 bpm, four beats a bar: two seconds each, bars 3 and 4 played twice.
        Assert.Equal([0.0, 2, 4, 6, 8, 10], overlay.Bars.Select(bar => bar.Seconds));
        Assert.Equal(["1", "2", "3", "4", "3", "4"], overlay.Bars.Select(bar => bar.Number));
        Assert.Equal("Bar 1", overlay.BarLabel(0.5));
        Assert.Equal("Bar 3 · 1st time", overlay.BarLabel(4.0));
        Assert.Equal("Bar 3 · 2nd time", overlay.BarLabel(9.0));
        Assert.Equal("Bar 4 · 2nd time", overlay.BarLabel(30.0));
        // Before the first bar, the first; on a bar line, the bar that starts there.
        Assert.Equal("Bar 1", overlay.BarLabel(-1.0));
        Assert.Equal(3, overlay.BarIndexAt(6.0));
        Assert.Equal(3, overlay.FirstBarFrom(5.5));
        Assert.Equal(3, overlay.FirstBarFrom(6.0));
        Assert.Equal(overlay.Bars.Count, overlay.FirstBarFrom(10.5));
    }

    [Fact]
    public void WithoutRepeatsEveryBarPlaysOnceAndHasNoPass()
    {
        SongOverlay overlay = SongOverlay.For(Score(), new SongTimelineOptions(ExpandRepeats: false), []);

        Assert.Equal(4, overlay.Bars.Count);
        Assert.Equal("Bar 3", overlay.BarLabel(4.0));
    }

    [Fact]
    public void ASongWithoutAScoreHasNoBarsButKeepsItsPedal()
    {
        SongOverlay overlay = SongOverlay.For(null, new SongTimelineOptions(), [new PedalChange(1, 127), new PedalChange(2, 0)]);

        Assert.Empty(overlay.Bars);
        Assert.Null(overlay.BarLabel(1.5));
        Assert.True(overlay.IsPedalDown(1.5));
    }

    [Fact]
    public void PedalSpansPairPressesWithReleases()
    {
        SongOverlay overlay = SongOverlay.For(null, new SongTimelineOptions(),
        [
            new PedalChange(1, 127),
            new PedalChange(1.5, 100), // still down: extends the span
            new PedalChange(2, 0),
            new PedalChange(2, 127),   // re-pedalled at the same moment
            new PedalChange(3, 0),
            new PedalChange(4, 0),     // a release while up changes nothing
            new PedalChange(5, 127)    // never released
        ]);

        Assert.Equal([(1.0, 2.0), (2.0, 3.0), (5.0, double.PositiveInfinity)], overlay.PedalDown);
        Assert.False(overlay.IsPedalDown(0.5));
        Assert.True(overlay.IsPedalDown(1.0));
        Assert.True(overlay.IsPedalDown(2.0));
        Assert.False(overlay.IsPedalDown(3.0));
        Assert.True(overlay.IsPedalDown(100));
        Assert.Equal(0, overlay.FirstPedalFrom(0));
        Assert.Equal(1, overlay.FirstPedalFrom(2.0));
        Assert.Equal(2, overlay.FirstPedalFrom(3.5));
    }

    [Fact]
    public void TheOverlayPedalIsThePedalTheTimelinePlays()
    {
        SongPerformance score = Score();
        SongTimelineOptions options = SongTimelineOptions.For(new ExpressionOptions());
        SongPlayback playback = SongTimeline.Build(score, options);
        SongOverlay overlay = SongOverlay.For(score, options, playback.Pedal);

        // Held from bar 2 to beat 3.5 of it, then from beat 1 of bar 4 for good.
        Assert.Equal([(2.0, 3.75), (6.5, double.PositiveInfinity)], overlay.PedalDown);
    }

    [Fact]
    public void HandsAreColouredByStaffInATwoStaffPart()
    {
        List<Note> notes = SongTimeline.BuildNotes(Score());

        // The right hand plays E5 and up on staff 0; the left hand C3 and up on staff 1.
        Assert.All(notes.Where(note => note.MidiPitch >= 76), note => Assert.Equal(Color.SkyBlue, note.Color));
        Assert.All(notes.Where(note => note.MidiPitch < 60), note => Assert.Equal(Color.Lime, note.Color));
    }

    [Fact]
    public void HandsAreSplitAtMiddleCWhenAPartHasOneStaff()
    {
        SongPerformance score = Score() with
        {
            Parts = [new SongPart(0, 1, "Melody")],
            Notes = [ScoreNote("C4", 60, staff: 1), ScoreNote("G3", 55, staff: 0)]
        };

        List<Note> notes = SongTimeline.BuildNotes(score);

        Assert.Equal(Color.SkyBlue, notes.Single(note => note.MidiPitch == 60).Color);
        Assert.Equal(Color.Lime, notes.Single(note => note.MidiPitch == 55).Color);
    }

    [Fact]
    public void TheFeatureSummaryCountsWhatTheScoreHolds()
    {
        Assert.Equal("4 articulations · 1 pedal · 0 dynamics · 2 repeats", Score().FeatureSummary());
        Assert.Equal("0 articulations · 0 pedals · 0 dynamics · 0 repeats",
            (Score() with { Features = default }).FeatureSummary());
    }

    [Fact]
    public void ExportMidiKeepsTimingVelocitiesOverlapsAndPedal()
    {
        using TemporaryDirectory directory = new();
        string path = Path.Combine(directory.Path, "exports", "song.mid");
        List<Note> notes =
        [
            new(39, 0.0, 1.0, 64, Color.SkyBlue),
            new(39, 0.5, 1.0, 100, Color.SkyBlue), // overlaps the first on the same key
            new(20, 1.25, 0.333, 30, Color.Lime)
        ];
        PedalChange[] pedal = [new(0.25, 127), new(1.5, 0)];

        SongCache.ExportMidi(path, notes, pedal);
        // A second export replaces the first rather than failing on the existing file.
        SongCache.ExportMidi(path, notes, pedal);

        List<Note> read = SongCache.ReadMidiForTesting(path);
        Assert.Equal(notes.Select(Describe), read.Select(Describe));
        Assert.Equal(pedal.Select(change => (Math.Round(change.Time, 3), change.Value)),
            SongCache.ReadMidiPedalForTesting(path).Select(change => (Math.Round(change.Time, 3), change.Value)));
        Assert.Single(Directory.GetFiles(Path.GetDirectoryName(path)!));
    }

    [Fact]
    public void ExportMusicXmlNeedsTheSongsScoreFile()
    {
        using TemporaryDirectory directory = new();
        string derived = Path.Combine(directory.Path, "songs", "scores", "homr480", "abc", "derived", "key");
        Directory.CreateDirectory(derived);
        File.WriteAllText(Path.Combine(derived, "interpretation.json"), "{}");
        SongLoadResult song = new([], "Song", OmrEngine.Homr480, true,
            Path.GetRelativePath(directory.Path, Path.Combine(derived, "interpretation.json")), Score());

        Assert.Null(SongCache.ScorePath(song, directory.Path));
        File.WriteAllText(Path.Combine(derived, "score.musicxml"), "<score-partwise/>");
        Assert.Equal(Path.Combine(derived, "score.musicxml"), SongCache.ScorePath(song, directory.Path));
        // A legacy MIDI cache has no score at all.
        Assert.Null(SongCache.ScorePath(song with { Performance = null }, directory.Path));
    }

    [Fact]
    public void ReconvertFindsAPackagesSourceByItsHash()
    {
        using TemporaryDirectory directory = new();
        string library = Path.Combine(directory.Path, "songs", "pdf");
        Directory.CreateDirectory(library);
        string other = Path.Combine(library, "other.pdf");
        File.WriteAllText(other, "a different score");
        string source = Path.Combine(library, "renamed by the user.pdf");
        File.WriteAllText(source, "the score");
        string package = Path.Combine(directory.Path, "songs", "scores", "homr480", "pkg");
        string derived = Path.Combine(package, "derived", "key");
        Directory.CreateDirectory(derived);
        File.WriteAllText(Path.Combine(package, "song.json"), $$"""{"source_sha256": "{{Sha256("the score")}}"}""");
        File.WriteAllText(Path.Combine(derived, "interpretation.json"), "{}");
        SongLoadResult song = new([], "Song", OmrEngine.Homr480, true,
            Path.GetRelativePath(directory.Path, Path.Combine(derived, "interpretation.json")), Score());

        Assert.Equal(source, SongCache.FindSource(song, directory.Path, [other, source]));
        Assert.Null(SongCache.FindSource(song, directory.Path, [other]));
        // An import or a MIDI file was never recognised, so there is nothing to re-convert.
        Assert.Null(SongCache.FindSource(song with { Engine = OmrEngine.MusicXml }, directory.Path, [other, source]));
    }

    [Fact]
    public void ReconvertFindsALegacyCachesSource()
    {
        using TemporaryDirectory directory = new();
        string library = Path.Combine(directory.Path, "songs", "pdf");
        Directory.CreateDirectory(library);
        string source = Path.Combine(library, "Nocturne.pdf");
        File.WriteAllText(source, "nocturne");
        string caches = Path.Combine(directory.Path, "songs", "midi", "homr");
        Directory.CreateDirectory(caches);
        string manifest = Path.Combine(caches, "Nocturne.timing-0123456789ab.mid.cache.json");
        File.WriteAllText(manifest, $$"""{"source_sha256": "{{Sha256("nocturne")}}", "engine": "homr"}""");
        SongLoadResult song = new([], "Nocturne", OmrEngine.Homr, true, Path.GetRelativePath(directory.Path, manifest));

        Assert.Equal(source, SongCache.FindSource(song, directory.Path, [source]));
    }

    [Fact]
    public void OnlyHomr480And465AndTheTwoPianosAreOffered()
    {
        Assert.Equal([OmrEngine.Homr480, OmrEngine.Homr465], OmrEngines.Offered);
        Assert.Equal(OmrEngine.Homr465, OmrEngines.ToOffered(OmrEngine.Homr465));
        Assert.Equal(OmrEngine.Homr480, OmrEngines.ToOffered(OmrEngine.Homr));
        Assert.Equal(OmrEngine.Homr480, OmrEngines.ToOffered(OmrEngine.Zeus));
        Assert.False(OmrEngines.RunsOmr(OmrEngine.MusicXml));
        Assert.False(OmrEngines.RunsOmr(OmrEngine.DirectMidi));

        Assert.Equal(AudioBackend.SfzPiano, AudioBackend.MidiDevice.Offered());
        Assert.Equal(AudioBackend.SfzPiano, AudioBackend.Silent.Offered());
        Assert.Equal(AudioBackend.SoundFont, AudioBackend.SoundFont.Offered());
        Assert.False(AudioBackend.Silent.IsBuiltIn());
        Assert.True(new AudioOutputStatus(AudioBackend.Silent, null, 0, null, null).IsSilent);
    }

    [Fact]
    public void AStoredMidiDeviceChoiceStillReadsAndKeepsItsCalibration()
    {
        using TemporaryDirectory directory = new();
        string path = directory.CreateFile("settings.json",
            """{"omr_engine": "zeus", "audio_offset_milliseconds": 80, "audio_backend": "midiDevice"}""");

        Assert.Equal(AudioBackend.MidiDevice, AppSettingsStore.LoadAudioBackendFromPath(path));
        Assert.Equal(80, AppSettingsStore.LoadAudioOffsetFromPath(path));
        Assert.Equal(OmrEngine.Homr480, OmrEngines.ToOffered(AppSettingsStore.LoadEngineFromPath(path)));
    }

    [Fact]
    public void AutoPedalLiftsAndCatchesAtEveryBarAndLetsGoAtTheEnd()
    {
        SongPerformance score = Score();
        SongPlayback playback = SongTimeline.Build(score,
            SongTimelineOptions.For(new ExpressionOptions(AutoPedal: true)));

        // The left hand holds one note a bar, so the only changes are the six bars of the play order.
        double catchSeconds = SongExpression.AutoPedalCatchSeconds;
        List<(double, int)> expected = [(catchSeconds, 127)];
        foreach (double bar in new[] { 2.0, 4, 6, 8, 10 })
        {
            expected.Add((bar, 0));
            expected.Add((bar + catchSeconds, 127));
        }
        expected.Add((12, 0));
        Assert.Equal(expected, playback.Pedal.Select(change => (Math.Round(change.Time, 6), change.Value)));
    }

    [Fact]
    public void AutoPedalChangesWhenTheBassFallsToANewNote()
    {
        // Broken chord C3 G3 E3, then G2: the climb stays in one harmony, the drop to G is a new one.
        // C2 an octave down is the same pitch class and keeps the pedal.
        SongPerformance score = Score() with
        {
            Measures = [new SongMeasure(0, 0, "1", 0, 4, 4, [4, 4], false, false, 0, null, false, null)],
            PlayOrder = [0],
            Notes =
            [
                ScoreNote("E5", 76, offset: 0, staff: 0),
                ScoreNote("C3", 48, offset: 0, duration: 1, staff: 1),
                ScoreNote("G3", 55, offset: 1, duration: 1, staff: 1),
                ScoreNote("E3", 52, offset: 1.5, duration: 0.5, staff: 1),
                ScoreNote("G2", 43, offset: 2, duration: 1, staff: 1),
                ScoreNote("G1", 31, offset: 3, duration: 1, staff: 1)
            ]
        };

        SongPlayback playback = SongTimeline.Build(score, new SongTimelineOptions(AutoPedal: true));

        Assert.Equal([(0.08, 127), (1.0, 0), (1.08, 127), (2.0, 0)],
            playback.Pedal.Select(change => (Math.Round(change.Time, 6), change.Value)));
    }

    [Fact]
    public void AutoPedalReplacesTheMarksAndIsOffByDefault()
    {
        SongPerformance score = Score();
        Assert.False(new ExpressionOptions().AutoPedal);
        IReadOnlyList<PedalChange> marks = SongTimeline.Build(score, SongTimelineOptions.For(new ExpressionOptions())).Pedal;
        IReadOnlyList<PedalChange> auto = SongTimeline.Build(score,
            SongTimelineOptions.For(new ExpressionOptions(Pedal: false, AutoPedal: true))).Pedal;

        Assert.Equal(2, marks.Count(change => change.IsDown));
        Assert.Equal(6, auto.Count(change => change.IsDown));
        Assert.True(SongExpression.Availability(score).AutoPedal);
        Assert.False(ExpressionPlayback.Availability(new SongLoadResult([], "midi", OmrEngine.DirectMidi, true, null)).AutoPedal);
    }

    [Fact]
    public void TheAutoPedalSwitchIsSavedAndOldSettingsLeaveItOff()
    {
        using TemporaryDirectory directory = new();
        string path = directory.CreateFile("settings.json", """{"omr_engine": "homr480"}""");

        Assert.False(AppSettingsStore.LoadExpressionFromPath(path).AutoPedal);
        AppSettingsStore.SaveExpressionToPath(new ExpressionOptions(AutoPedal: true), path);
        Assert.True(AppSettingsStore.LoadExpressionFromPath(path).AutoPedal);
    }

    [Fact]
    public void ANumberedLibraryCopyIsListedUnderItsSongsName()
    {
        using TemporaryDirectory directory = new();
        string pdf = Path.Combine(directory.Path, "songs", "pdf");
        string caches = Path.Combine(directory.Path, "songs", "midi", "homr465");
        Directory.CreateDirectory(pdf);
        Directory.CreateDirectory(caches);
        string named = new string('a', 64) + "-" + new string('b', 64);
        string unnamed = new string('c', 64) + "-" + new string('d', 64);
        File.WriteAllText(Path.Combine(pdf, named + ".pdf"), "one");
        File.WriteAllText(Path.Combine(pdf, unnamed + ".pdf"), "two");
        File.WriteAllText(Path.Combine(pdf, "Nocturne.pdf"), "three");
        File.WriteAllText(Path.Combine(caches, named + ".mid.cache.json"), """{"display_name": "Clair de lune"}""");

        Assert.Equal(["Clair de lune", "Nocturne", "Unnamed score (cccccccc)"],
            SongCache.GetPdfLibraryForTesting(directory.Path).Select(entry => entry.DisplayName));
    }

    private static string Describe(Note note) =>
        $"{note.TargetKeyIndex} {note.StartTime:F3} {note.Duration:F3} {note.Velocity}";

    private static string Sha256(string text) =>
        Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(text)));

    private static SongNote ScoreNote(string pitch, int midi, int measure = 0, double offset = 0, double duration = 1,
        int staff = 0, IReadOnlyList<string>? articulations = null) =>
        new(pitch, midi, measure, offset, duration, 0, staff, staff == 0 ? "1" : "2", false, false, false,
            articulations ?? [], []);

    /// <summary>Four bars of a two-staff piano part, bars 3 and 4 repeated, with two pedal presses.</summary>
    private static SongPerformance Score()
    {
        List<SongNote> notes = [];
        for (int measure = 0; measure < 4; measure++)
        {
            notes.Add(ScoreNote("E5", 76 + measure, measure, 0, 1, staff: 0, articulations: measure == 0 ? ["accent"] : null));
            notes.Add(ScoreNote("C3", 48 + measure, measure, 0, 4, staff: 1));
        }
        using JsonDocument features = JsonDocument.Parse(
            """{"articulation_marks": 4, "pedal_marks": 1, "dynamics_marks": 0, "repeat_backward": 1, "jump_marks": 1}""");
        return new SongPerformance(
            SongPerformance.CurrentSchemaVersion, "omr-pages", [], false, [new SongPart(0, 2, "Piano")], [],
            [
                new SongMeasure(0, 0, "1", 0, 4, 4, [4, 4], false, false, 0, null, false, null),
                new SongMeasure(1, 0, "2", 4, 4, 4, [4, 4], false, false, 0, null, false, null),
                new SongMeasure(2, 0, "3", 8, 4, 4, [4, 4], false, true, 0, null, false, null),
                new SongMeasure(3, 0, "4", 12, 4, 4, [4, 4], false, false, 1, null, false, null)
            ],
            [0, 1, 2, 3, 2, 3],
            notes,
            [
                new SongPedal(1, 0, 0, 1, "start", "mark"),
                new SongPedal(1, 3.5, 0, 1, "stop", "mark"),
                new SongPedal(3, 1, 0, 1, "start", "mark")
            ],
            [], [], [], features.RootElement.Clone(), []);
    }
}
