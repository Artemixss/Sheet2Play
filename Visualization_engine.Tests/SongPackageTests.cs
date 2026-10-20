using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using SynthesiaClone;

namespace Visualization_engine.Tests;

/// <summary>
/// Song packages: a conversion keeps its MusicXML, the app plays the interpreted performance,
/// switching the timing fix re-interprets without OMR, and anything invalid falls back safely.
/// </summary>
public sealed class SongPackageTests
{
    private static readonly JsonSerializerOptions SnakeCase = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    // --- The timeline ------------------------------------------------------------------------

    [Fact]
    public void TimelinePlacesNotesByMeasureAndTempoLikeTheBridge()
    {
        // Three 2/4 measures at the default 120: a beat is half a second.
        SongPerformance performance = SongPerformance.Parse(PerformanceJson(
            [(0, 0.0, 1.0, 60), (1, 0.5, 1.5, 62), (2, 0.0, 2.0, 64)], measures: 3));
        List<Note> notes = SongTimeline.BuildNotes(performance);
        Assert.Equal([(39, 0.0, 0.5), (41, 1.25, 0.75), (43, 2.0, 1.0)],
            notes.Select(note => (note.TargetKeyIndex, Math.Round(note.StartTime, 9), Math.Round(note.Duration, 9))));
        Assert.All(notes, note => Assert.Equal(80, note.Velocity));
    }

    [Fact]
    public void TimelineExpandsRepeatsAndATempoMarkHoldsBackAcrossThem()
    {
        // Measures 0-1 repeat; a mark of 60 in measure 1 still holds when measure 0 plays again.
        SongPerformance performance = SongPerformance.Parse(PerformanceJson(
            [(0, 0.0, 2.0, 60), (1, 0.0, 2.0, 62), (2, 0.0, 2.0, 64)], measures: 3, playOrder: [0, 1, 0, 1, 2],
            tempos: [(1, 0.0, 60.0)]));
        List<Note> notes = SongTimeline.BuildNotes(performance);
        Assert.Equal([60, 62, 60, 62, 64], notes.Select(note => note.MidiPitch));
        Assert.Equal([0.0, 1.0, 3.0, 5.0, 7.0], notes.Select(note => Math.Round(note.StartTime, 9)));
        List<Note> once = SongTimeline.BuildNotes(performance, new SongTimelineOptions(ExpandRepeats: false));
        Assert.Equal([60, 62, 64], once.Select(note => note.MidiPitch));
    }

    [Fact]
    public void GraceNotesAreLeftOutUntilTheyHaveAPlayingRule()
    {
        SongPerformance performance = SongPerformance.Parse(PerformanceJson(
            [(0, 0.0, 2.0, 60)], measures: 1, graceMidi: 72));
        Assert.Equal([60], SongTimeline.BuildNotes(performance).Select(note => note.MidiPitch));
    }

    [Fact]
    public void ParseRejectsUnknownFieldsAndOtherSchemas()
    {
        string valid = PerformanceJson([(0, 0.0, 1.0, 60)], measures: 1);
        Assert.Single(SongPerformance.Parse(valid).Notes);
        Assert.Throws<InvalidDataException>(() => SongPerformance.Parse(
            valid.Replace("\"schema_version\":3,", "\"unknown_field\":1,\"schema_version\":3,")));
        Assert.Throws<InvalidDataException>(() => SongPerformance.Parse(
            valid.Replace("\"schema_version\":3,", "\"schema_version\":2,")));
    }

    [Fact]
    public void ParseRejectsAPlayOrderOutsideTheScore()
    {
        Assert.Throws<InvalidDataException>(() => SongPerformance.Parse(PerformanceJson(
            [(0, 0.0, 1.0, 60)], measures: 1, playOrder: [0, 1])));
    }

    // --- Conversion and reopening ------------------------------------------------------------

    [Fact]
    public void AConversionKeepsItsPackageAndReopensWithoutOmr()
    {
        using Library library = new();
        SongLoadResult first = library.Load();
        Assert.Equal(1, library.OmrRuns);
        Assert.False(first.LoadedFromCache);
        Assert.Equal("score", first.DisplayName);
        Assert.EndsWith("interpretation.json", first.ManifestRelativePath);
        Assert.Contains(Path.Combine("songs", "scores", "homr480"), first.ManifestRelativePath);
        Assert.Equal([60, 62, 64], first.Notes.Select(note => note.MidiPitch));

        SongLoadResult second = library.Load();
        Assert.Equal(1, library.OmrRuns);
        Assert.Equal(0, library.Interpretations);
        Assert.True(second.LoadedFromCache);
        Assert.Equal(first.ManifestRelativePath, second.ManifestRelativePath);
        Assert.True(SongCache.IsPackageHitForTesting(library.Source, OmrEngine.Homr480, library.Root));
        // No MIDI cache is written beside a package.
        Assert.False(Directory.Exists(Path.Combine(library.Root, "songs", "midi", "homr480")));
    }

