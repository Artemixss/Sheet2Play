using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using VisualNote = SynthesiaClone.Note;

namespace SynthesiaClone;

/// <summary>
/// Song packages: a conversion keeps the MusicXML it read, and the app plays a performance
/// interpreted from it (<c>plans/2026-10-19-musicxml-songs.md</c>, Phase 2).
/// </summary>
/// <remarks>
/// One package per source and engine, in <c>songs/scores/&lt;engine&gt;/&lt;source-sha&gt;[-&lt;profile-sha&gt;]/</c>:
/// <list type="bullet">
/// <item><c>recognition.json</c> and <c>pages/</c> (or <c>source.*</c> for an import), written by
/// <c>song_entry.py</c>: the OMR output, byte for byte.</item>
/// <item><c>song.json</c>: this app's manifest of what produced it. Only an OMR run replaces it.</item>
/// <item><c>derived/&lt;interpretation key&gt;/</c>: <c>performance.json</c>, the combined
/// <c>score.musicxml</c> and <c>interpretation.json</c>. The key hashes the interpreter and, when on,
/// the timing fix, so turning the fix on or off, or shipping a new interpreter, re-interprets the
/// stored pages in seconds and never runs OMR again.</item>
/// </list>
/// Anything that fails to produce a valid package falls back to the MIDI cache, so a packaging
/// fault costs the new model, never the conversion. MIDI caches written before packages existed
/// stay readable as they are.
/// </remarks>
public static partial class SongCache
{
    private const int PackageManifestVersion = 1;
    private const string ScoresFolderName = "scores";
    private const string PackageManifestName = "song.json";
    private const string RecognitionName = "recognition.json";
    private const string InterpretationManifestName = "interpretation.json";
    private const string PerformanceName = "performance.json";
    private const string CombinedScoreName = "score.musicxml";

    /// <summary>Runs OMR and writes the song package to <c>songOutputDirectory</c>.</summary>
    internal delegate OmrResult SongPipeline(
        string sourcePath, OmrEngine engine, string songOutputDirectory, bool timingCorrection,
        CancellationToken cancellationToken);

    /// <summary>Interprets stored MusicXML into a directory, without OMR.</summary>
    internal delegate void SongInterpretation(
        OmrEngine engine, IReadOnlyList<string> sources, bool imported, bool timingCorrection, string outputDirectory,
        CancellationToken cancellationToken);

    private static readonly SongTimelineOptions PlaybackTimeline = new();

    private sealed record PackageContext(
        string ApplicationDirectory,
        string BridgeDirectory,
        SongInterpretation Interpret);

    private sealed record PackagePaths(string Directory)
    {
        public string ManifestPath => Path.Combine(Directory, PackageManifestName);
        public string RecognitionPath => Path.Combine(Directory, RecognitionName);
        public string DerivedRoot => Path.Combine(Directory, "derived");
        public string Derived(string key) => Path.Combine(DerivedRoot, key);
    }

    private sealed record PackageManifest(
        int PackageManifestVersion,
        string SourceSha256,
        OmrEngine Engine,
        string EngineRevision,
        string ModelRevision,
        int BridgeSchemaVersion,
        OmrSettings OmrSettings,
        string RecognitionSha256,
        string DisplayName,
        DateTimeOffset CreatedUtc,
        string? RuntimeProfileSha256 = null);

    private sealed record InterpretationManifest(
        string InterpretationKey,
        bool TimingCorrection,
        string PerformanceSha256,
        string ScoreSha256,
        int NoteCount,
        double DurationSeconds,
        DateTimeOffset CreatedUtc);

    private sealed record RecognitionFile(string Name, string Sha256);

    private sealed record Recognition(
        int PackageSchemaVersion,
        string Kind,
        string Engine,
        string SourceName,
        string SourceSha256,
        string SongEntrySha256,
        IReadOnlyList<RecognitionFile> Files,
        string CreatedUtc);

    /// <summary>A package whose recognition checked out: its manifest and its MusicXML files.</summary>
    private sealed record ValidPackage(PackagePaths Paths, PackageManifest Manifest, IReadOnlyList<string> Sources,
        bool Imported);

