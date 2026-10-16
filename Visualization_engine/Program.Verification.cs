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
            if (arguments.Length != 4 || !Enum.TryParse(arguments[2], true, out OmrEngine engine) ||
                engine is not (OmrEngine.Homr or OmrEngine.Homr465 or OmrEngine.MusicXml))
                throw new ArgumentException("Expected input (or manifest), engine, and exclusive evidence directory.");
            string destination = Path.GetFullPath(arguments[3]);
            if (Directory.Exists(destination)) throw new IOException("Evidence directory already exists.");
            Directory.CreateDirectory(destination);
            Stopwatch elapsed = Stopwatch.StartNew();
            SongLoadResult song = arguments[0] == "--verify-omr-reopen"
                ? SongCache.LoadRecent(new(arguments[1], "Verification", engine, DateTimeOffset.MinValue), recordRecent: false)
                : SongCache.LoadOrCreateDetailed(arguments[1], engine, recordRecent: false);
            elapsed.Stop();
            if (song.ManifestRelativePath is null || song.NoteCount == 0 || song.Engine != engine)
                throw new InvalidDataException("Verified scan has no valid cache or the wrong engine.");
            SongLoadResult reopened = SongCache.LoadRecent(new(song.ManifestRelativePath,
                song.DisplayName, engine, DateTimeOffset.MinValue), recordRecent: false);
            if (!reopened.LoadedFromCache || reopened.NoteCount != song.NoteCount)
                throw new InvalidDataException("Cache reopen did not preserve the complete score.");
            string manifestPath = Path.Combine(SongCache.ApplicationDirectory, song.ManifestRelativePath);
            string midiPath = manifestPath[..^".cache.json".Length];
            using JsonDocument manifest = JsonDocument.Parse(File.ReadAllText(manifestPath));
            if (engine == OmrEngine.Homr465 &&
                (manifest.RootElement.GetProperty("runtime_profile_sha256").GetString() != OmrPipeline.Homr465ProfileSha256 ||
                 manifest.RootElement.GetProperty("model_revision").GetString() != OmrPipeline.Homr465ModelRevision))
                throw new InvalidDataException("Published cache identity does not match HOMR 465.");
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
                midiSha256 = VerificationHash(midiPath),
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