    [Fact]
    public void SwitchingTheTimingFixReinterpretsTheStoredPagesWithoutOmr()
    {
        using Library library = new();
        SongLoadResult plain = library.Load();
        SongLoadResult corrected = library.Load(timing: true);
        Assert.Equal(1, library.OmrRuns);
        Assert.Equal(1, library.Interpretations);
        Assert.EndsWith(SongCache.TimingCorrectionLabel, corrected.DisplayName);
        Assert.NotEqual(plain.ManifestRelativePath, corrected.ManifestRelativePath);

        // Both interpretations stay; switching back loads the plain one as it is.
        SongLoadResult again = library.Load();
        Assert.Equal(1, library.Interpretations);
        Assert.Equal(plain.ManifestRelativePath, again.ManifestRelativePath);
        Assert.Equal(2, SongCache.GetCachedSongsForTesting(library.Root, library.Bridge, library.Interpret).Count);
    }

    [Fact]
    public void ANewInterpreterReinterpretsOnOpenAndReplacesTheOldInterpretation()
    {
        using Library library = new();
        SongLoadResult before = library.Load();
        File.AppendAllText(Path.Combine(library.Bridge, OmrPipeline.SongModelScriptName), "# changed\n");

        // The library lists the song from its old interpretation and never runs the interpreter.
        CachedSongEntry listed = Assert.Single(SongCache.GetCachedSongsForTesting(library.Root, library.Bridge, Refuse));
        Assert.Equal(before.ManifestRelativePath, listed.RecentSong.ManifestRelativePath);

        Assert.True(SongCache.TryLoadRecentForTesting(listed.RecentSong, library.Root, library.Bridge, library.Interpret,
            allowInterpretation: true, out SongLoadResult? opened));
        Assert.Equal(1, library.Interpretations);
        Assert.Equal(1, library.OmrRuns);
        Assert.NotEqual(before.ManifestRelativePath, opened!.ManifestRelativePath);
        Assert.False(File.Exists(Path.Combine(library.Root, before.ManifestRelativePath!)));
        Assert.Single(Directory.GetDirectories(Path.Combine(library.PackageDirectory, "derived")));
    }

    [Fact]
    public void AChangedPageInvalidatesThePackageAndTheSongIsConvertedAgain()
    {
        using Library library = new();
        library.Load();
        File.AppendAllText(Directory.GetFiles(Path.Combine(library.PackageDirectory, "pages")).Single(), "<!-- edited -->");
        Assert.False(SongCache.IsPackageHitForTesting(library.Source, OmrEngine.Homr480, library.Root));
        library.Load();
        Assert.Equal(2, library.OmrRuns);
    }

    [Fact]
    public void ACorruptPerformanceIsReinterpretedFromThePages()
    {
        using Library library = new();
        SongLoadResult first = library.Load();
        string performance = Path.Combine(library.Root, Path.GetDirectoryName(first.ManifestRelativePath!)!, "performance.json");
        File.WriteAllText(performance, "{\"schema_version\":3}");
        SongLoadResult second = library.Load();
        Assert.Equal(1, library.OmrRuns);
        Assert.Equal(1, library.Interpretations);
        Assert.Equal(first.Notes.Count, second.Notes.Count);
    }

    [Fact]
    public void ARunThatLeavesNoPackageFallsBackToTheMidiCache()
    {
        using Library library = new() { WritePackage = false };
        SongLoadResult result = library.Load();
        Assert.EndsWith(".mid.cache.json", result.ManifestRelativePath);
        Assert.Equal(3, result.NoteCount);
        Assert.True(library.Load().LoadedFromCache);
        Assert.Equal(1, library.OmrRuns);
    }

