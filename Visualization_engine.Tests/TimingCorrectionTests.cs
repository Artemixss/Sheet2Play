using SynthesiaClone;

namespace Visualization_engine.Tests;

/// <summary>
/// The timing fix setting: on by default, routed to the correction's own entry script, and
/// never sharing a cache entry with the uncorrected conversion.
/// </summary>
public sealed class TimingCorrectionTests
{
    private const string IdentityA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string IdentityB = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    [Fact]
    public void SettingIsOnByDefaultRoundTripsAndOlderFilesLoad()
    {
        using TemporaryDirectory temporary = new();
        string path = Path.Combine(temporary.Path, "settings.json");
        Assert.True(AppSettingsStore.LoadTimingCorrectionFromPath(path));
        Assert.Contains("\"timing_correction\": true", File.ReadAllText(path));
        AppSettingsStore.SaveTimingCorrectionToPath(false, path);
        Assert.False(AppSettingsStore.LoadTimingCorrectionFromPath(path));
        AppSettingsStore.SaveEngineToPath(OmrEngine.Homr, path);
        Assert.False(AppSettingsStore.LoadTimingCorrectionFromPath(path));
        AppSettingsStore.SaveTimingCorrectionToPath(true, path);
        Assert.True(AppSettingsStore.LoadTimingCorrectionFromPath(path));

        // A file written before the setting existed has no field, so it gets the default.
        File.WriteAllText(path, """{"omr_engine":"homr465","audio_offset_milliseconds":55}""");
        Assert.True(AppSettingsStore.LoadTimingCorrectionFromPath(path));
        Assert.Equal(OmrEngine.Homr465, AppSettingsStore.LoadEngineFromPath(path));

        // One the user switched off stays off.
        File.WriteAllText(path, """{"omr_engine":"homr480","timing_correction":false}""");
        Assert.False(AppSettingsStore.LoadTimingCorrectionFromPath(path));
    }

    [Fact]
    public void OnlyTheHomrEnginesAreCorrected()
    {
        Assert.True(OmrPipeline.SupportsTimingCorrection(OmrEngine.Homr));
        Assert.True(OmrPipeline.SupportsTimingCorrection(OmrEngine.Homr465));
        Assert.False(OmrPipeline.SupportsTimingCorrection(OmrEngine.Zeus));
        Assert.False(OmrPipeline.SupportsTimingCorrection(OmrEngine.MusicXml));
    }

    [Fact]
    public void ShippedCorrectionIsBesideTheBridge()
    {
        string bridge = Path.Combine(AppContext.BaseDirectory, "Bridge", "bridge.py");
        Assert.Matches("^[0-9a-f]{64}$", OmrPipeline.GetTimingCorrectionSha256(bridge) ?? "");
    }

    [Fact]
    public void CorrectedAndPlainConversionsNeverShareACacheEntry()
    {
        using TemporaryDirectory temporary = new();
        string source = temporary.CreateFile("score.pdf", "pdf bytes");
        int calls = 0;
        OmrResult Pipeline(string path, OmrEngine engine, CancellationToken cancellationToken)
        {
            calls++;
            return CreateResult(calls);
        }

        SongLoadResult plain = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr, temporary.Path, Pipeline);
        SongLoadResult corrected = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr, temporary.Path, Pipeline,
            IdentityA);
        Assert.Equal(2, calls);
        Assert.NotEqual(plain.ManifestRelativePath, corrected.ManifestRelativePath);
        Assert.Contains(".timing-" + IdentityA[..12], corrected.ManifestRelativePath!);
        Assert.Equal("score", plain.DisplayName);
        Assert.EndsWith(SongCache.TimingCorrectionLabel, corrected.DisplayName);

        Assert.True(SongCache.IsCacheHitForTesting(source, OmrEngine.Homr, temporary.Path));
        Assert.True(SongCache.IsCacheHitForTesting(source, OmrEngine.Homr, temporary.Path, IdentityA));
        Assert.False(SongCache.IsCacheHitForTesting(source, OmrEngine.Homr, temporary.Path, IdentityB));
        Assert.True(SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr, temporary.Path, Pipeline,
            IdentityA).LoadedFromCache);
        Assert.Equal(2, calls);

        // The retained source is one file for both, so the PDF library shows the score once.
        Assert.Single(Directory.GetFiles(Path.Combine(temporary.Path, "songs", "pdf")));
        IReadOnlyList<CachedSongEntry> library = SongCache.GetCachedSongsForTesting(temporary.Path);
        Assert.Equal(2, library.Count);
        Assert.Single(library, entry => entry.RecentSong.DisplayName.EndsWith(SongCache.TimingCorrectionLabel));
    }

    [Fact]
    public async Task RunAsyncStartsTheCorrectionScriptOnlyForHomr()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "image");
        string bridgePath = temporary.CreateFile("bridge.py", FakeBridge("bridge"));
        temporary.CreateFile(OmrPipeline.TimingCorrectionScriptName, FakeBridge("timing"));

        OmrResult plain = await OmrPipeline.RunAsync(inputPath, OmrEngine.Homr, bridgePath,
            timeout: TimeSpan.FromSeconds(20));
        OmrResult corrected = await OmrPipeline.RunAsync(inputPath, OmrEngine.Homr, bridgePath,
            timeout: TimeSpan.FromSeconds(20), timingCorrection: true);
        OmrResult zeus = await OmrPipeline.RunAsync(inputPath, OmrEngine.Zeus, bridgePath,
            timeout: TimeSpan.FromSeconds(20), timingCorrection: true);

        Assert.Equal("bridge", plain.Notes.Single().VoiceIdentifier);
        Assert.Equal("timing", corrected.Notes.Single().VoiceIdentifier);
        Assert.Equal("bridge", zeus.Notes.Single().VoiceIdentifier);
    }

    private static string FakeBridge(string marker) => $$"""
        import json
        import sys

        engine = sys.argv[sys.argv.index("--engine") + 1]
        revisions = {"homr": "{{OmrPipeline.HomrEngineRevision}}", "zeus": "{{OmrPipeline.ZeusEngineRevision}}"}
        print(json.dumps({
            "schema_version": 2,
            "engine": engine,
            "engine_revision": revisions[engine],
            "tempo_changes": [{"start_beat": 0.0, "bpm": 120.0}],
            "notes": [{
                "pitch": "C4", "midi_pitch": 60, "start_beat": 0.0,
                "duration_beats": 1.0, "start_seconds": 0.0,
                "duration_seconds": 0.5, "part_index": 0,
                "staff_index": 0, "voice_identifier": "{{marker}}"
            }]
        }, separators=(",", ":")))
        """;

    private static OmrResult CreateResult(int pitchOffset) => new()
    {
        SchemaVersion = 2,
        Engine = OmrEngine.Homr,
        EngineRevision = OmrPipeline.HomrEngineRevision,
        TempoChanges = [new TempoChange { StartBeat = 0, Bpm = 120 }],
        Notes = [new MusicNote { Pitch = "C4", MidiPitch = 60 + pitchOffset, StartBeat = 0, DurationBeats = 1,
            StartSeconds = 0, DurationSeconds = 0.5, PartIndex = 0, StaffIndex = 0, VoiceIdentifier = "1" }]
    };
}
