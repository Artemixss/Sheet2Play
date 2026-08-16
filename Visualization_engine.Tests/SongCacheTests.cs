using System.Text.Json.Nodes;
using SynthesiaClone;

namespace Visualization_engine.Tests;

public sealed class SongCacheTests
{
    [Fact]
    public void SettingsDefaultToHomrAndRecoverLegacyEnginesAsHomr()
    {
        using TemporaryDirectory temporary = new();
        string settingsPath = Path.Combine(temporary.Path, "settings", "settings.json");

        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(settingsPath));
        File.WriteAllText(settingsPath, "{\"omr_engine\":\"oemer\"}");
        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(settingsPath));
        File.WriteAllText(settingsPath, "{\"omr_engine\":\"clarity\"}");
        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(settingsPath));
        Assert.Contains("\"homr\"", File.ReadAllText(settingsPath));

        File.WriteAllText(settingsPath, "{\"omr_engine\":\"smt\"}");
        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(settingsPath));
        Assert.Contains("\"homr\"", File.ReadAllText(settingsPath));

        AppSettingsStore.SaveEngineToPath(OmrEngine.Zeus, settingsPath);
        Assert.Equal(OmrEngine.Zeus, AppSettingsStore.LoadEngineFromPath(settingsPath));
        Assert.Contains("\"zeus\"", File.ReadAllText(settingsPath));

        File.WriteAllText(settingsPath, "{\"omr_engine\":\"unknown-engine\"}");
        Assert.Equal(OmrEngine.Homr, AppSettingsStore.LoadEngineFromPath(settingsPath));
        Assert.Contains("\"homr\"", File.ReadAllText(settingsPath));
    }

    [Fact]
    public void SourceChangesInvalidateHomrManifest()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("score.png", "source-v1");
        string homrPath = SongCache.GetMidiPathForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path);

        Assert.Contains(Path.Combine("midi", "homr"), homrPath);

        OmrResult result = CreateTempoResult();
        SongCache.PersistCacheForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path,
            result);
        Assert.True(SongCache.IsCacheHitForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path));

        File.AppendAllText(inputPath, "-changed");
        Assert.False(SongCache.IsCacheHitForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path));
    }

    [Fact]
    public void MidiRoundTripUsesTempoMapAndPreservesOverlappingSamePitchNotes()
    {
        using TemporaryDirectory temporary = new();
        string midiPath = Path.Combine(temporary.Path, "tempo-overlap.mid");
        OmrResult result = CreateTempoResult();

        SongCache.WriteMidiForTesting(midiPath, result);
        List<Note> notes = SongCache.ReadMidiForTesting(midiPath);

        Assert.Equal(3, notes.Count);
        Assert.All(notes, note => Assert.Equal(39, note.TargetKeyIndex));
        Note[] canonicalNotes = notes
            .OrderBy(note => note.StartTime)
            .ThenBy(note => note.Duration)
            .ToArray();
        Assert.Equal(0.0, canonicalNotes[0].StartTime, precision: 6);
        Assert.Equal(0.5, canonicalNotes[0].Duration, precision: 6);
        Assert.Equal(0.0, canonicalNotes[1].StartTime, precision: 6);
        Assert.Equal(1.5, canonicalNotes[1].Duration, precision: 6);
        Assert.Equal(0.5, canonicalNotes[2].StartTime, precision: 6);
        Assert.Equal(1.0, canonicalNotes[2].Duration, precision: 6);
    }

    [Fact]
    public void RepeatedInputUsesHomrCacheWithoutInvokingPipelineAgain()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("cached-score.pdf", "score-content");
        int invocationCount = 0;
        OmrResult Pipeline(string _, OmrEngine __)
        {
            invocationCount++;
            return CreateTempoResult();
        }

        List<Note> first = SongCache.LoadOrCreateForTesting(
            inputPath, OmrEngine.Homr, temporary.Path, Pipeline);
        List<Note> second = SongCache.LoadOrCreateForTesting(
            inputPath, OmrEngine.Homr, temporary.Path, Pipeline);

        Assert.Equal(1, invocationCount);
        Assert.Equal(first.Count, second.Count);
        Assert.Equal(first.Select(note => (note.TargetKeyIndex, note.StartTime, note.Duration)),
            second.Select(note => (note.TargetKeyIndex, note.StartTime, note.Duration)));
    }

    [Fact]
    public void RepeatedInputUseszeusCacheWithoutInvokingPythonAgain()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("cached-zeus.pdf", "score-content");
        int invocationCount = 0;
        OmrResult Pipeline(string _, OmrEngine engine)
        {
            invocationCount++;
            return CreateTempoResult(engine);
        }

        List<Note> first = SongCache.LoadOrCreateForTesting(
            inputPath, OmrEngine.Zeus, temporary.Path, Pipeline);
        List<Note> second = SongCache.LoadOrCreateForTesting(
            inputPath, OmrEngine.Zeus, temporary.Path, Pipeline);

        Assert.Equal(1, invocationCount);
        Assert.Equal(first.Count, second.Count);
        Assert.Contains(
            Path.Combine("midi", "zeus"),
            SongCache.GetMidiPathForTesting(
                inputPath,
                OmrEngine.Zeus,
                temporary.Path));
    }

    [Fact]
    public void HomrAndzeusCachesAreIsolatedAndPinzeusMetadata()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("isolated-score.pdf", "score-content");
        SongCache.PersistCacheForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path,
            CreateTempoResult(OmrEngine.Homr));
        SongCache.PersistCacheForTesting(
            inputPath,
            OmrEngine.Zeus,
            temporary.Path,
            CreateTempoResult(OmrEngine.Zeus));

        string homrPath = SongCache.GetMidiPathForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path);
        string zeusPath = SongCache.GetMidiPathForTesting(
            inputPath,
            OmrEngine.Zeus,
            temporary.Path);
        string manifestPath = $"{zeusPath}.cache.json";
        string manifestJson = File.ReadAllText(manifestPath);

        Assert.NotEqual(homrPath, zeusPath);
        Assert.True(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Homr, temporary.Path));
        Assert.True(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Zeus, temporary.Path));
        Assert.Equal(
            [OmrEngine.Homr, OmrEngine.Zeus],
            SongCache.GetCachedSongsForTesting(temporary.Path)
                .Select(entry => entry.RecentSong.Engine)
                .Order()
                .ToArray());
        Assert.Contains(OmrPipeline.ZeusModelSha256, manifestJson);
        Assert.Contains("\"input_dimensions\": \"1485x1050\"", manifestJson);
        Assert.Contains("\"decoder_fallback_policy\"", manifestJson);
        Assert.Contains("NVIDIA GeForce RTX 4050 Laptop GPU", manifestJson);

        JsonObject manifest = JsonNode.Parse(manifestJson)!.AsObject();
        manifest["model_revision"] = "outdated-model";
        File.WriteAllText(manifestPath, manifest.ToJsonString());

        Assert.False(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Zeus, temporary.Path));
        Assert.True(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Homr, temporary.Path));
    }

    [Fact]
    public void VersionedLegacyHomrManifestIsReusedAndUpgradedWithoutInference()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("legacy-homr.pdf", "legacy-score-content");
        OmrResult result = CreateTempoResult(OmrEngine.Homr);
        SongCache.PersistCacheForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path,
            result);

        string midiPath = SongCache.GetMidiPathForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path);
        string manifestPath = $"{midiPath}.cache.json";
        JsonObject manifest = JsonNode.Parse(File.ReadAllText(manifestPath))!.AsObject();
        manifest["omr_settings"] = new JsonObject
        {
            ["device"] = "cuda",
            ["beam_width"] = null,
            ["pdf_dpi"] = 300,
            ["default_tempo_bpm"] = 120,
            ["backbone_revision"] = null
        };
        File.WriteAllText(manifestPath, manifest.ToJsonString());

        int invocationCount = 0;
        List<Note> notes = SongCache.LoadOrCreateForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path,
            (_, _) =>
            {
                invocationCount++;
                return result;
            });

        Assert.Equal(0, invocationCount);
        Assert.Equal(result.Notes.Count, notes.Count);
        string upgradedManifest = File.ReadAllText(manifestPath);
        Assert.Contains("\"cuda_device\"", upgradedManifest);
        Assert.Contains("\"pdf_dpi\": 300", upgradedManifest);
        Assert.DoesNotContain("\"beam_width\"", upgradedManifest);
        Assert.DoesNotContain("\"patch_sha256\"", upgradedManifest);
        Assert.DoesNotContain("\"model_sha256\"", upgradedManifest);
    }

    [Fact]
    public void ManifestVersionTwoHashesMidiAndRejectsLaterCorruption()
    {
        using TemporaryDirectory temporary = new();
        string inputPath = temporary.CreateFile("hashed-score.pdf", "score-content");
        SongCache.PersistCacheForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path,
            CreateTempoResult());
        string midiPath = SongCache.GetMidiPathForTesting(
            inputPath,
            OmrEngine.Homr,
            temporary.Path);
        string manifest = File.ReadAllText($"{midiPath}.cache.json");

        Assert.Contains("\"cache_manifest_version\": 2", manifest);
        Assert.Contains("\"midi_sha256\"", manifest);
        Assert.True(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Homr, temporary.Path));

        using (FileStream stream = new(midiPath, FileMode.Append, FileAccess.Write))
        {
            stream.WriteByte(0);
        }
        Assert.False(SongCache.IsCacheHitForTesting(
            inputPath, OmrEngine.Homr, temporary.Path));
    }

    [Fact]
    public void RecentSongStoreKeepsNewestTenAndSupportsRemoval()
    {
        using TemporaryDirectory temporary = new();
        string storePath = Path.Combine(temporary.Path, "recent.json");
        for (int index = 0; index < 12; index++)
        {
            RecentSongsStore.Touch(new RecentSongEntry(
                $"songs/midi/homr/{index}.mid.cache.json",
                $"Song {index}",
                OmrEngine.Homr,
                DateTimeOffset.UtcNow), storePath);
        }

        IReadOnlyList<RecentSongEntry> entries = RecentSongsStore.Load(storePath);
        Assert.Equal(10, entries.Count);
        string removed = entries[0].ManifestRelativePath;
        RecentSongsStore.Remove(removed, storePath);
        Assert.DoesNotContain(
            RecentSongsStore.Load(storePath),
            entry => entry.ManifestRelativePath == removed);
    }

    [Fact]
    public void LibraryListsScoreFilesAndEveryValidatedCacheManifest()
    {
        using TemporaryDirectory temporary = new();
        string pdfDirectory = Path.Combine(temporary.Path, "songs", "pdf");
        Directory.CreateDirectory(pdfDirectory);
        string firstPdf = Path.Combine(pdfDirectory, "Alpha Score.pdf");
        string secondPdf = Path.Combine(pdfDirectory, "Beta Score.pdf");
        File.WriteAllText(firstPdf, "alpha");
        File.WriteAllText(secondPdf, "beta");

        // Scanned images are valid OMR input and must be listed alongside PDFs.
        File.WriteAllText(Path.Combine(pdfDirectory, "Gamma Scan.png"), "image");

        // Anything that is not a score format must stay out of the library.
        File.WriteAllText(Path.Combine(pdfDirectory, "notes.txt"), "not a score");

        SongCache.PersistCacheForTesting(
            firstPdf,
            OmrEngine.Homr,
            temporary.Path,
            CreateTempoResult());

        IReadOnlyList<PdfLibraryEntry> pdfs = SongCache.GetPdfLibraryForTesting(
            temporary.Path);
        IReadOnlyList<CachedSongEntry> cached = SongCache.GetCachedSongsForTesting(
            temporary.Path);

        Assert.Equal(["Alpha Score", "Beta Score", "Gamma Scan"],
            pdfs.Select(static entry => entry.DisplayName));
        CachedSongEntry song = Assert.Single(cached);
        Assert.Equal("Alpha Score", song.RecentSong.DisplayName);
        Assert.Equal(3, song.NoteCount);
        Assert.True(song.DurationSeconds > 0);
    }

    private static OmrResult CreateTempoResult(OmrEngine engine = OmrEngine.Homr)
    {
        return new OmrResult
        {
            SchemaVersion = OmrPipeline.SchemaVersion,
            Engine = engine,
            EngineRevision = OmrPipeline.GetEngineRevision(engine),
            TempoChanges =
            [
                new TempoChange { StartBeat = 0, Bpm = 60 },
                new TempoChange { StartBeat = 1, Bpm = 120 }
            ],
            Notes =
            [
                new MusicNote
                {
                    Pitch = "C4",
                    MidiPitch = 60,
                    StartBeat = 0,
                    DurationBeats = 0.5,
                    StartSeconds = 0,
                    DurationSeconds = 0.5,
                    PartIndex = 0,
                    StaffIndex = 0,
                    VoiceIdentifier = "middle"
                },
                new MusicNote
                {
                    Pitch = "C4",
                    MidiPitch = 60,
                    StartBeat = 0,
                    DurationBeats = 2,
                    StartSeconds = 0,
                    DurationSeconds = 1.5,
                    PartIndex = 0,
                    StaffIndex = 0,
                    VoiceIdentifier = "upper"
                },
                new MusicNote
                {
                    Pitch = "C4",
                    MidiPitch = 60,
                    StartBeat = 0.5,
                    DurationBeats = 1.5,
                    StartSeconds = 0.5,
                    DurationSeconds = 1.0,
                    PartIndex = 0,
                    StaffIndex = 0,
                    VoiceIdentifier = "lower"
                }
            ]
        };
    }
}
