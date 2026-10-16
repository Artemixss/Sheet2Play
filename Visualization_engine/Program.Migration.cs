using System.Diagnostics;
using System.Text.Json;

namespace SynthesiaClone;

internal static partial class Program
{
    private static int RunMigration(string[] args)
    {
        try
        {
            if (args.Length == 3 && args[1] == "inventory")
            {
                LibraryMigrationInventory.Freeze(Path.GetFullPath(args[2]));
                return 0;
            }
            if (args.Length != 4 || args[1] != "resume")
                throw new ArgumentException("Use --reconvert inventory INVENTORY.json or --reconvert resume INVENTORY.json JOURNAL.json.");
            string inventoryPath = Path.GetFullPath(args[2]);
            MigrationInventory inventory = LibraryMigrationState.Read<MigrationInventory>(inventoryPath);
            string helper = Path.Combine(AppContext.BaseDirectory, "Bridge", "library_inventory.py");
            LibraryMigrationState.VerifyHash(helper, inventory.HelperSha256);
            MigrationOperations operations = new(
                item => ProcessMigrationItem(inventory, item),
                (item, success) => VerifyMigrationSuccess(inventory, item, success),
                (item, success) => RecentSongsStore.MapCommittedCache(item.OldManifest, success.Manifest));
            MigrationJournal result = LibraryMigrationRunner.Resume(inventoryPath, args[3], SongCache.ApplicationDirectory,
                LibraryMigrationState.Hash(Environment.ProcessPath!), operations, TimeSpan.FromHours(4));
            return result.Entries.Any(entry => entry.Status == "pending") ? 2 : 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"Migration interrupted: {error}");
            return 2;
        }
    }

    private static MigrationSuccess ProcessMigrationItem(MigrationInventory inventory, MigrationItem item)
    {
        string source = LibraryMigrationState.LibraryPath(inventory.Library, item.SourceRelativePath!);
        Stopwatch elapsed = Stopwatch.StartNew();
        SongLoadResult result = SongCache.LoadOrCreateDetailed(source, OmrEngine.Homr465, recordRecent: false);
        if (result.ManifestRelativePath is null || result.Engine != OmrEngine.Homr465 || result.NoteCount <= 0)
            throw new InvalidDataException("Migration did not produce a complete candidate cache.");
        string manifest = LibraryMigrationState.LibraryPath(inventory.Library, result.ManifestRelativePath);
        string midi = manifest[..^".cache.json".Length];
        MigrationSuccess success = new(result.ManifestRelativePath, LibraryMigrationState.Hash(manifest),
            LibraryMigrationState.Hash(midi), result.NoteCount, result.LoadedFromCache, elapsed.Elapsed.TotalSeconds);
        VerifyMigrationSuccess(inventory, item, success);
        return success;
    }

    private static void VerifyMigrationSuccess(MigrationInventory inventory, MigrationItem item, MigrationSuccess success)
    {
        string manifest = LibraryMigrationState.LibraryPath(inventory.Library, success.Manifest);
        if (!success.Manifest.Replace('\\', '/').StartsWith("songs/midi/homr465/", StringComparison.Ordinal) ||
            !manifest.EndsWith(".mid.cache.json", StringComparison.Ordinal) || success.NoteCount <= 0)
            throw new InvalidDataException("Invalid candidate success record.");
        LibraryMigrationState.VerifyHash(manifest, success.ManifestSha256);
        LibraryMigrationState.VerifyHash(manifest[..^".cache.json".Length], success.MidiSha256);
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(manifest));
        JsonElement cache = document.RootElement;
        if (cache.GetProperty("source_sha256").GetString() != item.SourceSha256 ||
            cache.GetProperty("runtime_profile_sha256").GetString() != inventory.ProfileSha256 ||
            cache.GetProperty("model_revision").GetString() != inventory.ModelRevision ||
            cache.GetProperty("engine_revision").GetString() != inventory.EngineRevision ||
            cache.GetProperty("midi_sha256").GetString() != success.MidiSha256)
            throw new InvalidDataException("Candidate cache source/model/profile/MIDI identity does not match.");
        SongLoadResult reopened = SongCache.LoadRecent(new(success.Manifest, "Migration", OmrEngine.Homr465,
            DateTimeOffset.MinValue), recordRecent: false);
        if (!reopened.LoadedFromCache || reopened.NoteCount != success.NoteCount)
            throw new InvalidDataException("Candidate MIDI/cache did not survive reopening.");
    }
}
