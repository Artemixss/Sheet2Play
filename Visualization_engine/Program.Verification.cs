using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using Raylib_cs;

namespace SynthesiaClone;

internal static partial class Program
{
    private static int RunOmrVerification(string[] arguments)
    {
        try
        {
            // --verify-omr[-reopen] INPUT|MANIFEST ENGINE EVIDENCE_DIR [--timing-fix]; the last
            // verifies the timing-fix interpretation, as the landing page switch selects it.
            bool timingFix = arguments.Length == 5 && arguments[4] == "--timing-fix";
            if (arguments.Length is not (4 or 5) || (arguments.Length == 5 && arguments[4] != "--timing-fix") ||
                !Enum.TryParse(arguments[2], true, out OmrEngine engine) ||
                engine is not (OmrEngine.Homr or OmrEngine.Homr465 or OmrEngine.Homr480 or OmrEngine.MusicXml))
                throw new ArgumentException("Expected input (or manifest), engine, and exclusive evidence directory.");
            string destination = Path.GetFullPath(arguments[3]);
            if (Directory.Exists(destination)) throw new IOException("Evidence directory already exists.");
            Directory.CreateDirectory(destination);
            Stopwatch elapsed = Stopwatch.StartNew();
            SongLoadResult song = arguments[0] == "--verify-omr-reopen"
                ? SongCache.LoadRecent(new(arguments[1], "Verification", engine, DateTimeOffset.MinValue), recordRecent: false)
                : SongCache.LoadOrCreateDetailed(arguments[1], engine, recordRecent: false, timingCorrection: timingFix);
            elapsed.Stop();
            if (song.ManifestRelativePath is null || song.NoteCount == 0 || song.Engine != engine)
                throw new InvalidDataException("Verified scan has no valid cache or the wrong engine.");
            SongLoadResult reopened = SongCache.LoadRecent(new(song.ManifestRelativePath,
                song.DisplayName, engine, DateTimeOffset.MinValue), recordRecent: false);
            if (!reopened.LoadedFromCache || reopened.NoteCount != song.NoteCount)
                throw new InvalidDataException("Cache reopen did not preserve the complete score.");
            string manifestPath = Path.Combine(SongCache.ApplicationDirectory, song.ManifestRelativePath);
            // A song package's interpretation names its performance, and the package manifest two
            // folders up holds the conversion's identity; a MIDI cache holds both in one manifest.
            bool packaged = Path.GetFileName(manifestPath) == "interpretation.json";
            string contentPath = packaged
                ? Path.Combine(Path.GetDirectoryName(manifestPath)!, "performance.json")
                : manifestPath[..^".cache.json".Length];
            string identityPath = packaged
                ? Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(manifestPath)!)!)!, "song.json")
                : manifestPath;
            using JsonDocument manifest = JsonDocument.Parse(File.ReadAllText(identityPath));
            if (OmrPipeline.IsPinnedNative(engine) &&
                (manifest.RootElement.GetProperty("runtime_profile_sha256").GetString() != OmrPipeline.GetProfileSha256(engine) ||
                 manifest.RootElement.GetProperty("model_revision").GetString() != OmrPipeline.GetModelRevision(engine)))
                throw new InvalidDataException($"Published cache identity does not match {OmrPipeline.GetEngineName(engine)}.");
            RenderVerifiedPreview(song, destination);
            var report = new
            {
                executable = Environment.ProcessPath,
                executableSha256 = VerificationHash(Environment.ProcessPath!),
                library = SongCache.ApplicationDirectory,
                settings = AppSettingsStore.GetSettingsPath(),
                savedEngine = AppSettingsStore.LoadEngine().ToString(),
                engine = song.Engine.ToString(),
                manifest = song.ManifestRelativePath,
                manifestSha256 = VerificationHash(manifestPath),
                kind = packaged ? "song-package" : "midi-cache",
                contentSha256 = VerificationHash(contentPath),
                timingFix,
                song.NoteCount,
                song.LoadedFromCache,
                elapsedSeconds = elapsed.Elapsed.TotalSeconds,
                reopened = true,
                physicalAudioTested = false
            };
            File.WriteAllText(Path.Combine(destination, "result.json"),
                JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine($"Verified {song.Engine}: {song.NoteCount} notes; cache reopen passed.");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    /// <summary>
    /// Opens every song the library holds the way the app does - each MIDI cache, each custom
    /// MIDI file and each song package - and builds its playback session, without converting
    /// or interpreting anything. <c>--verify-library EVIDENCE_DIR</c> writes <c>library.json</c>.
    /// </summary>
    private static int RunLibraryVerification(string[] arguments)
    {
        try
        {
            if (arguments.Length != 2)
                throw new ArgumentException("Expected an exclusive evidence directory.");
            string destination = Path.GetFullPath(arguments[1]);
            if (Directory.Exists(destination)) throw new IOException("Evidence directory already exists.");
            Directory.CreateDirectory(destination);
            string library = SongCache.ApplicationDirectory;
            List<LibraryCheck> rows = [];

            void Check(string kind, string path, OmrEngine engine, Func<SongLoadResult> load)
            {
                try
                {
                    SongLoadResult song = load();
                    PlaybackSession session = new(song.Notes);
                    // With expression off a song must play exactly as before expression existed.
                    SongPlayback off = ExpressionPlayback.ForSong(song, ExpressionOptions.None);
                    bool unchanged = new PlaybackSession(off.Notes, pedal: off.Pedal).Events.SequenceEqual(session.Events);
                    SongPlayback on = ExpressionPlayback.ForSong(song, new ExpressionOptions());
                    PlaybackSession expressed = new(on.Notes, pedal: on.Pedal);
                    ExpressionAvailability available = ExpressionPlayback.Availability(song);
                    rows.Add(new LibraryCheck(kind, path, engine.ToString(), unchanged, session.Notes.Count,
                        Math.Round(session.TotalDuration, 3),
                        unchanged ? null : "With expression off the events differ from the plain notes.",
                        unchanged, expressed.Notes.Count, expressed.Pedal.Count,
                        expressed.Notes.Select(static note => note.Velocity).Distinct().Count(),
                        Math.Round(expressed.TotalDuration, 3),
                        $"pedal={available.Pedal} dynamics={available.Dynamics} " +
                        $"articulations={available.Articulations} repeats={available.Repeats}",
                        EventsHash(session), EventsHash(expressed)));
                }
                catch (Exception error)
                {
                    rows.Add(new LibraryCheck(kind, path, engine.ToString(), false, 0, 0,
                        $"{error.GetType().Name}: {error.Message}"));
                }
            }

            string midiRoot = Path.Combine(library, "songs", "midi");
            foreach (OmrEngine engine in Enum.GetValues<OmrEngine>().Where(engine => engine != OmrEngine.DirectMidi))
            {
                string folder = Path.Combine(midiRoot, OmrPipeline.GetEngineName(engine));
                if (!Directory.Exists(folder)) continue;
                foreach (string manifest in Directory.EnumerateFiles(folder, "*.mid.cache.json").Order())
                {
                    string relative = Path.GetRelativePath(library, manifest);
                    Check("midi-cache", relative, engine, () => SongCache.LoadRecent(
                        new(relative, Path.GetFileName(manifest), engine, DateTimeOffset.MinValue), recordRecent: false));
                }
            }
            string custom = Path.Combine(midiRoot, "custom");
            if (Directory.Exists(custom))
            {
                foreach (string file in Directory.EnumerateFiles(custom).Where(file =>
                             Path.GetExtension(file).ToLowerInvariant() is ".mid" or ".midi").Order())
                {
                    Check("custom-midi", Path.GetRelativePath(library, file), OmrEngine.DirectMidi,
                        () => SongCache.LoadOrCreateDetailed(file, OmrEngine.DirectMidi, recordRecent: false));
                }
            }
            foreach (CachedSongEntry entry in SongCache.GetCachedSongs(AppSettingsStore.LoadTimingCorrection())
                         .Where(entry => entry.RecentSong.ManifestRelativePath.EndsWith("interpretation.json")))
            {
                Check("song-package", entry.RecentSong.ManifestRelativePath, entry.RecentSong.Engine,
                    () => SongCache.LoadRecent(entry.RecentSong, recordRecent: false));
            }

            var report = new
            {
                executable = Environment.ProcessPath,
                executableSha256 = VerificationHash(Environment.ProcessPath!),
                library,
                checkedUtc = DateTimeOffset.UtcNow,
                rows
            };
            File.WriteAllText(Path.Combine(destination, "library.json"),
                JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            int failed = rows.Count(static row => !row.Ok);
            Console.WriteLine($"Checked {rows.Count} songs: {rows.Count - failed} played, {failed} failed.");
            return failed == 0 ? 0 : 1;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private sealed record LibraryCheck(string Kind, string Path, string Engine, bool Ok, int Notes, double Seconds,
        string? Error, bool? ExpressionOffUnchanged = null, int? ExpressedNotes = null, int? PedalChanges = null,
        int? DistinctVelocities = null, double? ExpressedSeconds = null, string? Available = null,
        string? PlainEventsSha256 = null, string? ExpressedEventsSha256 = null);

    /// <summary>
    /// Every event a session would send, exactly, so two builds can be compared song by song: equal
    /// hashes mean the same notes and pedal at the same times.
    /// </summary>
    private static string EventsHash(PlaybackSession session) =>
        Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(string.Join('\n',
            session.Events.Select(static item => FormattableString.Invariant(
                $"{item.Time:R}|{item.KeyIndex}|{item.Velocity}|{item.IsNoteOn}|{item.IsPedal}")))))).ToLowerInvariant();

    private static string VerificationHash(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static void RenderVerifiedPreview(SongLoadResult song, string destination)
    {
        Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
        Raylib.InitWindow(InitialWidth, InitialHeight, "Sheet2Play verification");
        try
        {
            UiTheme.InitializeFonts();
            UiLayout layout = UiLayout.Create(InitialWidth, InitialHeight);
            PlaybackController playback = new(new PlaybackSession(song.Notes), new NullMidiOutput(), new PlaybackClock(() => 0));
            Keyboard keyboard = new(layout.Width, layout.HitLineY, layout.KeyboardHeight);
            GameState state = GameState.Playing;
            int failed = Capture(destination, "preview", layout, () =>
                DrawPlayback(playback, song, keyboard, false, 0, new PlaybackRateEditor(), new AudioOffsetEditor(), ref state, layout));
            if (failed != 0) throw new InvalidDataException("Published playback preview did not render.");
        }
        finally
        {
            UiTheme.ShutdownFonts();
            Raylib.CloseWindow();
        }
    }
}