    [Fact]
    public void AnInterpreterFailureKeepsThePagesAndPlaysFromTheMidiCache()
    {
        using Library library = new() { WriteInterpretation = false, InterpreterFails = true };
        SongLoadResult result = library.Load();
        Assert.EndsWith(".mid.cache.json", result.ManifestRelativePath);
        Assert.True(File.Exists(Path.Combine(library.PackageDirectory, "song.json")));
        Assert.Empty(Directory.Exists(Path.Combine(library.PackageDirectory, "derived"))
            ? Directory.GetDirectories(Path.Combine(library.PackageDirectory, "derived"))
            : []);

        // Next time the interpreter works again: the stored pages play, still without OMR.
        library.InterpreterFails = false;
        SongLoadResult recovered = library.Load();
        Assert.Equal(1, library.OmrRuns);
        Assert.EndsWith("interpretation.json", recovered.ManifestRelativePath);
    }

    [Fact]
    public void TheLibraryListsAPackageOnceAndHidesTheMidiCacheItSupersedes()
    {
        using Library library = new() { WritePackage = false };
        library.Load();
        Assert.Single(SongCache.GetCachedSongsForTesting(library.Root, library.Bridge, Refuse));

        library.WritePackage = true;
        library.Load(forceReprocess: true);
        CachedSongEntry listed = Assert.Single(SongCache.GetCachedSongsForTesting(library.Root, library.Bridge, Refuse));
        Assert.EndsWith("interpretation.json", listed.RecentSong.ManifestRelativePath);
        Assert.Equal(3, listed.NoteCount);
        Assert.Equal("score", listed.RecentSong.DisplayName);
    }

    // --- The real interpreter (skipped when the HOMR runtime is not installed) ---------------

    [Fact]
    public void TheInterpretationKeyMatchesTheInterpreters()
    {
        string bridge = OmrPipeline.DefaultBridgeDirectory;
        string python = OmrPipeline.ResolveEnginePythonExecutable(Path.Combine(bridge, "bridge.py"), OmrEngine.MusicXml);
        if (!File.Exists(python))
        {
            return;
        }
        foreach (bool timing in new[] { false, true })
        {
            string printed = RunPython(python, bridge,
                $"import song_model; print(song_model.interpretation_key({(timing ? "True" : "False")}))");
            Assert.Equal(SongInterpreter.InterpretationKey(bridge, timing), printed.Trim());
        }
    }