    private static PackageContext DefaultPackageContext(string applicationDirectory) =>
        new(applicationDirectory, OmrPipeline.DefaultBridgeDirectory,
            (engine, sources, imported, timing, output, token) => SongInterpreter.Run(
                OmrPipeline.DefaultBridgeDirectory, engine, sources, imported, timing, output, token));

    private static PackagePaths CreatePackagePaths(OmrEngine engine, string applicationDirectory, string sourceHash)
    {
        string name = OmrPipeline.IsPinnedNative(engine)
            ? $"{sourceHash}-{OmrPipeline.GetProfileSha256(engine)}"
            : sourceHash;
        return new PackagePaths(Path.Combine(applicationDirectory, "songs", ScoresFolderName,
            OmrPipeline.GetEngineName(engine), name));
    }

    private static bool AppliesTimingCorrection(OmrEngine engine, bool timingCorrection) =>
        timingCorrection && OmrPipeline.SupportsTimingCorrection(engine);

    // --- Loading -------------------------------------------------------------------------------

    private static SongLoadResult LoadOrCreatePackageCore(
        string inputPath,
        OmrEngine engine,
        PackageContext context,
        SongPipeline pipeline,
        CancellationToken cancellationToken,
        IProgress<OmrProgress>? progress,
        bool bypassKnownFailure,
        bool forceReprocess,
        bool timingCorrection)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string sourcePath = ValidateInputPath(inputPath);
        string sourceHash = ComputeSha256(sourcePath);
        bool timing = AppliesTimingCorrection(engine, timingCorrection);
        // The MIDI cache stays the fallback, keyed as it always was.
        string? timingIdentity = ResolveTimingIdentity(engine, timing);
        CachePaths cachePaths = CreateCachePaths(sourcePath, engine, context.ApplicationDirectory, sourceHash, timingIdentity);
        PackagePaths package = CreatePackagePaths(engine, context.ApplicationDirectory, sourceHash);

