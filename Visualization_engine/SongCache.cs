using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Interaction;
using Raylib_cs;
using Color = Raylib_cs.Color;
using MidiNote = Melanchall.DryWetMidi.Interaction.Note;
using VisualNote = SynthesiaClone.Note;

namespace SynthesiaClone;

public sealed record SongLoadResult(
    List<Note> Notes,
    string DisplayName,
    OmrEngine Engine,
    bool LoadedFromCache,
    string? ManifestRelativePath)
{
    public int NoteCount => Notes.Count;
}

public sealed record PdfLibraryEntry(
    string FullPath,
    string DisplayName,
    long SizeBytes,
    DateTimeOffset LastModifiedUtc);

public sealed record MidiLibraryEntry(
    string FullPath,
    string DisplayName,
    long SizeBytes,
    DateTimeOffset LastModifiedUtc);

public sealed record CachedSongEntry(
    RecentSongEntry RecentSong,
    int NoteCount,
    double DurationSeconds);

public static class SongCache
{
    private const int CacheManifestVersion = 2;
    private const short TicksPerQuarterNote = 480;
    private const int DefaultVelocity = 80;
    private const string TempoPolicy = "musicxml-tempo-or-120-bpm";

    private static readonly JsonSerializerOptions ManifestJsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    private static readonly JsonSerializerOptions LegacyManifestJsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Converters = { new JsonStringEnumConverter<OmrEngine>(JsonNamingPolicy.CamelCase) }
    };

    public static List<VisualNote> LoadOrCreate(string inputPath, OmrEngine engine)
    {
        return LoadOrCreateDetailed(inputPath, engine).Notes;
    }

    public static List<VisualNote> LoadOrCreate(
        string inputPath,
        OmrEngine engine,
        CancellationToken cancellationToken)
    {
        return LoadOrCreateDetailed(inputPath, engine, cancellationToken).Notes;
    }

    public static SongLoadResult LoadOrCreateDetailed(
        string inputPath,
        OmrEngine engine,
        CancellationToken cancellationToken = default,
        IProgress<OmrProgress>? progress = null,
        bool bypassKnownFailure = false,
        bool forceReprocess = false)
    {
        string applicationDirectory = FindApplicationDirectory();
        
        string ext = Path.GetExtension(inputPath).ToLowerInvariant();
        bool isMidi = ext is ".mid" or ".midi";
        bool isXml = ext is ".mxl" or ".musicxml" or ".xml";
        
        if (isMidi || isXml)
        {
            string customDir = Path.Combine(applicationDirectory, "songs", "midi", "custom");
            Directory.CreateDirectory(customDir);
            string destFile = Path.Combine(customDir, Path.GetFileName(inputPath));
            
            try 
            {
                string fullInput = Path.GetFullPath(inputPath);
                string fullDest = Path.GetFullPath(destFile);
                if (!string.Equals(fullInput, fullDest, StringComparison.OrdinalIgnoreCase) && File.Exists(inputPath))
                {
                    File.Copy(inputPath, destFile, overwrite: true);
                }
                inputPath = destFile;
            }
            catch (IOException)
            {
                // Ignore copy errors (e.g. file is locked or identical paths bypassed string compare)
                // Just use the inputPath as is
            }
        }

        if (isMidi)
        {
            List<VisualNote> parsed = ReadMidi(inputPath);
            SongLoadResult midiResult = new SongLoadResult(
                Notes: parsed,
                DisplayName: Path.GetFileNameWithoutExtension(inputPath),
                Engine: OmrEngine.DirectMidi,
                LoadedFromCache: true,
                ManifestRelativePath: Path.GetRelativePath(applicationDirectory, inputPath)
            );
            TouchRecent(midiResult);
            return midiResult;
        }

        if (isXml)
        {
            engine = OmrEngine.MusicXml;
        }

        SongLoadResult result = LoadOrCreateCore(
            inputPath,
            engine,
            applicationDirectory,
            (path, selectedEngine, token) =>
                OmrPipeline.Run(
                    path,
                    selectedEngine,
                    cancellationToken: token,
                    progress: progress),
            cancellationToken,
            progress,
            bypassKnownFailure,
            forceReprocess);
        TouchRecent(result);
        return result;
    }

    /// <summary>
    /// Reports whether a validated cache already exists for this source file and engine,
    /// so the UI can offer to reuse it instead of running the pipeline again.
    /// </summary>
    public static bool HasCachedResult(string sourcePath, OmrEngine engine)
    {
        try
        {
            return IsCacheHit(sourcePath, engine, FindApplicationDirectory());
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return false;
        }
    }

    private static SongLoadResult LoadOrCreateCore(
        string inputPath,
        OmrEngine engine,
        string applicationDirectory,
        Func<string, OmrEngine, CancellationToken, OmrResult> pipeline,
        CancellationToken cancellationToken,
        IProgress<OmrProgress>? progress = null,
        bool bypassKnownFailure = false,
        bool forceReprocess = false)
    {
        ArgumentNullException.ThrowIfNull(pipeline);
        cancellationToken.ThrowIfCancellationRequested();
        string sourcePath = ValidateInputPath(inputPath);
        string sourceHash = ComputeSha256(sourcePath);
        CachePaths cachePaths = CreateCachePaths(sourcePath, engine, applicationDirectory);
        Directory.CreateDirectory(cachePaths.MidiDirectory);
        Directory.CreateDirectory(cachePaths.PdfDirectory);

        ReportProgress(progress, engine, OmrProgressStages.CacheLookup, OmrProgressStatuses.Started,
            forceReprocess ? "Ignoring song cache (re-run requested)" : "Checking song cache");
        if (forceReprocess)
        {
            Console.Error.WriteLine(
                $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} " +
                $"source_sha256={sourceHash} decision=forced_rerun path=\"{cachePaths.MidiPath}\"");
        }
        else if (TryReadCache(sourceHash, engine, cachePaths, out List<VisualNote>? cachedNotes))
        {
            Console.Error.WriteLine(
                $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} " +
                $"source_sha256={sourceHash} decision=hit path=\"{cachePaths.MidiPath}\"");
            ReportProgress(progress, engine, OmrProgressStages.Complete, OmrProgressStatuses.Completed,
                "Loaded validated MIDI cache");
            return CreateLoadResult(
                cachedNotes,
                sourcePath,
                engine,
                loadedFromCache: true,
                cachePaths,
                applicationDirectory);
        }

        ReportProgress(progress, engine, OmrProgressStages.CacheLookup, OmrProgressStatuses.Completed,
            "Cache miss; starting OMR");
        Console.Error.WriteLine(
            $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} " +
            $"source_sha256={sourceHash} decision=miss input=\"{sourcePath}\"");
        if (!bypassKnownFailure &&
            OmrFailureStore.TryGet(sourceHash, engine, out OmrFailureEntry? knownFailure) &&
            knownFailure is not null)
        {
            ReportProgress(
                progress,
                engine,
                OmrProgressStages.KnownFailure,
                OmrProgressStatuses.Completed,
                $"Known deterministic failure on page {knownFailure.Page?.ToString() ?? "?"}");
            throw new KnownOmrFailureException(knownFailure);
        }

        OmrResult result;
        try
        {
            result = pipeline(sourcePath, engine, cancellationToken);
        }
        catch (OmrPipelineException exception)
        {
            OmrFailureStore.Remember(sourceHash, engine, exception);
            throw;
        }
        cancellationToken.ThrowIfCancellationRequested();
        OmrFailureStore.Remove(sourceHash, engine);
        List<VisualNote> generatedNotes = MapOmrNotes(result.Notes);
        if (generatedNotes.Count == 0)
        {
            throw new InvalidDataException(
                "OMR produced notes, but none are inside the 88-key piano range.");
        }

        try
        {
            ReportProgress(progress, engine, OmrProgressStages.MidiWrite,
                OmrProgressStatuses.Started, "Writing MIDI cache");
            PersistCache(sourcePath, sourceHash, engine, cachePaths, result, generatedNotes);
            ReportProgress(progress, engine, OmrProgressStages.MidiWrite,
                OmrProgressStatuses.Completed, "MIDI cache written");
            ReportProgress(progress, engine, OmrProgressStages.CacheValidation,
                OmrProgressStatuses.Completed, "MIDI round-trip validated");
            Console.Error.WriteLine(
                $"[SONG CACHE] engine={OmrPipeline.GetEngineName(engine)} " +
                $"source_sha256={sourceHash} decision=saved path=\"{cachePaths.MidiPath}\"");
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or
            InvalidOperationException or InvalidDataException or JsonException or
            CryptographicException or OverflowException or FormatException or
            ArgumentException or MidiException)
        {
            Console.Error.WriteLine(
                "[SONG CACHE] decision=save_failed playback=uncached " +
                $"error=\"{exception.Message}\"");
        }

        ReportProgress(progress, engine, OmrProgressStages.Complete,
            OmrProgressStatuses.Completed, "Song is ready");
        return CreateLoadResult(
            generatedNotes,
            sourcePath,
            engine,
            loadedFromCache: false,
            cachePaths,
            applicationDirectory);
    }

    private static SongLoadResult CreateLoadResult(
        List<VisualNote> notes,
        string sourcePath,
        OmrEngine engine,
        bool loadedFromCache,
        CachePaths paths,
        string applicationDirectory) =>
        new(
            notes,
            Path.GetFileNameWithoutExtension(sourcePath),
            engine,
            loadedFromCache,
            File.Exists(paths.ManifestPath)
                ? Path.GetRelativePath(applicationDirectory, paths.ManifestPath)
                : null);

    private static void ReportProgress(
        IProgress<OmrProgress>? progress,
        OmrEngine engine,
        string stage,
        string status,
        string message) =>
        progress?.Report(new OmrProgress
        {
            Engine = engine,
            Stage = stage,
            Status = status,
            Message = message
        });

    private static void TouchRecent(SongLoadResult result)
    {
        if (string.IsNullOrWhiteSpace(result.ManifestRelativePath))
        {
            return;
        }
        RecentSongsStore.Touch(new RecentSongEntry(
            result.ManifestRelativePath,
            result.DisplayName,
            result.Engine,
            DateTimeOffset.UtcNow));
    }

    public static IReadOnlyList<RecentSongEntry> GetRecentSongs(int maximum = 5)
    {
        if (maximum <= 0)
        {
            return [];
        }
        string applicationDirectory = FindApplicationDirectory();
        IReadOnlyList<RecentSongEntry> stored = RecentSongsStore.Load();
        if (stored.Count == 0)
        {
            SeedRecentSongs(applicationDirectory);
            stored = RecentSongsStore.Load();
        }

        List<RecentSongEntry> valid = [];
        foreach (RecentSongEntry entry in stored)
        {
            if (TryLoadRecentCore(entry, applicationDirectory, out _))
            {
                valid.Add(entry);
                if (valid.Count == maximum)
                {
                    break;
                }
            }
            else
            {
                RecentSongsStore.Remove(entry.ManifestRelativePath);
            }
        }
        return valid;
    }

    public static IReadOnlyList<PdfLibraryEntry> GetPdfLibrary()
    {
        return GetPdfLibraryCore(FindApplicationDirectory());
    }

    public static IReadOnlyList<MidiLibraryEntry> GetMidiLibrary()
    {
        return GetMidiLibraryCore(FindApplicationDirectory());
    }

    public static IReadOnlyList<CachedSongEntry> GetCachedSongs()
    {
        return GetCachedSongsCore(FindApplicationDirectory());
    }

    private static IReadOnlyList<PdfLibraryEntry> GetPdfLibraryCore(
        string applicationDirectory)
    {
        string pdfDirectory = Path.Combine(applicationDirectory, "songs", "pdf");
        try
        {
            if (!Directory.Exists(pdfDirectory))
            {
                Directory.CreateDirectory(pdfDirectory);
                return [];
            }
            return Directory.EnumerateFiles(pdfDirectory, "*.*", SearchOption.TopDirectoryOnly)
                .Where(file => file.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".png", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".jpeg", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".bmp", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".tif", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".tiff", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".webp", StringComparison.OrdinalIgnoreCase))
                .Select(static path => new FileInfo(path))
                .Select(static file => new PdfLibraryEntry(
                    file.FullName,
                    Path.GetFileNameWithoutExtension(file.Name),
                    file.Length,
                    file.LastWriteTimeUtc))
                .OrderBy(static entry => entry.DisplayName, StringComparer.CurrentCultureIgnoreCase)
                .ToArray();
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[PDF LIBRARY] Scan failed: {exception.Message}");
            return [];
        }
    }

    private static IReadOnlyList<MidiLibraryEntry> GetMidiLibraryCore(
        string applicationDirectory)
    {
        string midiDirectory = Path.Combine(applicationDirectory, "songs", "midi", "custom");
        try
        {
            if (!Directory.Exists(midiDirectory))
            {
                Directory.CreateDirectory(midiDirectory);
                return [];
            }
            return Directory.EnumerateFiles(midiDirectory, "*.*", SearchOption.TopDirectoryOnly)
                .Where(file => file.EndsWith(".mid", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".midi", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".mxl", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".musicxml", StringComparison.OrdinalIgnoreCase) ||
                               file.EndsWith(".xml", StringComparison.OrdinalIgnoreCase))
                .Select(static path => new FileInfo(path))
                .Select(static file => new MidiLibraryEntry(
                    file.FullName,
                    Path.GetFileNameWithoutExtension(file.Name),
                    file.Length,
                    file.LastWriteTimeUtc))
                .OrderBy(static entry => entry.DisplayName, StringComparer.CurrentCultureIgnoreCase)
                .ToArray();
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[MIDI LIBRARY] Scan failed: {exception.Message}");
            return [];
        }
    }

    private static IReadOnlyList<CachedSongEntry> GetCachedSongsCore(
        string applicationDirectory)
    {
        string midiRoot = Path.Combine(applicationDirectory, "songs", "midi");
        if (!Directory.Exists(midiRoot))
        {
            return [];
        }

        Dictionary<string, DateTimeOffset> lastOpenedByManifest = RecentSongsStore.Load()
            .ToDictionary(
                static entry => entry.ManifestRelativePath,
                static entry => entry.LastOpenedUtc,
                StringComparer.OrdinalIgnoreCase);
        List<CachedSongEntry> cachedSongs = [];
        foreach (OmrEngine engine in Enum.GetValues<OmrEngine>())
        {
            string engineDirectory = Path.Combine(
                midiRoot,
                OmrPipeline.GetEngineName(engine));
            if (!Directory.Exists(engineDirectory))
            {
                continue;
            }

            try
            {
                foreach (string manifestPath in Directory.EnumerateFiles(
                             engineDirectory,
                             "*.mid.cache.json",
                             SearchOption.TopDirectoryOnly))
                {
                    string relativePath = Path.GetRelativePath(
                        applicationDirectory,
                        manifestPath);
                    string fileName = Path.GetFileName(manifestPath);
                    string fallbackName = fileName[..^".mid.cache.json".Length];
                    DateTimeOffset lastOpened = lastOpenedByManifest.TryGetValue(
                        relativePath,
                        out DateTimeOffset storedLastOpened)
                        ? storedLastOpened
                        : File.GetLastWriteTimeUtc(manifestPath);
                    RecentSongEntry candidate = new(
                        relativePath,
                        fallbackName,
                        engine,
                        lastOpened);
                    if (TryLoadRecentCore(
                            candidate,
                            applicationDirectory,
                            out SongLoadResult? loaded) &&
                        loaded is not null)
                    {
                        cachedSongs.Add(new CachedSongEntry(
                            candidate with { DisplayName = loaded.DisplayName },
                            loaded.NoteCount,
                            GetTotalDuration(loaded.Notes)));
                    }
                }
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException)
            {
                Console.Error.WriteLine(
                    $"[CACHE LIBRARY] Could not scan {engineDirectory}: {exception.Message}");
            }
        }

        return cachedSongs
            .OrderBy(static entry => (int)entry.RecentSong.Engine)
            .ThenBy(static entry => entry.RecentSong.DisplayName, StringComparer.CurrentCultureIgnoreCase)
            .ToArray();
    }

    public static SongLoadResult LoadRecent(RecentSongEntry entry)
    {
        ArgumentNullException.ThrowIfNull(entry);
        string applicationDirectory = FindApplicationDirectory();
        if (!TryLoadRecentCore(entry, applicationDirectory, out SongLoadResult? result) ||
            result is null)
        {
            RecentSongsStore.Remove(entry.ManifestRelativePath);
            throw new InvalidDataException(
                $"Recent cache for '{entry.DisplayName}' is missing, outdated, or corrupt.");
        }
        TouchRecent(result);
        return result;
    }

    private static bool TryLoadRecentCore(
        RecentSongEntry entry,
        string applicationDirectory,
        out SongLoadResult? result)
    {
        result = null;
        try
        {
            string applicationRoot = Path.GetFullPath(applicationDirectory)
                .TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string manifestPath = Path.GetFullPath(
                Path.Combine(applicationDirectory, entry.ManifestRelativePath));
            
            if (!manifestPath.StartsWith(applicationRoot, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (manifestPath.EndsWith(".mid", StringComparison.OrdinalIgnoreCase) && File.Exists(manifestPath))
            {
                result = new SongLoadResult(
                    ReadMidi(manifestPath),
                    Path.GetFileNameWithoutExtension(manifestPath),
                    entry.Engine,
                    true,
                    entry.ManifestRelativePath);
                return true;
            }

            if (!manifestPath.EndsWith(".mid.cache.json", StringComparison.OrdinalIgnoreCase) ||
                !File.Exists(manifestPath))
            {
                return false;
            }
            string midiPath = manifestPath[..^".cache.json".Length];
            if (!File.Exists(midiPath))
            {
                return false;
            }

            CacheManifest? manifest = DeserializeCompatibleManifest(
                File.ReadAllText(manifestPath),
                entry.Engine,
                out bool requiresUpgrade);
            if (manifest is null ||
                manifest.Engine != entry.Engine ||
                manifest.EngineRevision != OmrPipeline.GetEngineRevision(entry.Engine) ||
                manifest.ModelRevision != OmrPipeline.GetModelRevision(entry.Engine) ||
                manifest.BridgeSchemaVersion != OmrPipeline.SchemaVersion ||
                manifest.TempoPolicy != TempoPolicy ||
                manifest.OmrSettings != GetOmrSettings(entry.Engine))
            {
                return false;
            }

            List<VisualNote> notes = ReadMidi(midiPath);
            if (notes.Count == 0 || notes.Count != manifest.NoteCount)
            {
                return false;
            }
            string midiSha256 = ComputeSha256(midiPath);
            if (manifest.CacheManifestVersion >= CacheManifestVersion &&
                !string.Equals(manifest.MidiSha256, midiSha256, StringComparison.Ordinal))
            {
                return false;
            }
            string displayName = string.IsNullOrWhiteSpace(manifest.DisplayName)
                ? entry.DisplayName
                : manifest.DisplayName;
            if (requiresUpgrade || manifest.CacheManifestVersion < CacheManifestVersion ||
                string.IsNullOrWhiteSpace(manifest.MidiSha256) ||
                manifest.DurationSeconds is null ||
                string.IsNullOrWhiteSpace(manifest.DisplayName))
            {
                manifest = manifest with
                {
                    CacheManifestVersion = CacheManifestVersion,
                    MidiSha256 = midiSha256,
                    DurationSeconds = GetTotalDuration(notes),
                    DisplayName = displayName
                };
                TryUpgradeManifest(manifestPath, manifest);
            }
            result = new SongLoadResult(
                notes,
                displayName,
                entry.Engine,
                LoadedFromCache: true,
                Path.GetRelativePath(applicationDirectory, manifestPath));
            return true;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or InvalidDataException or
            JsonException or CryptographicException or OverflowException or ArgumentException or
            MidiException)
        {
            Console.Error.WriteLine($"[RECENT SONGS] Invalid entry: {exception.Message}");
            return false;
        }
    }

    private static void SeedRecentSongs(string applicationDirectory)
    {
        string midiRoot = Path.Combine(applicationDirectory, "songs", "midi");
        if (!Directory.Exists(midiRoot))
        {
            return;
        }
        List<RecentSongEntry> candidates = [];
        foreach (OmrEngine engine in Enum.GetValues<OmrEngine>())
        {
            string engineDirectory = Path.Combine(midiRoot, OmrPipeline.GetEngineName(engine));
            if (!Directory.Exists(engineDirectory))
            {
                continue;
            }
            foreach (string manifestPath in Directory.EnumerateFiles(
                         engineDirectory, "*.mid.cache.json", SearchOption.TopDirectoryOnly))
            {
                string displayName = Path.GetFileName(manifestPath)[..^".mid.cache.json".Length];
                candidates.Add(new RecentSongEntry(
                    Path.GetRelativePath(applicationDirectory, manifestPath),
                    displayName,
                    engine,
                    File.GetLastWriteTimeUtc(manifestPath)));
            }
        }

        foreach (RecentSongEntry candidate in candidates
                     .OrderBy(entry => entry.LastOpenedUtc)
                     .TakeLast(10))
        {
            if (TryLoadRecentCore(candidate, applicationDirectory, out _))
            {
                RecentSongsStore.Touch(candidate);
            }
        }
    }

    private static string ValidateInputPath(string inputPath)
    {
        if (string.IsNullOrWhiteSpace(inputPath))
        {
            throw new ArgumentException("Song input path cannot be empty.", nameof(inputPath));
        }

        string fullPath = Path.GetFullPath(inputPath);
        if (!File.Exists(fullPath))
        {
            throw new FileNotFoundException("Song input file was not found.", fullPath);
        }
        return fullPath;
    }

    private static string ComputeSha256(string path)
    {
        using FileStream stream = new(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            1024 * 1024,
            FileOptions.SequentialScan);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    private static CachePaths CreateCachePaths(
        string sourcePath,
        OmrEngine engine,
        string applicationDirectory)
    {
        string songsDirectory = Path.Combine(applicationDirectory, "songs");
        string pdfDirectory = Path.Combine(songsDirectory, "pdf");
        string midiDirectory = Path.Combine(
            songsDirectory,
            "midi",
            OmrPipeline.GetEngineName(engine));
        string songName = Path.GetFileNameWithoutExtension(sourcePath);
        string midiPath = Path.Combine(midiDirectory, $"{songName}.mid");
        return new CachePaths(
            pdfDirectory,
            midiDirectory,
            Path.Combine(pdfDirectory, Path.GetFileName(sourcePath)),
            midiPath,
            $"{midiPath}.cache.json");
    }

    private const string HomeVariable = "SHEET2PLAY_HOME";

    private static string? resolvedApplicationDirectory;

    private static string FindApplicationDirectory() =>
        resolvedApplicationDirectory ??= ResolveApplicationDirectory();

    /// <summary>
    /// The folder holding songs/ and the cache: %LOCALAPPDATA%/Sheet2Play unless
    /// SHEET2PLAY_HOME overrides it, so a source checkout and a published build share one
    /// library instead of each keeping its own copy.
    ///
    /// LocalApplicationData, not ApplicationData: it matches AppSettingsStore,
    /// RecentSongsStore and OmrFailureStore so everything lives in one folder, and a
    /// multi-gigabyte score library has no business roaming with a profile.
    /// </summary>
    public static string ApplicationDirectory => FindApplicationDirectory();

    private static string ResolveApplicationDirectory()
    {
        string? configured = Environment.GetEnvironmentVariable(HomeVariable);
        string home;
        if (!string.IsNullOrWhiteSpace(configured))
        {
            home = Environment.ExpandEnvironmentVariables(configured.Trim());
            Console.WriteLine($"[APP HOME] Using {HomeVariable}: {home}");
        }
        else
        {
            home = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Sheet2Play");
        }

        try
        {
            Directory.CreateDirectory(Path.Combine(home, "songs", "pdf"));
            Directory.CreateDirectory(Path.Combine(home, "songs", "midi", "custom"));
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"[APP HOME] Could not prepare {home}: {exception.Message}");
        }
        return home;
    }

    private static bool TryReadCache(
        string sourceHash,
        OmrEngine engine,
        CachePaths cachePaths,
        out List<VisualNote> notes)
    {
        notes = [];
        if (!File.Exists(cachePaths.MidiPath) || !File.Exists(cachePaths.ManifestPath))
        {
            return false;
        }

        try
        {
            CacheManifest? manifest = DeserializeCompatibleManifest(
                File.ReadAllText(cachePaths.ManifestPath),
                engine,
                out bool upgradeLegacyManifest);
            if (manifest is null ||
                manifest.SourceSha256 != sourceHash ||
                manifest.Engine != engine ||
                manifest.EngineRevision != OmrPipeline.GetEngineRevision(engine) ||
                manifest.ModelRevision != OmrPipeline.GetModelRevision(engine) ||
                manifest.BridgeSchemaVersion != OmrPipeline.SchemaVersion ||
                manifest.TempoPolicy != TempoPolicy ||
                manifest.OmrSettings != GetOmrSettings(engine))
            {
                return false;
            }

            notes = ReadMidi(cachePaths.MidiPath);
            if (notes.Count == 0 || notes.Count != manifest.NoteCount)
            {
                throw new InvalidDataException(
                    "Cached MIDI note count does not match its manifest.");
            }

            string midiSha256 = ComputeSha256(cachePaths.MidiPath);
            if (manifest.CacheManifestVersion >= CacheManifestVersion &&
                !string.Equals(manifest.MidiSha256, midiSha256, StringComparison.Ordinal))
            {
                throw new InvalidDataException("Cached MIDI SHA-256 does not match its manifest.");
            }

            if (upgradeLegacyManifest ||
                manifest.CacheManifestVersion < CacheManifestVersion ||
                string.IsNullOrWhiteSpace(manifest.MidiSha256) ||
                manifest.DurationSeconds is null ||
                string.IsNullOrWhiteSpace(manifest.DisplayName))
            {
                manifest = manifest with
                {
                    CacheManifestVersion = CacheManifestVersion,
                    MidiSha256 = midiSha256,
                    DurationSeconds = GetTotalDuration(notes),
                    DisplayName = Path.GetFileNameWithoutExtension(cachePaths.MidiPath)
                };
                TryUpgradeManifest(cachePaths.ManifestPath, manifest);
            }
            return true;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or
            InvalidDataException or JsonException or CryptographicException or OverflowException or
            MidiException)
        {
            Console.Error.WriteLine(
                $"[SONG CACHE] decision=invalid regenerate=true error=\"{exception.Message}\"");
            notes = [];
            return false;
        }
    }

    private static CacheManifest? DeserializeCompatibleManifest(
        string manifestJson,
        OmrEngine requestedEngine,
        out bool upgradeLegacyManifest)
    {
        upgradeLegacyManifest = false;
        try
        {
            return JsonSerializer.Deserialize<CacheManifest>(
                manifestJson,
                ManifestJsonOptions);
        }
        catch (JsonException) when (requestedEngine == OmrEngine.Homr)
        {
            LegacyExpandedCacheManifest? expanded =
                JsonSerializer.Deserialize<LegacyExpandedCacheManifest>(
                    manifestJson,
                    LegacyManifestJsonOptions);
            if (expanded is not null &&
                expanded.Engine == OmrEngine.Homr &&
                expanded.OmrSettings is not null &&
                string.Equals(expanded.OmrSettings.Device, "cuda", StringComparison.Ordinal) &&
                string.Equals(
                    expanded.OmrSettings.CudaDevice,
                    "CUDAExecutionProvider",
                    StringComparison.Ordinal) &&
                string.Equals(
                    expanded.OmrSettings.Preprocessing,
                    "homr-default-300-dpi",
                    StringComparison.Ordinal) &&
                expanded.OmrSettings.DefaultTempoBpm == 120)
            {
                upgradeLegacyManifest = true;
                return new CacheManifest(
                    expanded.SourceSha256,
                    expanded.Engine,
                    expanded.EngineRevision,
                    expanded.ModelRevision,
                    expanded.BridgeSchemaVersion,
                    GetOmrSettings(OmrEngine.Homr),
                    expanded.TempoPolicy,
                    expanded.CreatedUtc,
                    expanded.NoteCount,
                    expanded.TempoCount,
                    expanded.CacheManifestVersion,
                    expanded.MidiSha256,
                    expanded.DurationSeconds,
                    expanded.DisplayName);
            }

            LegacyCacheManifest? legacy = JsonSerializer.Deserialize<LegacyCacheManifest>(
                manifestJson,
                LegacyManifestJsonOptions);
            if (legacy is null ||
                legacy.Engine != OmrEngine.Homr ||
                legacy.OmrSettings is null ||
                !string.Equals(legacy.OmrSettings.Device, "cuda", StringComparison.Ordinal) ||
                legacy.OmrSettings.BeamWidth is not null ||
                legacy.OmrSettings.PdfDpi != 300 ||
                legacy.OmrSettings.DefaultTempoBpm != 120 ||
                legacy.OmrSettings.BackboneRevision is not null)
            {
                return null;
            }

            upgradeLegacyManifest = true;
            return new CacheManifest(
                legacy.SourceSha256,
                legacy.Engine,
                legacy.EngineRevision,
                legacy.ModelRevision,
                legacy.BridgeSchemaVersion,
                GetOmrSettings(OmrEngine.Homr),
                legacy.TempoPolicy,
                legacy.CreatedUtc,
                legacy.NoteCount,
                legacy.TempoCount);
        }
    }

    private static void TryUpgradeManifest(string manifestPath, CacheManifest manifest)
    {
        string directory = Path.GetDirectoryName(manifestPath)
            ?? throw new InvalidOperationException("Cache manifest has no parent directory.");
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(manifestPath)}.{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(
                temporaryPath,
                JsonSerializer.Serialize(manifest, ManifestJsonOptions));
            File.Move(temporaryPath, manifestPath, overwrite: true);
            Console.Error.WriteLine(
                $"[SONG CACHE] decision=manifest_upgraded engine={OmrPipeline.GetEngineName(manifest.Engine)} path=\"{manifestPath}\"");
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine(
                "[SONG CACHE] decision=manifest_upgrade_failed cache_reused=true " +
                $"error=\"{exception.Message}\"");
        }
        finally
        {
            DeleteTemporaryFile(temporaryPath);
        }
    }

    private static OmrSettings GetOmrSettings(OmrEngine engine) => engine switch
    {
        OmrEngine.Homr => new OmrSettings(
            Device: "cuda",
            CudaDevice: "CUDAExecutionProvider",
            PdfDpi: 300,
            Preprocessing: "homr-default-300-dpi",
            DefaultTempoBpm: 120),
        OmrEngine.Zeus => new OmrSettings(
            Device: "cuda",
            CudaDevice: "NVIDIA GeForce RTX 4050 Laptop GPU",
            PdfDpi: 300,
            Preprocessing: "width-fit-top-crop-bottom-pad",
            DefaultTempoBpm: 120,
            ModelSha256: OmrPipeline.ZeusModelSha256,
            InputDimensions: "1485x1050",
            DecoderFallbackPolicy: "beam3-repetition1.1-then-grammar-greedy",
            MaximumTokens: 2048),
        _ => throw new ArgumentOutOfRangeException(nameof(engine), engine, "Unknown OMR engine.")
    };

    private static List<VisualNote> MapOmrNotes(IReadOnlyCollection<MusicNote> rawNotes)
    {
        List<VisualNote> mappedNotes = new(rawNotes.Count);
        foreach (MusicNote rawNote in rawNotes)
        {
            int targetKeyIndex = rawNote.MidiPitch - 21;
            if (targetKeyIndex < 0 || targetKeyIndex >= 88)
            {
                continue;
            }

            Color color = targetKeyIndex >= 39 ? Color.SkyBlue : Color.Lime;
            mappedNotes.Add(new VisualNote(
                targetKeyIndex,
                rawNote.StartSeconds,
                rawNote.DurationSeconds,
                DefaultVelocity,
                color));
        }

        mappedNotes.Sort(static (left, right) =>
        {
            int startComparison = left.StartTime.CompareTo(right.StartTime);
            return startComparison != 0
                ? startComparison
                : left.TargetKeyIndex.CompareTo(right.TargetKeyIndex);
        });
        return mappedNotes;
    }

    private static void PersistCache(
        string sourcePath,
        string sourceHash,
        OmrEngine engine,
        CachePaths cachePaths,
        OmrResult result,
        IReadOnlyList<VisualNote> expectedNotes)
    {
        string temporaryMidiPath = Path.Combine(
            cachePaths.MidiDirectory,
            $".{Path.GetFileName(cachePaths.MidiPath)}.{Guid.NewGuid():N}.tmp");
        string temporaryManifestPath = Path.Combine(
            cachePaths.MidiDirectory,
            $".{Path.GetFileName(cachePaths.ManifestPath)}.{Guid.NewGuid():N}.tmp");
        string? temporaryPdfPath = null;

        try
        {
            WriteMidi(temporaryMidiPath, result);
            List<VisualNote> roundTripNotes = ReadMidi(temporaryMidiPath);
            ValidateRoundTrip(expectedNotes, roundTripNotes);
            string midiSha256 = ComputeSha256(temporaryMidiPath);
            double durationSeconds = GetTotalDuration(roundTripNotes);

            CacheManifest manifest = new(
                SourceSha256: sourceHash,
                Engine: engine,
                EngineRevision: result.EngineRevision,
                ModelRevision: OmrPipeline.GetModelRevision(engine),
                BridgeSchemaVersion: result.SchemaVersion,
                OmrSettings: GetOmrSettings(engine),
                TempoPolicy: TempoPolicy,
                CreatedUtc: DateTimeOffset.UtcNow,
                NoteCount: roundTripNotes.Count,
                TempoCount: result.TempoChanges.Count,
                CacheManifestVersion: CacheManifestVersion,
                MidiSha256: midiSha256,
                DurationSeconds: durationSeconds,
                DisplayName: Path.GetFileNameWithoutExtension(sourcePath));
            string manifestJson = JsonSerializer.Serialize(manifest, ManifestJsonOptions);
            File.WriteAllText(temporaryManifestPath, manifestJson);

            if (string.Equals(
                    Path.GetExtension(sourcePath),
                    ".pdf",
                    StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(
                    Path.GetFullPath(sourcePath),
                    Path.GetFullPath(cachePaths.PdfPath),
                    StringComparison.OrdinalIgnoreCase))
            {
                temporaryPdfPath = Path.Combine(
                    cachePaths.PdfDirectory,
                    $".{Path.GetFileName(cachePaths.PdfPath)}.{Guid.NewGuid():N}.tmp");
                File.Copy(sourcePath, temporaryPdfPath, overwrite: false);
            }

            File.Move(temporaryMidiPath, cachePaths.MidiPath, overwrite: true);
            File.Move(temporaryManifestPath, cachePaths.ManifestPath, overwrite: true);
            if (temporaryPdfPath is not null)
            {
                File.Move(temporaryPdfPath, cachePaths.PdfPath, overwrite: true);
                File.SetLastWriteTimeUtc(
                    cachePaths.PdfPath,
                    File.GetLastWriteTimeUtc(sourcePath));
            }
        }
        finally
        {
            DeleteTemporaryFile(temporaryMidiPath);
            DeleteTemporaryFile(temporaryManifestPath);
            if (temporaryPdfPath is not null)
            {
                DeleteTemporaryFile(temporaryPdfPath);
            }
        }
    }

    private static void WriteMidi(string outputPath, OmrResult result)
    {
        List<ScheduledEvent> scheduledEvents = new(
            result.Notes.Count * 2 + result.TempoChanges.Count);
        foreach (TempoChange tempoChange in result.TempoChanges)
        {
            long tick = ToTicks(tempoChange.StartBeat, "tempo start beat");
            long microseconds = Tempo
                .FromBeatsPerMinute(tempoChange.Bpm)
                .MicrosecondsPerQuarterNote;
            scheduledEvents.Add(new ScheduledEvent(
                tick,
                0,
                new SetTempoEvent(microseconds)));
        }

        Dictionary<int, long[]> channelEndTicksByPitch = [];
        foreach (MusicNote note in result.Notes
                     .OrderBy(static note => note.StartBeat)
                     .ThenBy(static note => note.PartIndex)
                     .ThenBy(static note => note.VoiceIdentifier, StringComparer.Ordinal)
                     .ThenBy(static note => note.MidiPitch))
        {
            if (note.MidiPitch is < 21 or > 108)
            {
                continue;
            }

            long startTick = ToTicks(note.StartBeat, "note start beat");
            long durationTicks = Math.Max(1, ToTicks(note.DurationBeats, "note duration"));
            long endTick = checked(startTick + durationTicks);
            int channel = AllocateChannel(
                channelEndTicksByPitch,
                note.MidiPitch,
                startTick,
                endTick);
            FourBitNumber midiChannel = (FourBitNumber)(byte)channel;

            scheduledEvents.Add(new ScheduledEvent(
                startTick,
                2,
                new NoteOnEvent(
                    (SevenBitNumber)(byte)note.MidiPitch,
                    (SevenBitNumber)(byte)DefaultVelocity)
                {
                    Channel = midiChannel
                }));
            scheduledEvents.Add(new ScheduledEvent(
                endTick,
                1,
                new NoteOffEvent(
                    (SevenBitNumber)(byte)note.MidiPitch,
                    (SevenBitNumber)(byte)0)
                {
                    Channel = midiChannel
                }));
        }

        scheduledEvents.Sort(static (left, right) =>
        {
            int timeComparison = left.Time.CompareTo(right.Time);
            return timeComparison != 0
                ? timeComparison
                : left.Priority.CompareTo(right.Priority);
        });

        TrackChunk trackChunk = new();
        long previousTick = 0;
        foreach (ScheduledEvent scheduledEvent in scheduledEvents)
        {
            scheduledEvent.Event.DeltaTime = scheduledEvent.Time - previousTick;
            trackChunk.Events.Add(scheduledEvent.Event);
            previousTick = scheduledEvent.Time;
        }

        MidiFile midiFile = new(trackChunk)
        {
            TimeDivision = new TicksPerQuarterNoteTimeDivision(TicksPerQuarterNote)
        };
        midiFile.Write(outputPath, overwriteFile: false);
    }

    private static int AllocateChannel(
        Dictionary<int, long[]> endTicksByPitch,
        int midiPitch,
        long startTick,
        long endTick)
    {
        if (!endTicksByPitch.TryGetValue(midiPitch, out long[]? channelEndTicks))
        {
            channelEndTicks = new long[16];
            endTicksByPitch[midiPitch] = channelEndTicks;
        }

        for (int channel = 0; channel < channelEndTicks.Length; channel++)
        {
            if (channelEndTicks[channel] <= startTick)
            {
                channelEndTicks[channel] = endTick;
                return channel;
            }
        }

        throw new InvalidOperationException(
            $"More than 16 simultaneous notes use MIDI pitch {midiPitch}; " +
            "the MIDI cache cannot represent this overlap without losing note boundaries.");
    }

    private static List<VisualNote> ReadMidi(string midiPath)
    {
        MidiFile midiFile = MidiFile.Read(midiPath);
        if (midiFile.TimeDivision is not TicksPerQuarterNoteTimeDivision)
        {
            throw new InvalidDataException(
                "Cached MIDI does not use ticks-per-quarter-note timing.");
        }

        TempoMap tempoMap = midiFile.GetTempoMap();
        List<VisualNote> notes = [];
        foreach (MidiNote midiNote in midiFile.GetNotes())
        {
            int targetKeyIndex = midiNote.NoteNumber - 21;
            if (targetKeyIndex < 0 || targetKeyIndex >= 88)
            {
                continue;
            }

            MetricTimeSpan start = TimeConverter.ConvertTo<MetricTimeSpan>(
                midiNote.Time,
                tempoMap);
            MetricTimeSpan duration = LengthConverter.ConvertTo<MetricTimeSpan>(
                midiNote.Length,
                midiNote.Time,
                tempoMap);
            if (duration.TotalSeconds <= 0)
            {
                continue;
            }
            Color color = targetKeyIndex >= 39 ? Color.SkyBlue : Color.Lime;
            notes.Add(new VisualNote(
                targetKeyIndex,
                start.TotalSeconds,
                duration.TotalSeconds,
                midiNote.Velocity,
                color));
        }

        notes.Sort(static (left, right) =>
        {
            int startComparison = left.StartTime.CompareTo(right.StartTime);
            return startComparison != 0
                ? startComparison
                : left.TargetKeyIndex.CompareTo(right.TargetKeyIndex);
        });
        return notes;
    }

    private static void ValidateRoundTrip(
        IReadOnlyList<VisualNote> expected,
        IReadOnlyList<VisualNote> actual)
    {
        if (expected.Count != actual.Count)
        {
            throw new InvalidDataException(
                $"MIDI round trip changed note count from {expected.Count} to {actual.Count}.");
        }

        VisualNote[] canonicalExpected = expected
            .OrderBy(static note => note.StartTime)
            .ThenBy(static note => note.TargetKeyIndex)
            .ThenBy(static note => note.Duration)
            .ThenBy(static note => note.Velocity)
            .ToArray();
        VisualNote[] canonicalActual = actual
            .OrderBy(static note => note.StartTime)
            .ThenBy(static note => note.TargetKeyIndex)
            .ThenBy(static note => note.Duration)
            .ThenBy(static note => note.Velocity)
            .ToArray();

        const double toleranceSeconds = 0.01;
        for (int index = 0; index < canonicalExpected.Length; index++)
        {
            VisualNote expectedNote = canonicalExpected[index];
            VisualNote actualNote = canonicalActual[index];
            if (expectedNote.TargetKeyIndex != actualNote.TargetKeyIndex ||
                Math.Abs(expectedNote.StartTime - actualNote.StartTime) > toleranceSeconds ||
                Math.Abs(expectedNote.Duration - actualNote.Duration) > toleranceSeconds)
            {
                throw new InvalidDataException(
                    $"MIDI round trip changed note {index}: expected key/time/duration " +
                    $"{expectedNote.TargetKeyIndex}/{expectedNote.StartTime:F6}/" +
                    $"{expectedNote.Duration:F6}, actual " +
                    $"{actualNote.TargetKeyIndex}/{actualNote.StartTime:F6}/" +
                    $"{actualNote.Duration:F6}.");
            }
        }
    }

    private static double GetTotalDuration(IReadOnlyCollection<VisualNote> notes) =>
        notes.Count == 0 ? 0 : notes.Max(note => note.StartTime + note.Duration);

    private static long ToTicks(double value, string description)
    {
        if (!double.IsFinite(value) || value < 0)
        {
            throw new InvalidOperationException(
                $"Cannot cache invalid {description} {value}.");
        }
        return checked((long)Math.Round(
            value * TicksPerQuarterNote,
            MidpointRounding.AwayFromZero));
    }

    private static void DeleteTemporaryFile(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    internal static string GetMidiPathForTesting(
        string sourcePath,
        OmrEngine engine,
        string applicationDirectory)
    {
        return CreateCachePaths(sourcePath, engine, applicationDirectory).MidiPath;
    }

    internal static void WriteMidiForTesting(string outputPath, OmrResult result)
    {
        WriteMidi(outputPath, result);
    }

    internal static List<VisualNote> ReadMidiForTesting(string midiPath)
    {
        return ReadMidi(midiPath);
    }

    internal static void PersistCacheForTesting(
        string sourcePath,
        OmrEngine engine,
        string applicationDirectory,
        OmrResult result)
    {
        string validatedSource = ValidateInputPath(sourcePath);
        string sourceHash = ComputeSha256(validatedSource);
        CachePaths paths = CreateCachePaths(validatedSource, engine, applicationDirectory);
        Directory.CreateDirectory(paths.MidiDirectory);
        Directory.CreateDirectory(paths.PdfDirectory);
        PersistCache(
            validatedSource,
            sourceHash,
            engine,
            paths,
            result,
            MapOmrNotes(result.Notes));
    }

    internal static bool IsCacheHitForTesting(
        string sourcePath,
        OmrEngine engine,
        string applicationDirectory) =>
        IsCacheHit(sourcePath, engine, applicationDirectory);

    private static bool IsCacheHit(
        string sourcePath,
        OmrEngine engine,
        string applicationDirectory)
    {
        string validatedSource = ValidateInputPath(sourcePath);
        CachePaths paths = CreateCachePaths(validatedSource, engine, applicationDirectory);
        return TryReadCache(
            ComputeSha256(validatedSource),
            engine,
            paths,
            out _);
    }

    internal static List<VisualNote> LoadOrCreateForTesting(
        string inputPath,
        OmrEngine engine,
        string applicationDirectory,
        Func<string, OmrEngine, OmrResult> pipeline)
    {
        return LoadOrCreateCore(
            inputPath,
            engine,
            applicationDirectory,
            (path, selectedEngine, _) => pipeline(path, selectedEngine),
            CancellationToken.None).Notes;
    }

    internal static IReadOnlyList<PdfLibraryEntry> GetPdfLibraryForTesting(
        string applicationDirectory) => GetPdfLibraryCore(applicationDirectory);

    internal static IReadOnlyList<CachedSongEntry> GetCachedSongsForTesting(
        string applicationDirectory) => GetCachedSongsCore(applicationDirectory);

    private sealed record CachePaths(
        string PdfDirectory,
        string MidiDirectory,
        string PdfPath,
        string MidiPath,
        string ManifestPath);

    private sealed record ScheduledEvent(long Time, int Priority, MidiEvent Event);

    private sealed record OmrSettings(
        string Device,
        string CudaDevice,
        int PdfDpi,
        string Preprocessing,
        double DefaultTempoBpm,
        string? ModelSha256 = null,
        string? InputDimensions = null,
        string? DecoderFallbackPolicy = null,
        int? MaximumTokens = null);

    private sealed record CacheManifest(
        string SourceSha256,
        OmrEngine Engine,
        string EngineRevision,
        string ModelRevision,
        int BridgeSchemaVersion,
        OmrSettings OmrSettings,
        string TempoPolicy,
        DateTimeOffset CreatedUtc,
        int NoteCount,
        int TempoCount,
        int CacheManifestVersion = 1,
        string? MidiSha256 = null,
        double? DurationSeconds = null,
        string? DisplayName = null);

    private sealed record LegacyOmrSettings(
        string Device,
        int? BeamWidth,
        int PdfDpi,
        double DefaultTempoBpm,
        string? BackboneRevision);

    private sealed record LegacyExpandedOmrSettings(
        string Device,
        string CudaDevice,
        string? Decoding,
        string? MaximumDimensions,
        string Preprocessing,
        double DefaultTempoBpm,
        string? ModelSha256,
        string? ConfigSha256,
        string? RuntimeVersion,
        string? PatchSha256,
        string? PartCombinationPolicy,
        string? RuntimeHelperSha256);

    private sealed record LegacyExpandedCacheManifest(
        string SourceSha256,
        OmrEngine Engine,
        string EngineRevision,
        string ModelRevision,
        int BridgeSchemaVersion,
        LegacyExpandedOmrSettings? OmrSettings,
        string TempoPolicy,
        DateTimeOffset CreatedUtc,
        int NoteCount,
        int TempoCount,
        int CacheManifestVersion = 1,
        string? MidiSha256 = null,
        double? DurationSeconds = null,
        string? DisplayName = null);

    private sealed record LegacyCacheManifest(
        string SourceSha256,
        OmrEngine Engine,
        string EngineRevision,
        string ModelRevision,
        int BridgeSchemaVersion,
        LegacyOmrSettings? OmrSettings,
        string TempoPolicy,
        DateTimeOffset CreatedUtc,
        int NoteCount,
        int TempoCount);
}