    [Fact]
    public void AnImportedScoreConvertsThroughTheRealBridgeAndPlaysItsRepeat()
    {
        string bridge = OmrPipeline.DefaultBridgeDirectory;
        string python = OmrPipeline.ResolveEnginePythonExecutable(Path.Combine(bridge, "bridge.py"), OmrEngine.MusicXml);
        if (!File.Exists(python))
        {
            return;
        }
        using TemporaryDirectory temporary = new();
        string source = temporary.CreateFile("repeat.musicxml", RepeatScore);
        SongLoadResult result = SongCache.LoadOrCreatePackageForTesting(source, OmrEngine.MusicXml, temporary.Path, bridge,
            (path, engine, output, timing, token) => OmrPipeline.Run(path, engine, cancellationToken: token,
                timingCorrection: timing, songOutputDirectory: output, timeout: TimeSpan.FromMinutes(5)),
            (engine, sources, imported, timing, output, token) =>
                SongInterpreter.Run(bridge, engine, sources, imported, timing, output, token));
        // 2/4 at the default 120: measures 1-2 repeat, so five half notes a second apart.
        Assert.Equal([60, 62, 60, 62, 64], result.Notes.Select(note => note.MidiPitch));
        Assert.Equal([0.0, 1.0, 2.0, 3.0, 4.0], result.Notes.Select(note => Math.Round(note.StartTime, 6)));
        string package = Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(
            Path.Combine(temporary.Path, result.ManifestRelativePath!))!)!)!;
        Assert.Equal(File.ReadAllBytes(source), File.ReadAllBytes(Path.Combine(package, "source.musicxml")));
    }

    private const string RepeatScore = """
        <?xml version="1.0" encoding="UTF-8"?>
        <score-partwise version="4.0">
          <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
          <part id="P1">
            <measure number="1"><barline location="left"><repeat direction="forward"/></barline>
              <attributes><divisions>1</divisions><time><beats>2</beats><beat-type>4</beat-type></time>
                <clef><sign>G</sign><line>2</line></clef></attributes>
              <note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
            </measure>
            <measure number="2">
              <note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
              <barline location="right"><repeat direction="backward"/></barline>
            </measure>
            <measure number="3">
              <note><pitch><step>E</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
            </measure>
          </part>
        </score-partwise>
        """;

    private static string RunPython(string python, string workingDirectory, string code)
    {
        ProcessStartInfo start = new(python) { WorkingDirectory = workingDirectory, RedirectStandardOutput = true,
            RedirectStandardError = true, UseShellExecute = false };
        start.ArgumentList.Add("-c");
        start.ArgumentList.Add(code);
        using Process process = Process.Start(start)!;
        string output = process.StandardOutput.ReadToEnd();
        string errors = process.StandardError.ReadToEnd();
        process.WaitForExit();
        Assert.True(process.ExitCode == 0, errors);
        return output;
    }

    // --- Helpers -----------------------------------------------------------------------------

    private static void Refuse(OmrEngine engine, IReadOnlyList<string> sources, bool imported, bool timing, string output,
        CancellationToken token) => throw new InvalidOperationException("Listing must not run the interpreter.");

    /// <summary>A performance document as the interpreter writes it: 2/4 measures of two beats.</summary>
    private static string PerformanceJson(IEnumerable<(int Measure, double Offset, double Duration, int Midi)> notes,
        int measures, int[]? playOrder = null, (int Measure, double Offset, double Bpm)[]? tempos = null,
        bool timing = false, int? graceMidi = null)
    {
        List<object> noteRows = notes.Select(note => (object)new
        {
            pitch = "X", midi = note.Midi, measure = note.Measure, offset = note.Offset, duration = note.Duration,
            part = 0, staff = 0, voice = "1", grace = false, grace_slash = false, tied = false,
            articulations = Array.Empty<string>(), slurs = Array.Empty<string>()
        }).ToList();
        if (graceMidi is int grace)
        {
            noteRows.Add(new
            {
                pitch = "X", midi = grace, measure = 0, offset = 0.0, duration = 0.0, part = 0, staff = 0, voice = "1",
                grace = true, grace_slash = true, tied = false, articulations = Array.Empty<string>(),
                slurs = Array.Empty<string>()
            });
        }
        var document = new
        {
            schema_version = 3,
            kind = "omr-pages",
            sources = new[] { new { name = "page-0001.musicxml", sha256 = new string('0', 64) } },
            timing_correction = timing,
            parts = new[] { new { index = 0, staves = 1, name = "Piano" } },
            pages = new[] { new { index = 0, name = "page-0001.musicxml", first_measure = 0, measures, start_beat = 0.0,
                decoded_beats = 2.0 * measures, advance_beats = 2.0 * measures, timing = "off" } },
            measures = Enumerable.Range(0, measures).Select(index => new
            {
                index, page = 0, number = (index + 1).ToString(), start_beat = 2.0 * index, length_beats = 2.0,
                bar_beats = 2.0, time_signature = new[] { 2, 4 }, pickup = false, repeat_start = false, repeat_end = 0,
                ending = (int[]?)null, ending_stop = false, jumps = (object?)null
            }),
            play_order = playOrder ?? Enumerable.Range(0, measures).ToArray(),
            notes = noteRows,
            pedals = Array.Empty<object>(),
            dynamics = Array.Empty<object>(),
            wedges = Array.Empty<object>(),
            tempos = (tempos ?? []).Select(tempo => new
            {
                measure = tempo.Measure, offset = tempo.Offset, part = 0, staff = 0, beat_unit = "quarter", dots = 0,
                per_minute = tempo.Bpm, quarter_bpm = tempo.Bpm, source = "metronome"
            }),
            features = new { notes = noteRows.Count },
            warnings = Array.Empty<string>()
        };
        return JsonSerializer.Serialize(document);
    }

    [Fact]
    public void AFileMovedAwayWhileItIsRecognisedStillBecomesALibrarySong()
    {
        // Browse to a PDF outside the library, then cut it elsewhere while the model runs: the song
        // used to play once from memory as MIDI (legacy), with no package and no MIDI cache.
        using Library library = new();
        library.DuringRecognition = () => File.Delete(library.Source);

        SongLoadResult result = library.Load(timing: true);

        string kept = Path.Combine(library.Root, "songs", "pdf", "score.pdf");
        Assert.Equal(kept, library.RecognisedPath);
        Assert.True(File.Exists(kept));
        Assert.NotNull(result.Performance);
        Assert.True(result.Performance!.TimingCorrection);
        Assert.Single(Directory.GetDirectories(Path.Combine(library.Root, "songs", "scores", "homr480")));
    }

    /// <summary>
    /// A library folder, a stand-in bridge folder and stand-ins for the song entry and the
    /// interpreter that write what the real ones write.
    /// </summary>
    private sealed class Library : IDisposable
    {
        private readonly TemporaryDirectory temporary = new();

        public Library()
        {
            Directory.CreateDirectory(Bridge);
            File.WriteAllText(Path.Combine(Bridge, OmrPipeline.SongModelScriptName), "# interpreter\n");
            File.WriteAllText(Path.Combine(Bridge, OmrPipeline.TimingCorrectionScriptName), "# timing fix\n");
            Source = temporary.CreateFile("score.pdf", "pdf bytes");
        }

        public string Root => Path.Combine(temporary.Path, "library");
        public string Bridge => Path.Combine(temporary.Path, "bridge");
        public string Source { get; }
        public bool WritePackage { get; set; } = true;
        public bool WriteInterpretation { get; set; } = true;
        public bool InterpreterFails { get; set; }
        public int OmrRuns { get; private set; }
        public int Interpretations { get; private set; }

        /// <summary>Runs while the stand-in recognition does, as a user moving the file would.</summary>
        public Action? DuringRecognition { get; set; }

        /// <summary>The file the stand-in recognition was asked to read.</summary>
        public string? RecognisedPath { get; private set; }

        public string PackageDirectory => Directory.GetDirectories(Path.Combine(Root, "songs", "scores", "homr480")).Single();

        public SongLoadResult Load(bool timing = false, bool forceReprocess = false) =>
            SongCache.LoadOrCreatePackageForTesting(Source, OmrEngine.Homr480, Root, Bridge, Pipeline, Interpret,
                timing, forceReprocess);

        private OmrResult Pipeline(string path, OmrEngine engine, string output, bool timing, CancellationToken token)
        {
            OmrRuns++;
            RecognisedPath = path;
            DuringRecognition?.Invoke();
            if (WritePackage)
            {
                string staging = output + ".staging";
                Directory.CreateDirectory(Path.Combine(staging, "pages"));
                string page = Path.Combine(staging, "pages", "page-0001.musicxml");
                File.WriteAllText(page, "<score-partwise/>");
                File.WriteAllText(Path.Combine(staging, "recognition.json"), JsonSerializer.Serialize(new
                {
                    package_schema_version = 1, kind = "omr-pages", engine = OmrPipeline.GetEngineName(engine),
                    source_name = Path.GetFileName(path), source_sha256 = Sha256(path),
                    song_entry_sha256 = new string('1', 64),
                    files = new[] { new { name = "pages/page-0001.musicxml", sha256 = Sha256(page) } },
                    created_utc = "2026-10-19T00:00:00+00:00"
                }));
                if (WriteInterpretation)
                {
                    WriteDerived(Path.Combine(staging, "derived", SongInterpreter.InterpretationKey(Bridge, timing)), timing);
                }
                if (Directory.Exists(output))
                {
                    Directory.Delete(output, recursive: true);
                }
                Directory.Move(staging, output);
            }
            return BridgeResult(engine);
        }

        public void Interpret(OmrEngine engine, IReadOnlyList<string> sources, bool imported, bool timing, string output,
            CancellationToken token)
        {
            Interpretations++;
            if (InterpreterFails)
            {
                Directory.CreateDirectory(output);
                throw new OmrPipelineException("interpreter failed", errorCode: "NORMALIZATION_FAILED", stage: "interpretation");
            }
            Assert.Single(sources);
            WriteDerived(output, timing);
        }

        private static void WriteDerived(string directory, bool timing)
        {
            Directory.CreateDirectory(directory);
            File.WriteAllText(Path.Combine(directory, "performance.json"), PerformanceJson(
                [(0, 0.0, 1.0, 60), (1, 0.0, 1.0, 62), (2, 0.0, 1.0, 64)], measures: 3, timing: timing));
            File.WriteAllText(Path.Combine(directory, "score.musicxml"), "<score-partwise/>");
        }

        private static OmrResult BridgeResult(OmrEngine engine) => new()
        {
            SchemaVersion = OmrPipeline.SchemaVersion,
            Engine = engine,
            EngineRevision = OmrPipeline.GetEngineRevision(engine),
            ModelRevision = OmrPipeline.GetModelRevision(engine),
            RuntimeProfileSha256 = OmrPipeline.GetProfileSha256(engine),
            TempoChanges = [new TempoChange { StartBeat = 0, Bpm = 120 }],
            Notes = new[] { 60, 62, 64 }.Select((midi, index) => new MusicNote
            {
                Pitch = "X", MidiPitch = midi, StartBeat = 2 * index, DurationBeats = 1, StartSeconds = index,
                DurationSeconds = 0.5, PartIndex = 0, StaffIndex = 0, VoiceIdentifier = "1"
            }).ToList()
        };

        private static string Sha256(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

        public void Dispose() => temporary.Dispose();
    }
}