        ReportProgress(progress, engine, OmrProgressStages.CacheLookup, OmrProgressStatuses.Started,
            forceReprocess ? "Ignoring song cache (re-run requested)" : "Checking song cache");
        if (forceReprocess)
        {
            LogPackage(engine, sourceHash, "forced_rerun", package.Directory);
        }
        else
        {
            SongLoadResult? stored = TryLoadPackage(sourcePath, sourceHash, engine, context, timing,
                allowInterpretation: true, progress, cancellationToken);
            if (stored is not null)
            {
                ReportProgress(progress, engine, OmrProgressStages.Complete, OmrProgressStatuses.Completed,
                    "Loaded the stored song");
                return stored;
            }
            if (TryReadCache(sourceHash, engine, cachePaths, out List<VisualNote>? cachedNotes, timingIdentity))
            {
                Console.Error.WriteLine(
                    $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} " +
                    $"source_sha256={sourceHash} decision=hit kind=midi path=\"{cachePaths.MidiPath}\"");
                ReportProgress(progress, engine, OmrProgressStages.Complete, OmrProgressStatuses.Completed,
                    "Loaded validated MIDI cache");
                return CreateLoadResult(cachedNotes, sourcePath, engine, loadedFromCache: true, cachePaths,
                    context.ApplicationDirectory, timingIdentity);
            }
        }

        ReportProgress(progress, engine, OmrProgressStages.CacheLookup, OmrProgressStatuses.Completed,
            "Cache miss; starting OMR");
        LogPackage(engine, sourceHash, "miss", sourcePath);
        if (!bypassKnownFailure &&
            OmrFailureStore.TryGet(sourceHash, engine, out OmrFailureEntry? knownFailure) &&
            knownFailure is not null)
        {
            ReportProgress(progress, engine, OmrProgressStages.KnownFailure, OmrProgressStatuses.Completed,
                $"Known deterministic failure on page {knownFailure.Page?.ToString() ?? "?"}");
            throw new KnownOmrFailureException(knownFailure);
        }

        Directory.CreateDirectory(Path.GetDirectoryName(package.Directory)!);
        OmrResult result;
        try
        {
            result = pipeline(sourcePath, engine, package.Directory, timing, cancellationToken);
        }
        catch (OmrPipelineException exception)
        {
            OmrFailureStore.Remember(sourceHash, engine, exception);
            throw;
        }
        cancellationToken.ThrowIfCancellationRequested();
        OmrFailureStore.Remove(sourceHash, engine);
        if (OmrPipeline.IsPinnedNative(engine))
        {
            OmrPipeline.ValidateResult(result, engine);
        }

        try
        {
            SongLoadResult? packaged = CompletePackage(sourcePath, sourceHash, engine, context, package, result, timing,
                progress, cancellationToken);
            if (packaged is not null)
            {
                // Just converted: the player's CACHE badge must not show.
                packaged = packaged with { LoadedFromCache = false };
                CrossCheck(packaged, result, engine, sourceHash, context.ApplicationDirectory);
                RetainSource(sourcePath, engine, context.ApplicationDirectory);
                ReportProgress(progress, engine, OmrProgressStages.Complete, OmrProgressStatuses.Completed,
                    "Song is ready");
                return packaged;
            }
            LogPackage(engine, sourceHash, "package_missing", package.Directory);
        }
        catch (Exception exception) when (IsPackageFault(exception))
        {
            Console.Error.WriteLine(
                $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} source_sha256={sourceHash} " +
                $"decision=package_failed fallback=midi error=\"{exception.Message}\"");
        }
        return CompleteLegacyConversion(sourcePath, sourceHash, engine, cachePaths, result, timingIdentity,
            context.ApplicationDirectory, progress);
    }

    /// <summary>
    /// The stored song for this source, re-interpreted first when its interpretation is missing
    /// or out of date and <paramref name="allowInterpretation"/> permits; null when there is no
    /// valid package or it cannot be interpreted.
    /// </summary>
    private static SongLoadResult? TryLoadPackage(string sourcePath, string sourceHash, OmrEngine engine,
        PackageContext context, bool timing, bool allowInterpretation, IProgress<OmrProgress>? progress,
        CancellationToken cancellationToken)
    {
        PackagePaths paths = CreatePackagePaths(engine, context.ApplicationDirectory, sourceHash);
        ValidPackage? package = TryReadPackage(paths, engine, sourceHash);
        if (package is null)
        {
            return null;
        }
        try
        {
            return LoadInterpretation(package, context, timing, allowInterpretation, progress, cancellationToken);
        }
        catch (Exception exception) when (IsPackageFault(exception))
        {
            Console.Error.WriteLine(
                $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} source_sha256={sourceHash} " +
                $"decision=interpretation_failed error=\"{exception.Message}\"");
            return null;
        }
    }

    private static SongLoadResult? LoadInterpretation(ValidPackage package, PackageContext context, bool timing,
        bool allowInterpretation, IProgress<OmrProgress>? progress, CancellationToken cancellationToken)
    {
        OmrEngine engine = package.Manifest.Engine;
        string key = SongInterpreter.InterpretationKey(context.BridgeDirectory, timing);
        string derived = package.Paths.Derived(key);
        if (TryReadInterpretation(derived, key, timing, out SongPerformance? performance, out List<VisualNote>? notes))
        {
            LogPackage(engine, package.Manifest.SourceSha256, "hit", derived);
            return PackageResult(package, notes!, performance!, timing, derived, context.ApplicationDirectory);
        }
        if (!allowInterpretation)
        {
            return null;
        }

        ReportProgress(progress, engine, OmrProgressStages.Normalization, OmrProgressStatuses.Started,
            "Reading the stored score");
        Stopwatch elapsed = Stopwatch.StartNew();
        string staging = derived + $".{Guid.NewGuid():N}.tmp";
        try
        {
            context.Interpret(engine, package.Sources, package.Imported, timing, staging, cancellationToken);
            (notes, performance) = WriteInterpretation(staging, key, timing);
            ReplaceDirectory(staging, derived);
        }
        finally
        {
            DeleteDirectory(staging);
        }
        RemoveStaleInterpretations(package.Paths, key, timing);
        Console.Error.WriteLine(
            $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} source_sha256={package.Manifest.SourceSha256} " +
            $"decision=reinterpret omr=false seconds={elapsed.Elapsed.TotalSeconds:F2} path=\"{derived}\"");
        ReportProgress(progress, engine, OmrProgressStages.Normalization, OmrProgressStatuses.Completed,
            "Stored score read");
        return PackageResult(package, notes, performance, timing, derived, context.ApplicationDirectory);
    }

    private static SongLoadResult PackageResult(ValidPackage package, List<VisualNote> notes,
        SongPerformance performance, bool timing, string derived, string applicationDirectory) =>
        new(notes,
            package.Manifest.DisplayName + (timing ? TimingCorrectionLabel : ""),
            package.Manifest.Engine,
            LoadedFromCache: true,
            Path.GetRelativePath(applicationDirectory, Path.Combine(derived, InterpretationManifestName)),
            performance);

    // --- Conversion ----------------------------------------------------------------------------

    /// <summary>
    /// Records the package the song entry just wrote, interprets it if the entry could not, and
    /// loads it. Null when the run left no package.
    /// </summary>
    private static SongLoadResult? CompletePackage(string sourcePath, string sourceHash, OmrEngine engine,
        PackageContext context, PackagePaths paths, OmrResult result, bool timing, IProgress<OmrProgress>? progress,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(paths.RecognitionPath))
        {
            return null;
        }
        Recognition recognition = ReadJson<Recognition>(paths.RecognitionPath);
        if (recognition.Engine != OmrPipeline.GetEngineName(engine) || recognition.SourceSha256 != sourceHash)
        {
            throw new InvalidDataException("The song package records a different source or engine.");
        }
        PackageManifest manifest = new(
            PackageManifestVersion,
            sourceHash,
            engine,
            result.EngineRevision,
            OmrPipeline.GetModelRevision(engine),
            result.SchemaVersion,
            GetOmrSettings(engine),
            ComputeSha256(paths.RecognitionPath),
            Path.GetFileNameWithoutExtension(sourcePath),
            DateTimeOffset.UtcNow,
            result.RuntimeProfileSha256);
        WriteJsonAtomic(paths.ManifestPath, manifest);
        ValidPackage package = TryReadPackage(paths, engine, sourceHash)
            ?? throw new InvalidDataException("The song package did not validate after it was written.");

        string key = SongInterpreter.InterpretationKey(context.BridgeDirectory, timing);
        string derived = paths.Derived(key);
        if (Directory.Exists(derived) && !File.Exists(Path.Combine(derived, InterpretationManifestName)))
        {
            // The song entry interpreted the pages it kept; record that interpretation.
            (List<VisualNote> notes, SongPerformance performance) = WriteInterpretation(derived, key, timing);
            LogPackage(engine, sourceHash, "saved", derived);
            return PackageResult(package, notes, performance, timing, derived, context.ApplicationDirectory);
        }
        return LoadInterpretation(package, context, timing, allowInterpretation: true, progress, cancellationToken);
    }

    /// <summary>
    /// Logs how the new timeline compares with the bridge's own notes for the same run. A score
    /// without repeats must agree note for note; one with repeats differs by design.
    /// </summary>
    private static void CrossCheck(SongLoadResult packaged, OmrResult result, OmrEngine engine, string sourceHash,
        string applicationDirectory)
    {
        try
        {
            SongPerformance performance = SongPerformance.Parse(File.ReadAllText(Path.Combine(
                applicationDirectory, Path.GetDirectoryName(packaged.ManifestRelativePath!)!, PerformanceName)));
            string prefix = $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} source_sha256={sourceHash} crosscheck";
            if (!performance.PlayOrder.SequenceEqual(Enumerable.Range(0, performance.Measures.Count)))
            {
                Console.Error.WriteLine($"{prefix} skipped=repeats played_measures={performance.PlayOrder.Count} " +
                                        $"measures={performance.Measures.Count}");
                return;
            }
            VisualNote[] bridge = Canonical(MapOmrNotes(result.Notes));
            VisualNote[] model = Canonical(packaged.Notes);
            double worst = 0;
            bool keysMatch = bridge.Length == model.Length;
            for (int index = 0; keysMatch && index < bridge.Length; index++)
            {
                keysMatch = bridge[index].TargetKeyIndex == model[index].TargetKeyIndex;
                worst = Math.Max(worst, Math.Max(Math.Abs(bridge[index].StartTime - model[index].StartTime),
                    Math.Abs(bridge[index].EndTime - model[index].EndTime)));
            }
            Console.Error.WriteLine($"{prefix} bridge_notes={bridge.Length} model_notes={model.Length} " +
                                    $"keys_match={keysMatch} max_difference_ms={(keysMatch ? worst * 1000 : double.NaN):F4}");
        }
        catch (Exception exception) when (IsPackageFault(exception))
        {
            Console.Error.WriteLine($"[SONG CACHE] crosscheck failed error=\"{exception.Message}\"");
        }
    }

    private static VisualNote[] Canonical(IEnumerable<VisualNote> notes) => notes
        .OrderBy(static note => note.StartTime)
        .ThenBy(static note => note.TargetKeyIndex)
        .ThenBy(static note => note.Duration)
        .ToArray();

    /// <summary>
    /// Keeps a PDF or image chosen from outside the library in <c>songs/pdf</c> under its own
    /// name, so the library lists it. An import already lives in <c>songs/midi/custom</c>.
    /// </summary>
    private static void RetainSource(string sourcePath, OmrEngine engine, string applicationDirectory)
    {
        if (engine == OmrEngine.MusicXml)
        {
            return;
        }
        string pdfDirectory = Path.Combine(applicationDirectory, "songs", "pdf");
        string source = Path.GetFullPath(sourcePath);
        if (string.Equals(Path.GetDirectoryName(source), Path.GetFullPath(pdfDirectory), StringComparison.OrdinalIgnoreCase))
        {
            return;
        }
        try
        {
            Directory.CreateDirectory(pdfDirectory);
            string target = Path.Combine(pdfDirectory, Path.GetFileName(source));
            if (File.Exists(target))
            {
                if (ComputeSha256(target) == ComputeSha256(source))
                {
                    return;
                }
                target = Path.Combine(pdfDirectory,
                    $"{Path.GetFileNameWithoutExtension(source)} ({ComputeSha256(source)[..8]}){Path.GetExtension(source)}");
                if (File.Exists(target))
                {
                    return;
                }
            }
            string temporary = Path.Combine(pdfDirectory, $".{Path.GetFileName(target)}.{Guid.NewGuid():N}.tmp");
            try
            {
                File.Copy(source, temporary);
                File.Move(temporary, target);
                File.SetLastWriteTimeUtc(target, File.GetLastWriteTimeUtc(source));
            }
            finally
            {
                DeleteTemporaryFile(temporary);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[SONG CACHE] decision=source_not_retained error=\"{exception.Message}\"");
        }
    }

    // --- Validation ----------------------------------------------------------------------------

    /// <summary>The package if its manifest matches this engine and its pages match their hashes.</summary>
    private static ValidPackage? TryReadPackage(PackagePaths paths, OmrEngine engine, string? sourceHash)
    {
        if (!File.Exists(paths.ManifestPath) || !File.Exists(paths.RecognitionPath))
        {
            return null;
        }
        try
        {
            PackageManifest manifest = ReadJson<PackageManifest>(paths.ManifestPath);
            if (manifest.PackageManifestVersion != PackageManifestVersion ||
                (sourceHash is not null && manifest.SourceSha256 != sourceHash) ||
                manifest.Engine != engine ||
                manifest.EngineRevision != OmrPipeline.GetEngineRevision(engine) ||
                manifest.ModelRevision != OmrPipeline.GetModelRevision(engine) ||
                manifest.BridgeSchemaVersion != OmrPipeline.SchemaVersion ||
                manifest.OmrSettings != GetOmrSettings(engine) ||
                (OmrPipeline.IsPinnedNative(engine) && manifest.RuntimeProfileSha256 != OmrPipeline.GetProfileSha256(engine)) ||
                manifest.RecognitionSha256 != ComputeSha256(paths.RecognitionPath))
            {
                return null;
            }
            Recognition recognition = ReadJson<Recognition>(paths.RecognitionPath);
            if (recognition.SourceSha256 != manifest.SourceSha256 || recognition.Files.Count == 0 ||
                recognition.Kind is not ("omr-pages" or "musicxml"))
            {
                return null;
            }
            List<string> sources = [];
            string root = Path.GetFullPath(paths.Directory).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            foreach (RecognitionFile file in recognition.Files)
            {
                string path = Path.GetFullPath(Path.Combine(paths.Directory, file.Name));
                if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase) || !File.Exists(path) ||
                    ComputeSha256(path) != file.Sha256)
                {
                    Console.Error.WriteLine($"[SONG CACHE] decision=invalid_package reason=page path=\"{path}\"");
                    return null;
                }
                sources.Add(path);
            }
            return new ValidPackage(paths, manifest, sources, recognition.Kind == "musicxml");
        }
        catch (Exception exception) when (IsPackageFault(exception))
        {
            Console.Error.WriteLine($"[SONG CACHE] decision=invalid_package error=\"{exception.Message}\"");
            return null;
        }
    }

    private static bool TryReadInterpretation(string derived, string key, bool timing,
        out SongPerformance? performance, out List<VisualNote>? notes)
    {
        performance = null;
        notes = null;
        string manifestPath = Path.Combine(derived, InterpretationManifestName);
        if (!File.Exists(manifestPath))
        {
            return false;
        }
        try
        {
            InterpretationManifest manifest = ReadJson<InterpretationManifest>(manifestPath);
            string performancePath = Path.Combine(derived, PerformanceName);
            if (manifest.InterpretationKey != key || manifest.TimingCorrection != timing ||
                !File.Exists(performancePath) || ComputeSha256(performancePath) != manifest.PerformanceSha256)
            {
                return false;
            }
            performance = SongPerformance.Parse(File.ReadAllText(performancePath));
            notes = SongTimeline.BuildNotes(performance, PlaybackTimeline);
            return notes.Count == manifest.NoteCount && notes.Count > 0;
        }
        catch (Exception exception) when (IsPackageFault(exception))
        {
            Console.Error.WriteLine($"[SONG CACHE] decision=invalid_interpretation error=\"{exception.Message}\"");
            return false;
        }
    }

    /// <summary>Checks an interpretation in <paramref name="directory"/> and writes its manifest.</summary>
    private static (List<VisualNote> Notes, SongPerformance Performance) WriteInterpretation(string directory,
        string key, bool timing)
    {
        string performancePath = Path.Combine(directory, PerformanceName);
        string scorePath = Path.Combine(directory, CombinedScoreName);
        if (!File.Exists(performancePath) || !File.Exists(scorePath))
        {
            throw new InvalidDataException("The interpreter did not write a performance and a score.");
        }
        SongPerformance performance = SongPerformance.Parse(File.ReadAllText(performancePath));
        if (performance.TimingCorrection != timing)
        {
            throw new InvalidDataException("The interpretation does not match the requested timing fix.");
        }
        List<VisualNote> notes = SongTimeline.BuildNotes(performance, PlaybackTimeline);
        if (notes.Count == 0)
        {
            throw new InvalidDataException("The song has no notes inside the 88-key piano range.");
        }
        WriteJsonAtomic(Path.Combine(directory, InterpretationManifestName), new InterpretationManifest(
            key, timing, ComputeSha256(performancePath), ComputeSha256(scorePath), notes.Count,
            GetTotalDuration(notes), DateTimeOffset.UtcNow));
        return (notes, performance);
    }

    private static void RemoveStaleInterpretations(PackagePaths paths, string currentKey, bool timing)
    {
        if (!Directory.Exists(paths.DerivedRoot))
        {
            return;
        }
        foreach (string directory in Directory.EnumerateDirectories(paths.DerivedRoot))
        {
            string name = Path.GetFileName(directory);
            if (name == currentKey || name.EndsWith(".tmp", StringComparison.Ordinal))
            {
                continue;
            }
            string manifestPath = Path.Combine(directory, InterpretationManifestName);
            try
            {
                if (!File.Exists(manifestPath) || ReadJson<InterpretationManifest>(manifestPath).TimingCorrection == timing)
                {
                    DeleteDirectory(directory);
                }
            }
            catch (Exception exception) when (IsPackageFault(exception))
            {
                DeleteDirectory(directory);
            }
        }
    }

    private static bool IsPackageFault(Exception exception) =>
        exception is IOException or UnauthorizedAccessException or InvalidDataException or JsonException or
            CryptographicException or OverflowException or ArgumentException or InvalidOperationException or
            OmrPipelineException or TimeoutException or NotSupportedException;

    // --- Listing -------------------------------------------------------------------------------

    /// <summary>
    /// Opens a library or recent-songs entry that points at an interpretation. Listing never runs
    /// the interpreter, so an entry whose interpretation is out of date is listed from it as it
    /// stands; opening it re-interprets.
    /// </summary>
    private static bool TryLoadPackageEntry(RecentSongEntry entry, string interpretationPath, PackageContext context,
        bool allowInterpretation, out SongLoadResult? result)
    {
        result = null;
        string derived = Path.GetDirectoryName(interpretationPath)!;
        PackagePaths paths = new(Path.GetDirectoryName(Path.GetDirectoryName(derived)!)!);
        ValidPackage? package = TryReadPackage(paths, entry.Engine, sourceHash: null);
        if (package is null || !File.Exists(interpretationPath))
        {
            return false;
        }
        bool timing = ReadJson<InterpretationManifest>(interpretationPath).TimingCorrection;
        string currentKey = SongInterpreter.InterpretationKey(context.BridgeDirectory, timing);
        if (Path.GetFileName(derived) == currentKey || allowInterpretation)
        {
            try
            {
                result = LoadInterpretation(package, context, timing, allowInterpretation, null, CancellationToken.None);
            }
            catch (Exception exception) when (IsPackageFault(exception))
            {
                Console.Error.WriteLine($"[SONG CACHE] decision=interpretation_failed error=\"{exception.Message}\"");
            }
            return result is not null;
        }
        string staleKey = Path.GetFileName(derived);
        if (!TryReadInterpretation(derived, staleKey, timing, out SongPerformance? stale, out List<VisualNote>? notes))
        {
            return false;
        }
        result = PackageResult(package, notes!, stale!, timing, derived, context.ApplicationDirectory);
        return true;
    }

    /// <summary>Every interpretation in the library, one per package and timing setting.</summary>
    private static IEnumerable<(string Path, OmrEngine Engine)> EnumeratePackageEntries(string applicationDirectory)
    {
        string scoresRoot = Path.Combine(applicationDirectory, "songs", ScoresFolderName);
        if (!Directory.Exists(scoresRoot))
        {
            yield break;
        }
        foreach (OmrEngine engine in Enum.GetValues<OmrEngine>().Where(OmrPipeline.SupportsSongPackage))
        {
            string engineDirectory = Path.Combine(scoresRoot, OmrPipeline.GetEngineName(engine));
            if (!Directory.Exists(engineDirectory))
            {
                continue;
            }
            foreach (string packageDirectory in Directory.EnumerateDirectories(engineDirectory))
            {
                string derivedRoot = Path.Combine(packageDirectory, "derived");
                if (!Directory.Exists(derivedRoot))
                {
                    continue;
                }
                // Stale interpretations are removed when a newer one is written; until then the
                // newest per timing setting stands for the song.
                Dictionary<bool, (string Path, DateTime Written)> newest = [];
                foreach (string manifestPath in Directory.EnumerateFiles(derivedRoot, InterpretationManifestName,
                             SearchOption.AllDirectories))
                {
                    if (Path.GetDirectoryName(manifestPath)!.EndsWith(".tmp", StringComparison.Ordinal))
                    {
                        continue;
                    }
                    bool timing;
                    try
                    {
                        timing = ReadJson<InterpretationManifest>(manifestPath).TimingCorrection;
                    }
                    catch (Exception exception) when (IsPackageFault(exception))
                    {
                        continue;
                    }
                    DateTime written = File.GetLastWriteTimeUtc(manifestPath);
                    if (!newest.TryGetValue(timing, out (string Path, DateTime Written) current) || written > current.Written)
                    {
                        newest[timing] = (manifestPath, written);
                    }
                }
                foreach ((string path, _) in newest.Values)
                {
                    yield return (path, engine);
                }
            }
        }
    }

    /// <summary>Sources (by engine and SHA-256) that have a package, whose MIDI caches it supersedes.</summary>
    private static HashSet<(OmrEngine, string)> PackagedSources(string applicationDirectory)
    {
        HashSet<(OmrEngine, string)> packaged = [];
        foreach ((string path, OmrEngine engine) in EnumeratePackageEntries(applicationDirectory))
        {
            string packageDirectory = Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(path)!)!)!;
            try
            {
                packaged.Add((engine, ReadJson<PackageManifest>(Path.Combine(packageDirectory, PackageManifestName)).SourceSha256));
            }
            catch (Exception exception) when (IsPackageFault(exception))
            {
            }
        }
        return packaged;
    }

    private static bool IsSupersededMidiCache(string manifestPath, OmrEngine engine, HashSet<(OmrEngine, string)> packaged)
    {
        if (packaged.Count == 0)
        {
            return false;
        }
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(manifestPath));
            return document.RootElement.TryGetProperty("source_sha256", out JsonElement source) &&
                   source.GetString() is string sha && packaged.Contains((engine, sha));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return false;
        }
    }

    private static bool IsPackageHit(string sourcePath, OmrEngine engine, string applicationDirectory)
    {
        string sourceHash = ComputeSha256(ValidateInputPath(sourcePath));
        return TryReadPackage(CreatePackagePaths(engine, applicationDirectory, sourceHash), engine, sourceHash) is not null;
    }

    // --- Files ---------------------------------------------------------------------------------

    private static T ReadJson<T>(string path) =>
        JsonSerializer.Deserialize<T>(File.ReadAllText(path), ManifestJsonOptions)
        ?? throw new InvalidDataException($"{Path.GetFileName(path)} is empty.");

    private static void WriteJsonAtomic<T>(string path, T value)
    {
        string temporary = Path.Combine(Path.GetDirectoryName(path)!, $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporary, JsonSerializer.Serialize(value, ManifestJsonOptions));
            File.Move(temporary, path, overwrite: true);
        }
        finally
        {
            DeleteTemporaryFile(temporary);
        }
    }

    /// <summary>Moves a finished directory into place, replacing what was there.</summary>
    private static void ReplaceDirectory(string staging, string target)
    {
        string? retired = null;
        if (Directory.Exists(target))
        {
            retired = target + $".{Guid.NewGuid():N}.old.tmp";
            Directory.Move(target, retired);
        }
        Directory.Move(staging, target);
        if (retired is not null)
        {
            DeleteDirectory(retired);
        }
    }

    private static void DeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
        }
    }

    private static void LogPackage(OmrEngine engine, string sourceHash, string decision, string path) =>
        Console.Error.WriteLine(
            $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} source_sha256={sourceHash} " +
            $"decision={decision} kind=package path=\"{path}\"");

    // --- Test hooks ----------------------------------------------------------------------------

    internal static SongLoadResult LoadOrCreatePackageForTesting(string inputPath, OmrEngine engine,
        string applicationDirectory, string bridgeDirectory, SongPipeline pipeline, SongInterpretation interpret,
        bool timingCorrection = false, bool forceReprocess = false) =>
        LoadOrCreatePackageCore(inputPath, engine, new PackageContext(applicationDirectory, bridgeDirectory, interpret),
            pipeline, CancellationToken.None, null, bypassKnownFailure: true, forceReprocess, timingCorrection);

    internal static bool TryLoadRecentForTesting(RecentSongEntry entry, string applicationDirectory,
        string bridgeDirectory, SongInterpretation interpret, bool allowInterpretation, out SongLoadResult? result) =>
        TryLoadRecentCore(entry, applicationDirectory, out result, allowInterpretation,
            new PackageContext(applicationDirectory, bridgeDirectory, interpret));

    internal static IReadOnlyList<CachedSongEntry> GetCachedSongsForTesting(string applicationDirectory,
        string bridgeDirectory, SongInterpretation interpret) =>
        GetCachedSongsCore(applicationDirectory, new PackageContext(applicationDirectory, bridgeDirectory, interpret));

    internal static bool IsPackageHitForTesting(string sourcePath, OmrEngine engine, string applicationDirectory) =>
        IsPackageHit(sourcePath, engine, applicationDirectory);
}
