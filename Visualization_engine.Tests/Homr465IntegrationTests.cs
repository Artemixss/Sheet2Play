using System.Text.Json;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class Homr465IntegrationTests
{
    [Fact]
    public void DirectXmlCachePersistsAndReopensWithoutRecognition()
    {
        using TemporaryDirectory temporary = new();
        string input = temporary.CreateFile("score.musicxml", "xml fixture");
        OmrResult result = new()
        {
            SchemaVersion = 2,
            Engine = OmrEngine.MusicXml,
            EngineRevision = "direct-xml",
            TempoChanges = CreateResult().TempoChanges,
            Notes = CreateResult().Notes
        };
        SongLoadResult saved = SongCache.LoadOrCreateDetailedForTesting(input, OmrEngine.MusicXml,
            temporary.Path, (_, _, _) => result);
        Assert.NotNull(saved.ManifestRelativePath);
        Assert.True(SongCache.IsCacheHitForTesting(input, OmrEngine.MusicXml, temporary.Path));
        SongLoadResult reopened = SongCache.LoadOrCreateDetailedForTesting(input, OmrEngine.MusicXml,
            temporary.Path, (_, _, _) => throw new InvalidOperationException("Unexpected recognition"));
        Assert.True(reopened.LoadedFromCache);
        Assert.Equal(saved.NoteCount, reopened.NoteCount);
    }

    [Fact]
    public void EngineValuesAndLegacySerializationRemainStable()
    {
        Assert.Equal(0, (int)OmrEngine.Homr);
        Assert.Equal(1, (int)OmrEngine.Zeus);
        Assert.Equal(2, (int)OmrEngine.MusicXml);
        Assert.Equal(3, (int)OmrEngine.DirectMidi);
        Assert.Equal(4, (int)OmrEngine.Homr465);
        Assert.Equal(OmrEngine.Homr, JsonSerializer.Deserialize<OmrEngine>("\"homr\""));
        Assert.Equal(OmrEngine.Homr465, JsonSerializer.Deserialize<OmrEngine>("\"homr465\""));
        Assert.Equal("direct-xml", OmrPipeline.GetEngineRevision(OmrEngine.MusicXml));
    }

    [Theory]
    [InlineData(null, null)]
    [InlineData("wrong", null)]
    [InlineData(OmrPipeline.Homr465ModelRevision, "wrong")]
    public void MissingOrWrongIdentityIsRejected(string? model, string? profile)
    {
        Assert.Throws<OmrPipelineException>(() => OmrPipeline.ValidateResult(CreateResult(model, profile), OmrEngine.Homr465));
    }

    [Fact]
    public void CacheSeparatesDuplicateNamesAndChangedSourceAndReusesValidatedResults()
    {
        using TemporaryDirectory temporary = new();
        Directory.CreateDirectory(Path.Combine(temporary.Path, "first"));
        Directory.CreateDirectory(Path.Combine(temporary.Path, "second"));
        string sourceA = temporary.CreateFile("first/score.png", "first image");
        string sourceB = temporary.CreateFile("second/score.png", "second image");
        int calls = 0;
        OmrResult Pipeline(string path, OmrEngine engine, CancellationToken cancellationToken)
        {
            calls++;
            return CreateResult();
        }
        SongLoadResult first = SongCache.LoadOrCreateDetailedForTesting(sourceA, OmrEngine.Homr465, temporary.Path, Pipeline);
        SongLoadResult second = SongCache.LoadOrCreateDetailedForTesting(sourceB, OmrEngine.Homr465, temporary.Path, Pipeline);
        Assert.NotEqual(first.ManifestRelativePath, second.ManifestRelativePath);
        Assert.True(SongCache.LoadOrCreateDetailedForTesting(sourceA, OmrEngine.Homr465, temporary.Path, Pipeline).LoadedFromCache);
        Assert.Equal(2, calls);
        Assert.Contains(OmrPipeline.Homr465ProfileSha256, first.ManifestRelativePath!);
        File.WriteAllText(sourceA, "changed image");
        SongLoadResult changed = SongCache.LoadOrCreateDetailedForTesting(sourceA, OmrEngine.Homr465, temporary.Path, Pipeline);
        Assert.NotEqual(first.ManifestRelativePath, changed.ManifestRelativePath);
        Assert.True(File.Exists(Path.Combine(temporary.Path, first.ManifestRelativePath!)));
        Assert.Equal(3, calls);
    }

    [Fact]
    public void CacheRejectsProfileTamperingAndNeverCommitsInvalidCandidateIdentity()
    {
        using TemporaryDirectory temporary = new();
        string source = temporary.CreateFile("score.png", "image");
        SongLoadResult saved = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr465, temporary.Path,
            (path, engine, cancellation) => CreateResult());
        string manifest = Path.Combine(temporary.Path, saved.ManifestRelativePath!);
        File.WriteAllText(manifest, File.ReadAllText(manifest).Replace(OmrPipeline.Homr465ProfileSha256, new string('0', 64)));
        Assert.False(SongCache.IsCacheHitForTesting(source, OmrEngine.Homr465, temporary.Path));
        Assert.Throws<OmrPipelineException>(() => SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr465, temporary.Path,
            (path, engine, cancellation) => CreateResult(profile: "wrong")));
        Assert.Contains(new string('0', 64), File.ReadAllText(manifest));
    }

    [Fact]
    public void LibraryPrefers465WhileRetainingTheValid426Version()
    {
        using TemporaryDirectory temporary = new();
        string source = temporary.CreateFile("score.png", "retained image");
        OmrResult candidate = CreateResult();
        OmrResult legacy = new()
        {
            SchemaVersion = 2, Engine = OmrEngine.Homr, EngineRevision = OmrPipeline.HomrEngineRevision,
            TempoChanges = candidate.TempoChanges, Notes = candidate.Notes
        };
        SongLoadResult old = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr,
            temporary.Path, (_, _, _) => legacy);
        string oldManifest = Path.Combine(temporary.Path, old.ManifestRelativePath!);
        string identity = LibraryMigrationState.Hash(oldManifest);
        SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr465, temporary.Path, (_, _, _) => candidate);
        IReadOnlyList<CachedSongEntry> entries = SongCache.GetCachedSongsForTesting(temporary.Path);
        Assert.Equal(new[] { OmrEngine.Homr465, OmrEngine.Homr }, entries.Select(entry => entry.RecentSong.Engine));
        Assert.Equal(identity, LibraryMigrationState.Hash(oldManifest));
    }

    [Fact]
    public void Saved465SelectionPreservesAudioCalibrationAndAllows426Fallback()
    {
        using TemporaryDirectory temporary = new();
        string path = temporary.CreateFile("settings.json", "{\"omr_engine\":\"homr\",\"audio_offset_milliseconds\":73}");
        AppSettingsStore.SaveEngineToPath(OmrEngine.Homr465, path);
        Assert.Equal(OmrEngine.Homr465, AppSettingsStore.LoadEngineFromPath(path));
        Assert.Equal(73, AppSettingsStore.LoadAudioOffsetFromPath(path));
        AppSettingsStore.SaveEngineToPath(OmrEngine.Homr, path);
        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(path));
        Assert.Equal(73, AppSettingsStore.LoadAudioOffsetFromPath(path));
        Assert.Contains(OmrRecoveryAction.RetryWithHomr, OmrRecoveryPolicy.GetActions(OmrEngine.Homr465));
    }

    private static OmrResult CreateResult(string? model = OmrPipeline.Homr465ModelRevision, string? profile = OmrPipeline.Homr465ProfileSha256) => new()
    {
        SchemaVersion = 2,
        Engine = OmrEngine.Homr465,
        EngineRevision = OmrPipeline.Homr465EngineRevision,
        ModelRevision = model,
        RuntimeProfileSha256 = profile,
        TempoChanges = [new TempoChange { StartBeat = 0, Bpm = 120 }],
        Notes = [new MusicNote { Pitch = "C4", MidiPitch = 60, StartBeat = 0, DurationBeats = 1,
            StartSeconds = 0, DurationSeconds = 0.5, PartIndex = 0, StaffIndex = 0, VoiceIdentifier = "1" }]
    };
}
