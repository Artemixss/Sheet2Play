using System.Security.Cryptography;
using System.Text.Json;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class Homr480IntegrationTests
{
    [Fact]
    public void EngineIdentityIsPinnedBesideHomr465()
    {
        Assert.Equal(5, (int)OmrEngine.Homr480);
        Assert.Equal(OmrEngine.Homr480, JsonSerializer.Deserialize<OmrEngine>("\"homr480\""));
        Assert.Equal("homr480", OmrPipeline.GetEngineName(OmrEngine.Homr480));
        Assert.Equal(OmrPipeline.Homr480EngineRevision, OmrPipeline.GetEngineRevision(OmrEngine.Homr480));
        Assert.True(OmrPipeline.IsPinnedNative(OmrEngine.Homr480));
        Assert.True(OmrPipeline.IsPinnedNative(OmrEngine.Homr465));
        Assert.False(OmrPipeline.IsPinnedNative(OmrEngine.Homr));
        Assert.NotEqual(OmrPipeline.GetProfileSha256(OmrEngine.Homr465), OmrPipeline.GetProfileSha256(OmrEngine.Homr480));
        Assert.True(OmrPipeline.SupportsTimingCorrection(OmrEngine.Homr480));
    }

    [Theory]
    [InlineData("homr465-profile.json", OmrPipeline.Homr465ProfileSha256)]
    [InlineData("homr480-profile.json", OmrPipeline.Homr480ProfileSha256)]
    public void PinsMatchTheShippedProfiles(string profile, string expected)
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Bridge", profile)))
        {
            directory = directory.Parent;
        }
        Assert.NotNull(directory);
        string path = Path.Combine(directory!.FullName, "Bridge", profile);
        Assert.Equal(expected, Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path))));
    }

    [Theory]
    [InlineData(null, null)]
    [InlineData("wrong", OmrPipeline.Homr480ProfileSha256)]
    [InlineData(OmrPipeline.Homr480ModelRevision, OmrPipeline.Homr465ProfileSha256)]
    public void MissingOrWrongIdentityIsRejected(string? model, string? profile)
    {
        Assert.Throws<OmrPipelineException>(() => OmrPipeline.ValidateResult(CreateResult(model, profile), OmrEngine.Homr480));
    }

    [Fact]
    public void CacheKeepsHomr480And465ApartAndListsThe480VersionFirst()
    {
        using TemporaryDirectory temporary = new();
        string source = temporary.CreateFile("score.png", "image");
        SongLoadResult latest = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr480, temporary.Path,
            (_, _, _) => CreateResult());
        SongLoadResult secondary = SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr465, temporary.Path,
            (_, _, _) => CreateResult(OmrPipeline.Homr465ModelRevision, OmrPipeline.Homr465ProfileSha256, OmrEngine.Homr465));
        Assert.Contains(OmrPipeline.Homr480ProfileSha256, latest.ManifestRelativePath!);
        Assert.NotEqual(latest.ManifestRelativePath, secondary.ManifestRelativePath);
        Assert.True(SongCache.LoadOrCreateDetailedForTesting(source, OmrEngine.Homr480, temporary.Path,
            (_, _, _) => throw new InvalidOperationException("Unexpected recognition")).LoadedFromCache);
        Assert.Equal(new[] { OmrEngine.Homr480, OmrEngine.Homr465 },
            SongCache.GetCachedSongsForTesting(temporary.Path).Select(entry => entry.RecentSong.Engine));
    }

    [Fact]
    public void Homr480FallsBackToTheSecondaryHomr465()
    {
        Assert.Contains(OmrRecoveryAction.RetryWithHomr, OmrRecoveryPolicy.GetActions(OmrEngine.Homr480));
        Assert.Equal(OmrEngine.Homr465, OmrRecoveryPolicy.GetAlternateEngine(OmrEngine.Homr480));
        Assert.Equal("Retry HOMR 465", OmrRecoveryPolicy.GetAlternateLabel(OmrEngine.Homr480));
        Assert.Equal(OmrEngine.Homr, OmrRecoveryPolicy.GetAlternateEngine(OmrEngine.Homr465));
        Assert.Equal("Retry HOMR 426", OmrRecoveryPolicy.GetAlternateLabel(OmrEngine.Zeus));
        Assert.Equal("Retry HOMR 480", OmrRecoveryPolicy.GetSameEngineLabel(OmrEngine.Homr480));
    }

    private static OmrResult CreateResult(string? model = OmrPipeline.Homr480ModelRevision,
        string? profile = OmrPipeline.Homr480ProfileSha256, OmrEngine engine = OmrEngine.Homr480) => new()
    {
        SchemaVersion = 2,
        Engine = engine,
        EngineRevision = OmrPipeline.GetEngineRevision(engine),
        ModelRevision = model,
        RuntimeProfileSha256 = profile,
        TempoChanges = [new TempoChange { StartBeat = 0, Bpm = 120 }],
        Notes = [new MusicNote { Pitch = "C4", MidiPitch = 60, StartBeat = 0, DurationBeats = 1,
            StartSeconds = 0, DurationSeconds = 0.5, PartIndex = 0, StaffIndex = 0, VoiceIdentifier = "1" }]
    };
}
