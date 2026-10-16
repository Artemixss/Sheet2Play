using System.Diagnostics;

namespace SynthesiaClone;

internal sealed record MigrationOperations(Func<MigrationItem, MigrationSuccess> Process,
    Action<MigrationItem, MigrationSuccess> VerifySuccess, Action<MigrationItem, MigrationSuccess> MapRecent);

internal static class LibraryMigrationRunner
{
    internal static MigrationJournal Resume(string inventoryPath, string journalPath, string library,
        string executableSha256, MigrationOperations operations, TimeSpan deadline)
    {
        if (deadline <= TimeSpan.Zero || deadline > TimeSpan.FromHours(4))
            throw new ArgumentOutOfRangeException(nameof(deadline));
        inventoryPath = Path.GetFullPath(inventoryPath);
        journalPath = Path.GetFullPath(journalPath);
        if (string.Equals(inventoryPath, journalPath, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Inventory and journal must be separate files.");
        Directory.CreateDirectory(Path.GetDirectoryName(journalPath)!);
        // The OS lock survives stale lock-file names and prevents two resume writers.
        using FileStream journalLock = new(journalPath + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        MigrationInventory inventory = LibraryMigrationState.Read<MigrationInventory>(inventoryPath);
        LibraryMigrationInventory.Validate(inventory, library);
        string inventorySha256 = LibraryMigrationState.Hash(inventoryPath);
        MigrationJournal journal = File.Exists(journalPath)
            ? LibraryMigrationState.Read<MigrationJournal>(journalPath)
            : new(1, inventorySha256, inventory.ProfileSha256, executableSha256, DateTimeOffset.UtcNow,
                inventory.Items.Select(item => new MigrationEntry(item.Id,
                    item.SourceRelativePath is null ? "unavailable" : "pending", Error: item.UnavailableReason)).ToArray());
        ValidateJournal(journal, inventory, inventorySha256, executableSha256);
        Dictionary<string, MigrationEntry> entries = journal.Entries.ToDictionary(entry => entry.Id);
        Stopwatch elapsed = Stopwatch.StartNew();

        void Save()
        {
            journal = journal with { UpdatedUtc = DateTimeOffset.UtcNow,
                Entries = inventory.Items.Select(item => entries[item.Id]).ToArray() };
            LibraryMigrationState.Write(journalPath, journal, overwrite: true);
        }

        Save();
        for (int index = 0; index < inventory.Items.Count; index++)
        {
            MigrationItem item = inventory.Items[index];
            MigrationEntry entry = entries[item.Id];
            try
            {
                if (elapsed.Elapsed >= deadline) throw new TimeoutException("Migration session deadline reached; resume explicitly.");
                LibraryMigrationInventory.VerifyInput(inventory, item);
                if (entry.Status == "success")
                {
                    operations.VerifySuccess(item, entry.Success!);
                    operations.MapRecent(item, entry.Success!);
                    Console.WriteLine($"MIGRATION {index + 1}/{inventory.Items.Count} {item.Id} success reused-journal");
                    continue;
                }
                if (entry.Status is "failed" or "unavailable")
                {
                    Console.WriteLine($"MIGRATION {index + 1}/{inventory.Items.Count} {item.Id} {entry.Status} accounted");
                    continue;
                }
                entries[item.Id] = entry with { Error = null, ErrorCode = null };
                Save();
                MigrationSuccess success = operations.Process(item);
                LibraryMigrationInventory.VerifyInput(inventory, item);
                operations.VerifySuccess(item, success);
                entries[item.Id] = new(item.Id, "success", success);
                // Commit the success before mapping recents; resume repairs a crash between these writes.
                Save();
                operations.MapRecent(item, success);
                Console.WriteLine($"MIGRATION {index + 1}/{inventory.Items.Count} {item.Id} success notes={success.NoteCount} cache={success.ReusedCache}");
            }
            catch (OmrPipelineException error) when (IsOrdinaryFailure(error))
            {
                entries[item.Id] = new(item.Id, "failed", Error: error.Message, ErrorCode: error.ErrorCode);
                Save();
                Console.WriteLine($"MIGRATION {index + 1}/{inventory.Items.Count} {item.Id} failed code={error.ErrorCode}");
            }
            catch (Exception error)
            {
                entries[item.Id] = entries[item.Id] with { Error = error.Message,
                    ErrorCode = error is OmrPipelineException omr ? omr.ErrorCode : error.GetType().Name };
                Save();
                Console.Error.WriteLine($"MIGRATION STOP {item.Id}: {error.Message}");
                throw;
            }
        }
        Save();
        Console.WriteLine($"Migration accounted: {journal.Entries.Count(e => e.Status == "success")} success, " +
                          $"{journal.Entries.Count(e => e.Status == "failed")} failed, " +
                          $"{journal.Entries.Count(e => e.Status == "unavailable")} unavailable, " +
                          $"{journal.Entries.Count(e => e.Status == "pending")} pending.");
        return journal;
    }

    internal static bool IsOrdinaryFailure(OmrPipelineException error) =>
        error.ErrorCode is "NORMALIZATION_FAILED" or "HOMR_INFERENCE_FAILED";

    private static void ValidateJournal(MigrationJournal journal, MigrationInventory inventory,
        string inventorySha256, string executableSha256)
    {
        if (journal.Version != 1 || journal.InventorySha256 != inventorySha256 ||
            journal.ProfileSha256 != inventory.ProfileSha256 || journal.ExecutableSha256 != executableSha256 ||
            journal.Entries.Count != inventory.Items.Count ||
            !journal.Entries.Select(e => e.Id).Order().SequenceEqual(inventory.Items.Select(i => i.Id).Order()) ||
            journal.Entries.Any(e => e.Status is not ("success" or "failed" or "unavailable" or "pending") ||
                (e.Status == "success") != (e.Success is not null)) ||
            journal.Entries.Any(e => (e.Status == "unavailable") !=
                (inventory.Items.Single(i => i.Id == e.Id).SourceRelativePath is null)))
            throw new InvalidDataException("Resume journal identity or accounting does not match the frozen inventory.");
    }
}
